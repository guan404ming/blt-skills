"""Verify translated lyrics against musical constraints."""

from __future__ import annotations

from .patterns import analyze_pattern_alignment, get_syllable_patterns
from .rhyme import check_rhyme, extract_rhyme_ending
from .syllables import count_syllables


def verify_all_constraints(
    lines: list[str],
    language: str,
    target_syllables: list[int],
    rhyme_scheme: str = "",
    target_patterns: list[list[int]] | None = None,
) -> dict:
    """Verify all translation constraints at once.

    Args:
        lines: List of translated lines.
        language: Language code.
        target_syllables: Target syllable count per line.
        rhyme_scheme: Expected rhyme scheme (e.g., "AABB").
        target_patterns: Optional target syllable patterns.

    Returns:
        Dictionary with verification results and feedback.
    """
    syllables = [count_syllables(line, language) for line in lines]
    syllables_match = syllables == target_syllables

    rhyme_endings = [extract_rhyme_ending(line, language) for line in lines]

    feedback_parts = []

    # Syllable patterns (highest priority)
    patterns_match = True
    pattern_similarity_score = 1.0
    syllable_patterns = None

    if target_patterns:
        syllable_patterns = get_syllable_patterns(lines, language)
        patterns_match = syllable_patterns == target_patterns

        if not patterns_match:
            alignments = []
            total_similarity = 0.0
            for i, (actual, target) in enumerate(zip(syllable_patterns, target_patterns)):
                alignment = analyze_pattern_alignment(target, actual)
                alignments.append((i, alignment))
                total_similarity += alignment["similarity"]

            pattern_similarity_score = total_similarity / len(alignments) if alignments else 0.0

            pattern_feedback = _build_pattern_feedback_fuzzy(alignments)
            if pattern_feedback:
                if pattern_similarity_score >= 0.8:
                    severity = "Pattern acceptable (fuzzy match):"
                elif pattern_similarity_score >= 0.6:
                    severity = "Pattern close (minor adjustments needed):"
                else:
                    severity = "CRITICAL: Pattern mismatch:"
                feedback_parts.append(f"{severity}\n\n" + "\n\n".join(pattern_feedback))

    # Syllable counts (second priority)
    if not syllables_match:
        mismatches = _build_syllable_feedback(syllables, target_syllables)
        if mismatches:
            feedback_parts.append("Syllable count mismatches:\n" + "\n".join(mismatches))

    # Rhyme scheme (lowest priority)
    rhymes_valid = True
    if rhyme_scheme:
        rhymes_valid, rhyme_issues = _check_rhyme_scheme(rhyme_endings, rhyme_scheme, language)
        if rhyme_issues:
            feedback_parts.append("Rhyme issues:\n" + "\n".join(rhyme_issues))

    feedback = "\n\n".join(feedback_parts) if feedback_parts else "All constraints satisfied!"

    result = {
        "syllables": syllables,
        "syllables_match": syllables_match,
        "rhyme_endings": rhyme_endings,
        "rhymes_valid": rhymes_valid,
        "feedback": feedback,
    }

    if target_patterns:
        result["syllable_patterns"] = syllable_patterns
        result["patterns_match"] = patterns_match
        result["pattern_similarity_score"] = pattern_similarity_score

    return result


def _build_syllable_feedback(actual: list[int], target: list[int]) -> list[str]:
    mismatches = []
    for i, (act, tgt) in enumerate(zip(actual, target)):
        if act != tgt:
            diff = act - tgt
            if diff > 0:
                mismatches.append(f"Line {i + 1}: {act} syllables (need {diff} fewer)")
            else:
                mismatches.append(f"Line {i + 1}: {act} syllables (need {abs(diff)} more)")
    return mismatches


def _build_pattern_feedback_fuzzy(
    alignments: list[tuple[int, dict]],
) -> list[str]:
    feedback = []
    for line_idx, alignment in alignments:
        if not alignment["matches"]:
            similarity = alignment["similarity"]
            differences = alignment.get("differences", [])
            if differences:
                details = [f"Line {line_idx + 1}: {similarity:.0%} similar"]
                target_vals = [d["target_syllables"] for d in differences]
                current_vals = [d["current_syllables"] for d in differences]
                details.append(f"  Actual:  {current_vals}")
                details.append(f"  Target:  {target_vals}")
                suggestions = alignment.get("suggestions", [])
                if suggestions:
                    details.append("  Suggestions:")
                    for s in suggestions[:2]:
                        details.append(f"    - {s}")
                feedback.append("\n".join(details))
    return feedback


def _check_rhyme_scheme(
    rhyme_endings: list[str], rhyme_scheme: str, language: str
) -> tuple[bool, list[str]]:
    if not rhyme_endings or not rhyme_scheme:
        return True, []
    if len(rhyme_endings) != len(rhyme_scheme):
        return False, [
            f"Rhyme scheme length mismatch: expected {len(rhyme_scheme)}, got {len(rhyme_endings)}"
        ]

    rhyme_groups: dict[str, list[int]] = {}
    for i, label in enumerate(rhyme_scheme):
        rhyme_groups.setdefault(label, []).append(i)

    rhymes_valid = True
    issues = []
    for label, indices in rhyme_groups.items():
        if len(indices) > 1:
            base = rhyme_endings[indices[0]]
            for idx in indices[1:]:
                if not check_rhyme(base, rhyme_endings[idx], language):
                    rhymes_valid = False
                    issues.append(
                        f"Lines {indices[0] + 1} and {idx + 1} (group '{label}'): "
                        f"'{rhyme_endings[indices[0]]}' vs '{rhyme_endings[idx]}' "
                        f"don't rhyme"
                    )

    return rhymes_valid, issues
