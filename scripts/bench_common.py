"""Shared utilities for benchmark scripts."""

import csv
import json
import re
import sys
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path

# Skill usage counter (thread-safe)

skill_counter: Counter = Counter()
_counter_lock = threading.Lock()


def reset_skill_counter():
    with _counter_lock:
        skill_counter.clear()


def get_skill_counts():
    with _counter_lock:
        return dict(skill_counter)


def _inc(skill, n=1):
    with _counter_lock:
        skill_counter[skill] += n


# Metric calculations


def levenshtein(seq1, seq2):
    m, n = len(seq1), len(seq2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq1[i - 1] == seq2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp[m][n]


def calc_ser(src_syl, tgt_syl):
    n = max(len(src_syl), len(tgt_syl))
    return levenshtein(src_syl, tgt_syl) / n if n else 0.0


def calc_scre(src_syl, tgt_syl):
    if not src_syl:
        return 0.0
    errs = []
    for s, t in zip(src_syl, tgt_syl):
        errs.append(abs(s - t) / s if s else (0.0 if t == 0 else 1.0))
    return sum(errs) / len(errs)


def scheme_to_labels(scheme):
    m, labels, nxt = {}, [], 0
    for c in scheme:
        if c not in m:
            m[c] = nxt
            nxt += 1
        labels.append(m[c])
    return labels


def calc_ari(src_scheme, tgt_scheme):
    if not src_scheme or not tgt_scheme:
        return 0.0
    from sklearn.metrics import adjusted_rand_score

    sl = scheme_to_labels(src_scheme)
    tl = scheme_to_labels(tgt_scheme)
    if len(sl) != len(tl):
        mx = max(len(sl), len(tl))
        nxt = max(max(sl), max(tl)) + 1
        if len(sl) < mx:
            sl += list(range(nxt, nxt + mx - len(sl)))
        if len(tl) < mx:
            tl += list(range(nxt, nxt + mx - len(tl)))
    return adjusted_rand_score(sl, tl)


# Song sampling


def sample_songs(csv_path, n, seed, lines_per_song, words_per_line):
    import random

    random.seed(seed)
    csv.field_size_limit(10 * 1024 * 1024)
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lyrics = row.get("lyrics", "").strip()
            artist = row.get("artist_name", "").strip() or "unknown"
            if lyrics and len(lyrics.split()) >= lines_per_song * words_per_line:
                rows.append((artist, lyrics))
    chosen = random.sample(rows, min(n, len(rows)))
    songs = []
    for i, (artist, lyrics) in enumerate(chosen, 1):
        words = lyrics.split()
        lines = []
        for j in range(lines_per_song):
            start = j * words_per_line
            end = start + words_per_line
            if end <= len(words):
                lines.append(" ".join(words[start:end]))
        if len(lines) == lines_per_song:
            songs.append(
                {
                    "id": f"genius_{i:03d}",
                    "source_lines": lines,
                    "source_lang": "en-us",
                    "target_lang": "cmn",
                    "metadata": {"artist": artist},
                }
            )
    return songs


def sample_ou_test(source_path, n, seed, lines_per_song):
    """Sample n test cases from Ou et al. 2023 lyric-trans en-zh test split.

    Each case is a window of `lines_per_song` consecutive non-empty lines from
    ``data_parallel/test.source``. Window starting indices are sampled with the
    given seed so the same n + seed always produces the same songs, matching
    the protocol described in the paper's phase_ablation_results.md.
    """
    import random

    with open(source_path, encoding="utf-8") as f:
        all_lines = [ln.strip() for ln in f if ln.strip()]

    max_start = len(all_lines) - lines_per_song
    if max_start < 0:
        return []

    rng = random.Random(seed)
    starts = rng.sample(range(max_start + 1), min(n, max_start + 1))
    starts.sort()

    songs = []
    for i, start in enumerate(starts, 1):
        window = all_lines[start : start + lines_per_song]
        songs.append(
            {
                "id": f"ou_{i:03d}",
                "source_lines": window,
                "source_lang": "en-us",
                "target_lang": "cmn",
                "metadata": {"artist": "ou-test", "test_start_line": start},
            }
        )
    return songs


# Shared CLI setup


def make_parser(description):
    import argparse

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("-n", type=int, required=True, help="Number of songs")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--lines-per-song", type=int, default=5, help="Lines per song (default: 5)")
    parser.add_argument(
        "--words-per-line", type=int, default=8, help="Words per line when splitting (default: 8)"
    )
    parser.add_argument(
        "-o", "--output-dir", default="data/bench", help="Output directory (default: data/bench)"
    )
    parser.add_argument(
        "--dataset",
        choices=("ou", "genius"),
        default="ou",
        help="Dataset: 'ou' (Ou 2023 en-zh test split, matches the paper) "
        "or 'genius' (random English lyric chunks). Default: ou.",
    )
    parser.add_argument(
        "--target-lang",
        default=None,
        help="Override target language for all sampled songs (e.g. 'ja'). "
        "Default: the per-dataset target ('cmn' for ou/genius).",
    )
    return parser


def load_songs(args):
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    dataset = getattr(args, "dataset", "ou")

    if dataset == "ou":
        source_path = (
            repo_root / "data" / "lyric-trans" / "datasets" / "data_parallel" / "test.source"
        )
        if not source_path.exists():
            print(f"Error: Ou test split not found at {source_path}", file=sys.stderr)
            print(
                "Download with: uvx --from huggingface_hub hf download "
                "LongshenOu/lyric-trans-en2zh-data --repo-type dataset "
                "--local-dir data/lyric-trans && cd data/lyric-trans && unzip -q datasets.zip",
                file=sys.stderr,
            )
            sys.exit(1)
        sample_fn = lambda: sample_ou_test(  # noqa: E731
            str(source_path), args.n, args.seed, args.lines_per_song
        )
    elif dataset == "genius":
        data_csv = repo_root / "data" / "genius-lyrics" / "english_lyrics_some_with_genres.csv"
        if not data_csv.exists():
            print(f"Error: genius dataset not found at {data_csv}", file=sys.stderr)
            print(
                "Download with: uvx --from huggingface_hub hf download "
                "brunokreiner/genius-lyrics --repo-type dataset --local-dir data/genius-lyrics",
                file=sys.stderr,
            )
            sys.exit(1)
        sample_fn = lambda: sample_songs(  # noqa: E731
            str(data_csv), args.n, args.seed, args.lines_per_song, args.words_per_line
        )
    else:  # pragma: no cover - argparse already restricts
        raise ValueError(f"unknown dataset: {dataset}")

    method = getattr(args, "bench_method", "all")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = Path(args.output_dir) / f"{ts}_{method}"
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Sampling {args.n} songs from {dataset} (seed={args.seed})...", file=sys.stderr)
    songs = sample_fn()
    if len(songs) < args.n:
        print(f"Warning: only got {len(songs)} songs", file=sys.stderr)
    tgt_override = getattr(args, "target_lang", None)
    if tgt_override:
        for s in songs:
            s["target_lang"] = tgt_override
        print(f"Overriding target_lang -> {tgt_override}", file=sys.stderr)

    songs_path = outdir / "test_songs.json"
    with open(songs_path, "w", encoding="utf-8") as f:
        json.dump(songs, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(songs)} songs to {songs_path}", file=sys.stderr)

    return songs, outdir


def evaluate_song(song, translations):
    """Evaluate translations for a single song, return result dict."""
    from blt_skills import count_syllables, detect_rhyme_scheme

    lines = song["source_lines"]
    src_lang = song["source_lang"]
    tgt_lang = song["target_lang"]

    _inc("syllable-counter", len(lines) + len(translations))
    _inc("rhyme-analyzer", 2)

    src_syl = [count_syllables(line, src_lang) for line in lines]
    src_rhyme = detect_rhyme_scheme(lines, src_lang)
    tgt_syl = [count_syllables(t, tgt_lang) for t in translations]
    tgt_rhyme = detect_rhyme_scheme(translations, tgt_lang)
    matches = sum(1 for a, b in zip(src_syl, tgt_syl) if a == b)

    return {
        "id": song["id"],
        "artist": song["metadata"]["artist"],
        "ser": calc_ser(src_syl, tgt_syl),
        "scre": calc_scre(src_syl, tgt_syl),
        "ari": calc_ari(src_rhyme, tgt_rhyme),
        "src_syl": src_syl,
        "tgt_syl": tgt_syl,
        "src_rhyme": src_rhyme,
        "tgt_rhyme": tgt_rhyme,
        "match": f"{matches}/{len(lines)}",
        "translations": translations,
    }


def save_results(results, method_name, songs, seed, outdir, skill_counts=None):
    """Save results.json and report.md."""

    def avg(vals):
        return sum(vals) / len(vals) if vals else 0.0

    output = {
        "method": method_name,
        "date": datetime.now().isoformat(),
        "n": len(songs),
        "seed": seed,
        "avg_ser": avg([r["ser"] for r in results]),
        "avg_scre": avg([r["scre"] for r in results]),
        "avg_ari": avg([r["ari"] for r in results]),
        "avg_time": avg([r.get("time_seconds", 0) for r in results]),
        "results": results,
    }
    if skill_counts:
        output["skill_counts"] = skill_counts

    results_path = outdir / "results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {results_path}", file=sys.stderr)

    # Report
    lines = []
    lines.append(f"# {method_name} Benchmark Report")
    lines.append("")
    lines.append(f"- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"- **Songs**: {len(songs)}")
    lines.append(f"- **Seed**: {seed}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| **SER** (lower better) | {output['avg_ser']:.4f} |")
    lines.append(f"| **SCRE** (lower better) | {output['avg_scre']:.4f} |")
    lines.append(f"| **ARI** (higher better) | {output['avg_ari']:.4f} |")
    lines.append(f"| **Avg Time (s)** | {output['avg_time']:.2f} |")
    lines.append("")

    if skill_counts:
        lines.append("## Skill Usage")
        lines.append("")
        lines.append("| Skill | Calls |")
        lines.append("|-------|-------|")
        for skill, count in sorted(skill_counts.items()):
            lines.append(f"| {skill} | {count} |")
        lines.append(f"| **Total** | **{sum(skill_counts.values())}** |")
        lines.append("")

    lines.append("## Per-Song Results")
    lines.append("")
    lines.append("| Song | Artist | Match | SER | SCRE | ARI | Time |")
    lines.append("|------|--------|-------|-----|------|-----|------|")
    for r in results:
        lines.append(
            f"| {r['id']} | {r['artist']} | {r['match']} | "
            f"{r['ser']:.2f} | {r['scre']:.2f} | {r['ari']:.2f} | "
            f"{r.get('time_seconds', 0):.1f}s |"
        )
    lines.append("")

    lines.append("## Sample Translations")
    lines.append("")
    for i, (song, r) in enumerate(zip(songs[:3], results[:3])):
        lines.append(f"### {song['id']} ({song['metadata']['artist']})")
        lines.append("")
        lines.append("**Source:**")
        lines.append("```")
        for j, src in enumerate(song["source_lines"], 1):
            lines.append(f"{j}. {src}")
        lines.append("```")
        lines.append("")
        lines.append(f"**Translation** (match {r['match']}):")
        lines.append("```")
        for j, t in enumerate(r["translations"], 1):
            lines.append(f"{j}. {t} [{r['tgt_syl'][j - 1]}]")
        lines.append("```")
        lines.append("")

    report_path = outdir / "report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Saved {report_path}", file=sys.stderr)

    # Print summary to stdout
    print(
        json.dumps(
            {
                "avg_ser": round(output["avg_ser"], 4),
                "avg_scre": round(output["avg_scre"], 4),
                "avg_ari": round(output["avg_ari"], 4),
                "avg_time": round(output["avg_time"], 2),
            },
            indent=2,
        )
    )


