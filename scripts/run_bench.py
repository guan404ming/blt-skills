#!/usr/bin/env python3
"""
Run both CC+Skills and CLT baseline benchmarks and generate comparison report.

Usage:
    uv run scripts/run_bench.py -n 5
    uv run scripts/run_bench.py -n 10 --seed 123 -o data/bench_run2
"""

import json
import sys
import time
from datetime import datetime

from bench_common import (
    clt_translate,
    evaluate_song,
    extract_constraints,
    get_skill_counts,
    load_clt_bad_words,
    load_clt_model,
    load_songs,
    make_parser,
    reset_skill_counter,
    save_results,
    translate_with_claude,
)

from blt_skills import count_syllables


def main():
    parser = make_parser("Run CC+Skills and CLT baseline benchmarks")
    parser.add_argument("--cc-model", default=None, help="Claude model (e.g. sonnet, opus, haiku)")
    parser.add_argument(
        "--clt-model", default=None, help="CLT model path (default: HuggingFace auto-download)"
    )
    parser.add_argument("--device", default="cuda", help="Device for CLT inference (default: cuda)")
    args = parser.parse_args()
    args.bench_method = "all"

    songs, outdir = load_songs(args)
    cc_dir = outdir / "cc"
    clt_dir = outdir / "clt"
    cc_dir.mkdir(parents=True, exist_ok=True)
    clt_dir.mkdir(parents=True, exist_ok=True)

    # Run CC+Skills
    print("\n=== CC+Skills ===", file=sys.stderr)
    reset_skill_counter()
    cc_results = []
    for song in songs:
        sid = song["id"]
        artist = song["metadata"]["artist"]
        constraints = extract_constraints(song["source_lines"], song["source_lang"])
        print(f"{sid} ({artist}): src_syl={constraints['syllables']}", file=sys.stderr)

        t0 = time.time()
        translations = translate_with_claude(
            song["source_lines"],
            song["source_lang"],
            song["target_lang"],
            constraints,
            model=args.cc_model,
        )
        elapsed = time.time() - t0

        if translations is None:
            print("  FAILED", file=sys.stderr)
            translations = [""] * len(song["source_lines"])

        r = evaluate_song(song, translations)
        r["time_seconds"] = round(elapsed, 2)
        cc_results.append(r)
        print(
            f"  SER={r['ser']:.4f} SCRE={r['scre']:.4f} ARI={r['ari']:.4f} "
            f"match={r['match']} time={elapsed:.1f}s",
            file=sys.stderr,
        )

    cc_skill_counts = get_skill_counts()
    save_results(cc_results, "cc-skills", songs, args.seed, cc_dir, skill_counts=cc_skill_counts)

    # Run CLT
    print("\n=== CLT Baseline ===", file=sys.stderr)
    mp = args.clt_model or "LongshenOu/lyric-trans-en2zh"
    print(f"Loading CLT model from {mp}...", file=sys.stderr)
    model, tokenizer = load_clt_model(mp, args.device)
    bad_words_ids = load_clt_bad_words()

    clt_results = []
    for song in songs:
        sid = song["id"]
        artist = song["metadata"]["artist"]
        src_syl = [count_syllables(line, song["source_lang"]) for line in song["source_lines"]]
        print(f"{sid} ({artist}): src_syl={src_syl}", file=sys.stderr)

        t0 = time.time()
        translations = clt_translate(
            model,
            tokenizer,
            song["source_lines"],
            src_syl,
            bad_words_ids=bad_words_ids,
            device=args.device,
        )
        elapsed = time.time() - t0

        r = evaluate_song(song, translations)
        r["time_seconds"] = round(elapsed, 2)
        clt_results.append(r)
        print(
            f"  SER={r['ser']:.4f} SCRE={r['scre']:.4f} ARI={r['ari']:.4f} "
            f"match={r['match']} time={elapsed:.1f}s",
            file=sys.stderr,
        )

    save_results(clt_results, "clt-baseline", songs, args.seed, clt_dir)

    # Comparison report
    def avg(vals):
        return sum(vals) / len(vals) if vals else 0.0

    cc_ser = avg([r["ser"] for r in cc_results])
    cc_scre = avg([r["scre"] for r in cc_results])
    cc_ari = avg([r["ari"] for r in cc_results])
    cc_time = avg([r["time_seconds"] for r in cc_results])
    clt_ser = avg([r["ser"] for r in clt_results])
    clt_scre = avg([r["scre"] for r in clt_results])
    clt_ari = avg([r["ari"] for r in clt_results])
    clt_time = avg([r["time_seconds"] for r in clt_results])

    def winner(cc, clt, lower_better=True):
        if lower_better:
            return "CC+Skills" if cc < clt else ("CLT" if clt < cc else "Tie")
        return "CC+Skills" if cc > clt else ("CLT" if clt > cc else "Tie")

    lines = []
    lines.append("# Benchmark Comparison Report")
    lines.append("")
    lines.append(f"- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"- **Songs**: {len(songs)}")
    lines.append(f"- **Seed**: {args.seed}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | CC+Skills | CLT | Winner |")
    lines.append("|--------|-----------|-----|--------|")
    w = winner
    lines.append(f"| **SER** | {cc_ser:.4f} | {clt_ser:.4f} | {w(cc_ser, clt_ser)} |")
    lines.append(f"| **SCRE** | {cc_scre:.4f} | {clt_scre:.4f} | {w(cc_scre, clt_scre)} |")
    lines.append(f"| **ARI** | {cc_ari:.4f} | {clt_ari:.4f} | {w(cc_ari, clt_ari, False)} |")
    lines.append(f"| **Time (s)** | {cc_time:.2f} | {clt_time:.2f} | {w(cc_time, clt_time)} |")
    lines.append("")

    if cc_skill_counts:
        lines.append("## CC+Skills Skill Usage")
        lines.append("")
        lines.append("| Skill | Calls |")
        lines.append("|-------|-------|")
        for skill, count in sorted(cc_skill_counts.items()):
            lines.append(f"| {skill} | {count} |")
        lines.append(f"| **Total** | **{sum(cc_skill_counts.values())}** |")
        lines.append("")

    lines.append("## Per-Song Results")
    lines.append("")
    lines.append("| Song | Artist | CC Match | CC SER | CLT Match | CLT SER |")
    lines.append("|------|--------|----------|--------|-----------|---------|")
    for cc_r, clt_r, song in zip(cc_results, clt_results, songs):
        lines.append(
            f"| {song['id']} | {song['metadata']['artist']} | "
            f"{cc_r['match']} | {cc_r['ser']:.2f} | "
            f"{clt_r['match']} | {clt_r['ser']:.2f} |"
        )
    lines.append("")
    lines.append("## Sample Translations")
    lines.append("")
    for i, song in enumerate(songs[:3]):
        lines.append(f"### {song['id']} ({song['metadata']['artist']})")
        lines.append("")
        lines.append("**Source:**")
        lines.append("```")
        for j, src in enumerate(song["source_lines"], 1):
            lines.append(f"{j}. {src}")
        lines.append("```")
        lines.append("")
        cr = cc_results[i]
        lines.append(f"**CC+Skills** (match {cr['match']}):")
        lines.append("```")
        for j, t in enumerate(cr["translations"], 1):
            lines.append(f"{j}. {t} [{cr['tgt_syl'][j - 1]}]")
        lines.append("```")
        lines.append("")
        br = clt_results[i]
        lines.append(f"**CLT Baseline** (match {br['match']}):")
        lines.append("```")
        for j, t in enumerate(br["translations"], 1):
            lines.append(f"{j}. {t} [{br['tgt_syl'][j - 1]}]")
        lines.append("```")
        lines.append("")

    report_path = outdir / "report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nSaved comparison {report_path}", file=sys.stderr)

    # Combined results.json
    output = {
        "date": datetime.now().isoformat(),
        "n": len(songs),
        "seed": args.seed,
        "methods": {
            "cc_skills": {
                "avg_ser": round(cc_ser, 4),
                "avg_scre": round(cc_scre, 4),
                "avg_ari": round(cc_ari, 4),
                "avg_time": round(cc_time, 2),
            },
            "clt_baseline": {
                "avg_ser": round(clt_ser, 4),
                "avg_scre": round(clt_scre, 4),
                "avg_ari": round(clt_ari, 4),
                "avg_time": round(clt_time, 2),
            },
        },
    }
    if cc_skill_counts:
        output["cc_skill_counts"] = cc_skill_counts
    results_path = outdir / "results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Saved {results_path}", file=sys.stderr)

    print(json.dumps(output["methods"], indent=2))


if __name__ == "__main__":
    main()
