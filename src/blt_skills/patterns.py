"""Syllable pattern analysis: word-level syllable distribution."""

from __future__ import annotations

import re

from .phonetics import normalize_language_code
from .syllables import count_syllables


def segment_words(lines: list[str], language: str) -> list[list[str]]:
    """Segment lines into words.

    Uses jieba for Chinese, space splitting for others.

    Args:
        lines: List of text lines.
        language: Language code.

    Returns:
        List of word lists for each line.
    """
    language = normalize_language_code(language)
    if not lines:
        return []

    result = []

    if language == "cmn":
        import jieba

        for line in lines:
            words = [w for w in jieba.cut(line) if w.strip()]
            result.append(words)
    else:
        for line in lines:
            cleaned = re.sub(r"[^\w\s'-]", "", line)
            words = [w for w in cleaned.split() if w.strip()]
            result.append(words)

    return result


def get_syllable_patterns(lines: list[str], language: str) -> list[list[int]]:
    """Get syllable pattern (syllables per word) for multiple lines.

    Args:
        lines: List of text lines.
        language: Language code.

    Returns:
        List of syllable patterns, e.g., [[1, 1, 3], [1, 2, 1]].
    """
    all_words = segment_words(lines, language)
    patterns = []
    for words in all_words:
        syllables = [count_syllables(word, language) for word in words]
        patterns.append(syllables)
    return patterns


def analyze_pattern_alignment(target_pattern: list[int], current_pattern: list[int]) -> dict:
    """Analyze alignment between target and current syllable patterns.

    Args:
        target_pattern: Target syllable pattern, e.g., [1, 2, 2, 1].
        current_pattern: Current syllable pattern, e.g., [1, 1, 2, 2].

    Returns:
        Dictionary with 'matches', 'similarity', 'differences',
        'suggestions', 'total_syllables_match'.
    """
    if not target_pattern or not current_pattern:
        return {
            "matches": target_pattern == current_pattern,
            "similarity": 0.0 if target_pattern != current_pattern else 1.0,
            "differences": [],
            "suggestions": [],
            "total_syllables_match": sum(target_pattern or []) == sum(current_pattern or []),
        }

    target_total = sum(target_pattern)
    current_total = sum(current_pattern)
    exact_match = target_pattern == current_pattern
    max_len = max(len(target_pattern), len(current_pattern))

    differences = []
    for i in range(max_len):
        target_val = target_pattern[i] if i < len(target_pattern) else 0
        current_val = current_pattern[i] if i < len(current_pattern) else 0
        diff = current_val - target_val
        if diff != 0:
            differences.append(
                {
                    "word_position": i,
                    "target_syllables": target_val,
                    "current_syllables": current_val,
                    "difference": diff,
                }
            )

    suggestions = []
    if not exact_match:
        if len(target_pattern) != len(current_pattern):
            suggestions.append(
                f"Word count mismatch: target has {len(target_pattern)} words, "
                f"current has {len(current_pattern)} words"
            )
        if target_total != current_total:
            syllable_diff = target_total - current_total
            if syllable_diff > 0:
                suggestions.append(f"Need to add {syllable_diff} syllables overall")
            else:
                suggestions.append(f"Need to remove {-syllable_diff} syllables overall")

        for d in differences:
            pos = d["word_position"]
            diff = d["difference"]
            if diff > 0:
                suggestions.append(
                    f"Word {pos + 1}: has {diff} too many syllables "
                    f"(target {d['target_syllables']}, current {d['current_syllables']})"
                )
            else:
                suggestions.append(
                    f"Word {pos + 1}: needs {-diff} more syllables "
                    f"(target {d['target_syllables']}, current {d['current_syllables']})"
                )

    position_similarity = (
        1.0
        if not differences
        else 1.0 - (sum(abs(d["difference"]) for d in differences) / target_total)
    )
    length_similarity = (
        1.0
        if len(target_pattern) == len(current_pattern)
        else max(0.0, 1.0 - (abs(len(target_pattern) - len(current_pattern)) / max_len))
    )
    total_similarity = (
        1.0
        if target_total == current_total
        else max(0.0, 1.0 - (abs(target_total - current_total) / target_total))
    )

    similarity = (
        (position_similarity * 0.5) + (length_similarity * 0.25) + (total_similarity * 0.25)
    )

    return {
        "matches": exact_match,
        "similarity": max(0.0, min(1.0, similarity)),
        "differences": differences,
        "suggestions": suggestions,
        "total_syllables_match": target_total == current_total,
    }


def score_syllable_patterns(
    target_patterns: list[list[int]], current_patterns: list[list[int]]
) -> dict:
    """Score overall syllable pattern quality across all lines.

    Args:
        target_patterns: Target syllable patterns for all lines.
        current_patterns: Current syllable patterns for all lines.

    Returns:
        Dictionary with overall_score, exact_match_rate, fuzzy_match_rate,
        average_similarity, worst_line, best_line, total_syllables_error,
        pattern_distribution_score.
    """
    if not target_patterns or not current_patterns:
        return {
            "overall_score": 0.0,
            "exact_match_rate": 0.0,
            "fuzzy_match_rate": 0.0,
            "average_similarity": 0.0,
            "worst_line": None,
            "best_line": None,
            "total_syllables_error": 0,
            "pattern_distribution_score": 0.0,
        }

    max_lines = max(len(target_patterns), len(current_patterns))
    exact_matches = 0
    fuzzy_matches = 0
    total_similarity = 0.0
    worst_alignment = None
    worst_similarity = 1.0
    best_alignment = None
    best_similarity = 0.0

    for i in range(max_lines):
        target = target_patterns[i] if i < len(target_patterns) else []
        current = current_patterns[i] if i < len(current_patterns) else []
        alignment = analyze_pattern_alignment(target, current)
        sim = alignment["similarity"]
        total_similarity += sim

        if alignment["matches"]:
            exact_matches += 1
        if sim >= 0.8:
            fuzzy_matches += 1
        if sim < worst_similarity:
            worst_similarity = sim
            worst_alignment = (i, alignment)
        if sim > best_similarity:
            best_similarity = sim
            best_alignment = (i, alignment)

    exact_match_rate = exact_matches / max_lines if max_lines > 0 else 0.0
    fuzzy_match_rate = fuzzy_matches / max_lines if max_lines > 0 else 0.0
    average_similarity = total_similarity / max_lines if max_lines > 0 else 0.0

    target_total = sum(sum(p) for p in target_patterns)
    current_total = sum(sum(p) for p in current_patterns)
    total_syllables_error = abs(target_total - current_total)

    pattern_distribution_score = (exact_match_rate * 0.7) + (fuzzy_match_rate * 0.3)
    syllable_score = (
        1.0
        if total_syllables_error == 0
        else max(0.0, 1.0 - (total_syllables_error / target_total))
    )
    overall_score = (exact_match_rate * 0.4) + (average_similarity * 0.3) + (syllable_score * 0.3)

    return {
        "overall_score": max(0.0, min(1.0, overall_score)),
        "exact_match_rate": exact_match_rate,
        "fuzzy_match_rate": fuzzy_match_rate,
        "average_similarity": average_similarity,
        "worst_line": {
            "line_idx": worst_alignment[0],
            "similarity": worst_alignment[1]["similarity"],
        }
        if worst_alignment
        else None,
        "best_line": {
            "line_idx": best_alignment[0],
            "similarity": best_alignment[1]["similarity"],
        }
        if best_alignment
        else None,
        "total_syllables_error": total_syllables_error,
        "pattern_distribution_score": pattern_distribution_score,
    }