# CC+Skills translation


def extract_constraints(lines, lang):
    from blt_skills import count_syllables, detect_rhyme_scheme, get_syllable_patterns

    _inc("syllable-counter", len(lines))
    _inc("rhyme-analyzer")
    _inc("syllable-pattern-analyzer")
    return {
        "syllables": [count_syllables(line, lang) for line in lines],
        "rhyme_scheme": detect_rhyme_scheme(lines, lang),
        "patterns": get_syllable_patterns(lines, lang),
    }


def parse_single_line(text):
    """Strip leading numbering, surrounding quotes, and parenthetical tails from a one-line response."""
    if not text:
        return ""
    for raw in text.strip().splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^\d+[\.\)]\s*(.+)$", line)
        if m:
            line = m.group(1).strip()
        if (line.startswith('"') and line.endswith('"')) or (
            line.startswith("'") and line.endswith("'")
        ):
            line = line[1:-1]
        line = re.split(r"\s*[\(（]", line)[0].strip()
        line = re.split(r"\s+[-—]\s+", line)[0].strip()
        if line:
            return line
    return ""


def parse_translations(text, expected_count):
    translations: list[str] = []
    for line in text.strip().split("\n"):
        m = re.match(r"\d+[\.\)]\s*(.+)", line.strip())
        if m:
            val = m.group(1).strip()
            if (val.startswith('"') and val.endswith('"')) or (
                val.startswith("'") and val.endswith("'")
            ):
                val = val[1:-1]
            val = re.split(r"\s*[\(（]", val)[0].strip()
            val = re.split(r"\s+[-—]\s+", val)[0].strip()
            if val:
                translations.append(val)
    if len(translations) >= expected_count:
        return translations[:expected_count]
    return None


