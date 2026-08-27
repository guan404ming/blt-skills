"""Shared utilities for benchmark scripts."""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

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
        "-o", "--output-dir", default="data/bench", help="Output directory (default: data/bench)"
    )
    parser.add_argument(
        "--target-lang",
        default=None,
        help="Override target language for all sampled songs (e.g. 'ja'). Default: cmn.",
    )
    return parser


def load_songs(args):
    repo_root = Path(__file__).resolve().parent.parent
    source_path = repo_root / "data" / "lyric-trans" / "datasets" / "data_parallel" / "test.source"
    if not source_path.exists():
        print(f"Error: Ou test split not found at {source_path}", file=sys.stderr)
        print(
            "Download with: uvx --from huggingface_hub hf download "
            "LongshenOu/lyric-trans-en2zh-data --repo-type dataset "
            "--local-dir data/lyric-trans && cd data/lyric-trans && unzip -q datasets.zip",
            file=sys.stderr,
        )
        sys.exit(1)

    method = getattr(args, "bench_method", "run")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = Path(args.output_dir) / f"{ts}_{method}"
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Sampling {args.n} songs (seed={args.seed})...", file=sys.stderr)
    songs = sample_ou_test(str(source_path), args.n, args.seed, args.lines_per_song)
    if len(songs) < args.n:
        print(f"Warning: only got {len(songs)} songs", file=sys.stderr)
    if args.target_lang:
        for song in songs:
            song["target_lang"] = args.target_lang
        print(f"Overriding target_lang -> {args.target_lang}", file=sys.stderr)

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


def save_results(results, method_name, songs, seed, outdir):
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
            val = re.sub(r"[\(（][^\)）]*[\)）]", "", val).strip()
            val = re.split(r"\s*[\(（]", val)[0].strip()
            val = re.split(r"\s+[-—]\s+", val)[0].strip()
            if val:
                translations.append(val)
    if len(translations) >= expected_count:
        return translations[-expected_count:]
    return None