CLAUDE_EFFORT: str | None = None  # set by run_cc.py from --effort, applied per call


def call_claude(prompt, model=None, timeout=300, retries=2, effort=None):
    """Call claude CLI with retry-on-empty-output and short backoff."""
    import subprocess
    import time as _time

    cmd = ["claude", "-p", prompt]
    if model:
        cmd.extend(["--model", model])
    eff = effort or CLAUDE_EFFORT
    if eff:
        cmd.extend(["--effort", eff])

    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            print(f"claude timeout after {timeout}s (attempt {attempt + 1})", file=sys.stderr)
            _time.sleep(2 + attempt * 3)
            continue
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"claude subprocess error: {exc} (attempt {attempt + 1})", file=sys.stderr)
            _time.sleep(2 + attempt * 3)
            continue
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip()
            print(
                f"claude rc={result.returncode} (attempt {attempt + 1}): {err[:300]}",
                file=sys.stderr,
            )
            _time.sleep(2 + attempt * 3)
            continue
        out = result.stdout.strip()
        if out:
            return out
        # Empty stdout but rc=0 — treat as transient and retry
        print(f"claude empty stdout (attempt {attempt + 1})", file=sys.stderr)
        _time.sleep(2 + attempt * 3)
    return None


def translate_with_claude(lines, source_lang, target_lang, constraints, model=None):
    from blt_skills import count_syllables

    target_syls = constraints["syllables"]
    rhyme = constraints["rhyme_scheme"]
    n = len(lines)

    prompt = f"""Translate these {source_lang} lyrics to {target_lang}.

Source lines:
{chr(10).join(f"{i + 1}. {line}" for i, line in enumerate(lines))}

Constraints:
- Target syllable counts per line: {target_syls}
- Source rhyme scheme: {rhyme}
- For Chinese: each character = 1 syllable, strip punctuation when counting.
- Preserve poetic meaning and emotional impact.

IMPORTANT: Return ONLY numbered translated lines.
NO explanations, NO annotations, NO syllable counts. Example format:
1. 中文翻译
2. 中文翻译"""

    max_attempts = 5
    translations = None

    for attempt in range(max_attempts):
        print(f"  Attempt {attempt + 1}/{max_attempts}...", file=sys.stderr)
        output = call_claude(prompt, model=model)
        if output is None:
            continue

        translations = parse_translations(output, n)
        if translations is None:
            print(f"  Could not parse {n} lines from output", file=sys.stderr)
            continue

        _inc("syllable-counter", len(translations))
        actual = [count_syllables(t, target_lang) for t in translations]
        mismatches = [
            (i, actual[i], target_syls[i]) for i in range(n) if actual[i] != target_syls[i]
        ]

        if not mismatches:
            print(f"  All lines match on attempt {attempt + 1}", file=sys.stderr)
            return translations

        print(f"  {len(mismatches)} mismatches, refining...", file=sys.stderr)

        fix_lines = []
        for i, act, tgt in mismatches:
            fix_lines.append(
                f'Line {i + 1}: got {act} syllables, need {tgt}. Current: "{translations[i]}"'
            )

        prompt = f"""Fix these {target_lang} lyric translations.
Each Chinese character = 1 syllable (strip punctuation).

{chr(10).join(fix_lines)}

Keep the other lines unchanged. Return ONLY ALL {n} lines numbered, NO explanations:
{chr(10).join(f"{i + 1}. {translations[i]}" for i in range(n))}"""

    return translations


# Multi-phase Claude orchestration (mirrors the Qwen pipeline used in the paper)


def _phase0_vanilla(lines, source_lang, target_lang, model, stats):
    """Vanilla baseline: plain translation prompt, no constraints, no skills."""
    import time as _time

    n = len(lines)
    src_block = chr(10).join(f"{i + 1}. {line}" for i, line in enumerate(lines))
    prompt = f"""Translate the following {n} song lyric lines from {source_lang} to {target_lang}.

Source lines:
{src_block}

Output exactly {n} translated lines, numbered 1-{n}. No explanations, no annotations.
"""
    t0 = _time.time()
    output = call_claude(prompt, model=model)
    stats["phase0_time_s"] = stats.get("phase0_time_s", 0.0) + (_time.time() - t0)
    stats["phase0_calls"] = stats.get("phase0_calls", 0) + 1
    if output is None:
        return None
    return parse_translations(output, n)


def _phase1(lines, source_lang, target_lang, constraints, model, stats, show_rhyme_pattern=True):
    """Phase 1: single-call initial translation.

    With ``show_rhyme_pattern=True`` (default) all three constraints are exposed;
    with ``False`` only syllable counts are given (syllable-counter-only ablation).
    """
    import time as _time

    target_syls = constraints["syllables"]
    rhyme = constraints["rhyme_scheme"]
    patterns = constraints["patterns"]
    n = len(lines)
    src_block = chr(10).join(f"{i + 1}. {line}" for i, line in enumerate(lines))

    if show_rhyme_pattern:
        constraint_block = f"""CONSTRAINT 1: SYLLABLE COUNTS (MUST MATCH EXACTLY) per line: {target_syls}
CONSTRAINT 2: RHYME SCHEME (preserve grouping): {rhyme}
CONSTRAINT 3: SYLLABLE PATTERNS per line: {patterns}"""
        intro = "while meeting THREE musical constraints"
    else:
        constraint_block = f"""CONSTRAINT: SYLLABLE COUNTS (MUST MATCH EXACTLY) per line: {target_syls}"""
        intro = "while matching the target syllable counts"

    prompt = f"""Translate ALL {n} lines from {source_lang} to {target_lang} {intro}.

Source lines:
{src_block}

{constraint_block}

Notes:
- For Chinese: each character = 1 syllable; strip punctuation when counting.
- Preserve poetic meaning and emotional impact.

Output exactly {n} translated lines, numbered 1-{n}. No explanations, no annotations.
"""
    t0 = _time.time()
    output = call_claude(prompt, model=model)
    stats["phase1_time_s"] = stats.get("phase1_time_s", 0.0) + (_time.time() - t0)
    stats["phase1_calls"] = stats.get("phase1_calls", 0) + 1
    if output is None:
        return None
    return parse_translations(output, n)


def _prompt_only_verifier(lines, source_lang, target_lang, constraints, model, rounds, stats):
    """Prompt-only multi-round verifier baseline: the LLM self-counts and self-refines
    in-prompt for a fixed number of rounds, with NO external syllable-counter gating.
    Isolates whether the gain comes from iteration alone vs. deterministic tool calls."""
    import time as _time

    target_syls = constraints["syllables"]
    n = len(lines)
    src_block = chr(10).join(f"{i + 1}. {line}" for i, line in enumerate(lines))

    prompt = f"""Translate ALL {n} lines from {source_lang} to {target_lang} matching the target syllable counts.

Source lines:
{src_block}

Target syllable counts per line: {target_syls}
- For Chinese: each character = 1 syllable; strip punctuation when counting.
- Count the syllables of each line yourself and make sure they match exactly.
- Preserve poetic meaning and emotional impact.

Output exactly {n} translated lines, numbered 1-{n}. No explanations, no annotations.
"""
    t0 = _time.time()
    output = call_claude(prompt, model=model)
    stats["pv_time_s"] = stats.get("pv_time_s", 0.0) + (_time.time() - t0)
    stats["pv_calls"] = stats.get("pv_calls", 0) + 1
    if output is None:
        return None
    translations = parse_translations(output, n)
    if translations is None:
        return None

    for _ in range(rounds):
        cur_block = chr(10).join(f"{i + 1}. {translations[i]}" for i in range(n))
        prompt = f"""Check each translated line and fix any whose syllable count does not match the target.
Count the syllables of each line carefully yourself (Chinese: 1 character = 1 syllable, ignore punctuation).

Target syllable counts per line: {target_syls}

Current translations:
{cur_block}

Revise only the lines that are off-count; keep correct lines unchanged and preserve meaning.
Output exactly {n} translated lines, numbered 1-{n}. No explanations, no annotations.
"""
        t0 = _time.time()
        out = call_claude(prompt, model=model)
        stats["pv_time_s"] = stats.get("pv_time_s", 0.0) + (_time.time() - t0)
        stats["pv_calls"] = stats.get("pv_calls", 0) + 1
        if out is None:
            continue
        revised = parse_translations(out, n)
        if revised is not None:
            translations = revised
    return translations


def _phase2_refine_line(src_line, current, target_syl, target_lang, model, max_iter, stats):
    """Phase 2: refine a single line until syllable count matches or budget exhausted.

    Returns the closest attempt found (smallest |actual - target|).
    """
    import time as _time

    from blt_skills import count_syllables

    best = current
    best_actual = count_syllables(best, target_lang)
    _inc("syllable-counter")
    if best_actual == target_syl:
        return best
    best_diff = abs(best_actual - target_syl)

    for _ in range(max_iter):
        delta = target_syl - best_actual
        action = (
            f"add {delta} syllable(s)" if delta > 0 else f"remove {-delta} syllable(s)"
        )
        prompt = f"""Adjust this translation to have EXACTLY {target_syl} syllables.
Focus ONLY on syllable count. Minimize meaning changes.

Original: "{src_line}"
Current:  "{best}"
Current syllables: {best_actual}/{target_syl}
Action: {action}

STRATEGIES:
- If too long: remove adjectives, use shorter words, merge concepts
- If too short: add descriptive words, use longer characters

Output ONLY the adjusted translation. No quotes, no explanations.
"""
        t0 = _time.time()
        out = call_claude(prompt, model=model)
        stats["phase2_time_s"] = stats.get("phase2_time_s", 0.0) + (_time.time() - t0)
        stats["phase2_calls"] = stats.get("phase2_calls", 0) + 1
        if out is None:
            continue
        cand = parse_single_line(out)
        if not cand:
            continue
        cand_actual = count_syllables(cand, target_lang)
        _inc("syllable-counter")
        diff = abs(cand_actual - target_syl)
        if diff < best_diff:
            best = cand
            best_actual = cand_actual
            best_diff = diff
        if best_diff == 0:
            return best
    return best


def _phase3_refine_pattern(src_line, current, target_pattern, target_lang, model, threshold, stats):
    """Phase 3: refine word-level distribution if pattern similarity below threshold.

    Accept revision only if: similarity strictly improves AND total syllable count is preserved.
    """
    import time as _time

    from blt_skills import count_syllables, get_syllable_patterns
    from blt_skills.patterns import analyze_pattern_alignment

    cur_pattern = get_syllable_patterns([current], target_lang)[0]
    _inc("syllable-pattern-analyzer")
    align = analyze_pattern_alignment(target_pattern, cur_pattern)
    if align.get("matches") or align.get("similarity", 0.0) >= threshold:
        stats["phase3_skipped"] = stats.get("phase3_skipped", 0) + 1
        return current

    suggestions = align.get("suggestions") or []
    suggest_block = "\n".join(f"- {s}" for s in suggestions) if suggestions else "- (none)"
    target_total = sum(target_pattern)

    prompt = f"""Adjust the word distribution in this translation WITHOUT changing total syllable count.

Original line:        "{src_line}"
Current translation:  "{current}"
Current pattern:      {cur_pattern} (total: {sum(cur_pattern)} syllables)
Target pattern:       {list(target_pattern)} (total: {target_total} syllables)

Adjustments needed:
{suggest_block}

Keep total syllable count at {target_total}. Adjust word choice to match the target pattern.
Output ONLY the adjusted translation. No quotes, no explanations.
"""
    t0 = _time.time()
    out = call_claude(prompt, model=model)
    stats["phase3_time_s"] = stats.get("phase3_time_s", 0.0) + (_time.time() - t0)
    stats["phase3_calls"] = stats.get("phase3_calls", 0) + 1
    if out is None:
        stats["phase3_failed_call"] = stats.get("phase3_failed_call", 0) + 1
        return current
    cand = parse_single_line(out)
    if not cand:
        stats["phase3_failed_parse"] = stats.get("phase3_failed_parse", 0) + 1
        return current

    cur_total = count_syllables(current, target_lang)
    cand_total = count_syllables(cand, target_lang)
    _inc("syllable-counter", 2)
    if cand_total != cur_total:
        stats["phase3_rejected_syl"] = stats.get("phase3_rejected_syl", 0) + 1
        return current  # rejected: would break Phase 2's match

    cand_pattern = get_syllable_patterns([cand], target_lang)[0]
    _inc("syllable-pattern-analyzer")
    cand_align = analyze_pattern_alignment(target_pattern, cand_pattern)
    if cand_align.get("similarity", 0.0) > align.get("similarity", 0.0):
        stats["phase3_accepted"] = stats.get("phase3_accepted", 0) + 1
        return cand
    stats["phase3_rejected_sim"] = stats.get("phase3_rejected_sim", 0) + 1
    return current


def translate_with_claude_phases(
    lines,
    source_lang,
    target_lang,
    constraints,
    model=None,
    phases=3,
    max_iter_p2=10,
    p3_threshold=0.8,
    metrics_out=None,
    ablation="none",
):
    """Multi-phase Claude orchestration matching the paper's pipeline.

    phases=0 -> Vanilla baseline (plain translate prompt, no constraints, no skills).
    phases=1 -> Phase 1 only (skill-aware initial translation).
    phases=2 -> Phase 1 + per-line syllable refinement.
    phases=3 -> Phase 1+2+3 (also per-line pattern refinement).

    If ``metrics_out`` is a mutable dict it is filled with phase-level timing,
    LLM call counts, post-phase syllable match counts, and Phase 3 outcome
    breakdown (accepted / rejected_syl / rejected_sim / skipped).
    """
    from blt_skills import count_syllables

    n = len(lines)
    target_syls = constraints["syllables"]
    target_patterns = constraints.get("patterns") or [[s] for s in target_syls]
    stats = metrics_out if metrics_out is not None else {}

    if phases == 0:
        translations = _phase0_vanilla(lines, source_lang, target_lang, model, stats)
        if translations is None:
            return None
        if len(translations) < n:
            translations = list(translations) + [""] * (n - len(translations))
        return translations[:n]

    if ablation == "prompt-verify":
        translations = _prompt_only_verifier(
            lines, source_lang, target_lang, constraints, model, max_iter_p2, stats
        )
        if translations is None:
            return None
        if len(translations) < n:
            translations = list(translations) + [""] * (n - len(translations))
        return translations[:n]

    show_rp = ablation != "sc-only"
    translations = _phase1(
        lines, source_lang, target_lang, constraints, model, stats, show_rhyme_pattern=show_rp
    )
    if translations is None:
        return None
    if len(translations) < n:
        translations = list(translations) + [""] * (n - len(translations))
    translations = translations[:n]

    actual = [count_syllables(t, target_lang) for t in translations]
    _inc("syllable-counter", n)
    stats["phase1_match"] = sum(1 for a, t in zip(actual, target_syls) if a == t)

    if phases <= 1:
        return translations

    for i in range(n):
        translations[i] = _phase2_refine_line(
            lines[i],
            translations[i],
            target_syls[i],
            target_lang,
            model,
            max_iter_p2,
            stats,
        )

    actual = [count_syllables(t, target_lang) for t in translations]
    _inc("syllable-counter", n)
    stats["phase2_match"] = sum(1 for a, t in zip(actual, target_syls) if a == t)

    if phases <= 2:
        return translations

    for i in range(n):
        translations[i] = _phase3_refine_pattern(
            lines[i],
            translations[i],
            target_patterns[i],
            target_lang,
            model,
            p3_threshold,
            stats,
        )

    actual = [count_syllables(t, target_lang) for t in translations]
    _inc("syllable-counter", n)
    stats["phase3_match"] = sum(1 for a, t in zip(actual, target_syls) if a == t)

    return translations


# CLT baseline inference


CLT_DEFAULT_MODEL = "LongshenOu/lyric-trans-en2zh"

CLT_BAD_WORDS_PATH = str(
    Path(__file__).resolve().parent.parent.parent
    / "blt"
    / "ControllableLyricTranslation"
    / "BartFinetune"
    / "tokenizers"
    / "misc"
    / "bad_word_list.json"
)


def load_clt_model(model_path=None, device="cuda"):
    from transformers import MBart50TokenizerFast, MBartForConditionalGeneration

    mp = model_path or CLT_DEFAULT_MODEL
    model = MBartForConditionalGeneration.from_pretrained(mp)
    tokenizer = MBart50TokenizerFast.from_pretrained(mp)
    model.to(device)
    model.eval()
    return model, tokenizer


def load_clt_bad_words(path=None):
    import os

    p = path or CLT_BAD_WORDS_PATH
    if not os.path.exists(p):
        return None
    ids = json.load(open(p))
    return [[i] for i in ids]


def clt_translate(
    model,
    tokenizer,
    lines,
    lengths,
    rhymes=None,
    boundaries=None,
    bad_words_ids=None,
    device="cuda",
    num_beams=5,
    max_length=36,
):
    import torch
    import torch.nn.functional as F

    n = len(lines)
    if rhymes is None:
        rhymes = [1] * n
    if boundaries is None:
        boundaries = [[0] * length for length in lengths]

    tokenizer.src_lang = "en_XX"
    tokenizer.tgt_lang = "zh_CN"

    encoded = tokenizer(lines, return_tensors="pt", padding=True).to(device)
    input_ids = encoded["input_ids"]
    attention_mask = encoded["attention_mask"]

    tgt_lens = [f"len_{x}" for x in lengths]
    t1 = tokenizer(
        tgt_lens,
        add_special_tokens=False,
        return_tensors="pt",
        max_length=1,
        padding=False,
        truncation=True,
    )
    tgt_lens = t1["input_ids"].to(device)
    attn_len = t1["attention_mask"].to(device)

    tgt_rhymes = [f"rhy_{x}" for x in rhymes]
    t2 = tokenizer(
        tgt_rhymes,
        add_special_tokens=False,
        return_tensors="pt",
        max_length=1,
        padding=False,
        truncation=True,
    )
    tgt_rhymes = t2["input_ids"].to(device)

    tgt_stress = ["".join(f"str_{i}" for i in x[::-1]) for x in boundaries]
    t3 = tokenizer(tgt_stress, return_tensors="pt", add_special_tokens=False, padding=True)
    tgt_stress = t3["input_ids"].to(device)
    attn_str = t3["attention_mask"].to(device)
    pad_bit = 20 - tgt_stress.shape[1]
    if pad_bit > 0:
        tgt_stress = F.pad(tgt_stress, (0, pad_bit, 0, 0), value=1).to(device)
        attn_str = F.pad(attn_str, (0, pad_bit, 0, 0), value=1).to(device)

    input_ids = torch.cat((tgt_lens, tgt_stress, input_ids), dim=1)
    attention_mask = torch.cat((attn_len, attn_str, attention_mask), dim=1)

    decoder_input_ids = torch.zeros(size=(n, 2), dtype=torch.long).to(device)
    decoder_input_ids[:, 0] = tgt_rhymes.squeeze()
    decoder_input_ids[:, 1] = 2

    with torch.no_grad():
        generated = model.generate(
            inputs=input_ids,
            attention_mask=attention_mask,
            decoder_input_ids=decoder_input_ids,
            num_beams=num_beams,
            max_length=max_length,
            forced_bos_token_id=tokenizer.lang_code_to_id["zh_CN"],
            bad_words_ids=bad_words_ids,
        )

    results = []
    for line in tokenizer.batch_decode(generated, skip_special_tokens=True):
        results.append(line[::-1])
    return results
