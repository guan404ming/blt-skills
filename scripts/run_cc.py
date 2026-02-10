#!/usr/bin/env python3
"""
Benchmark Claude Code + Skills lyrics translation.

Usage:
    uv run scripts/run_cc.py -n 5
    uv run scripts/run_cc.py -n 3 --model sonnet --seed 123
    uv run scripts/run_cc.py -n 10 -o data/bench_cc
"""

import sys
import time

from bench_common import (
    evaluate_song,
    extract_constraints,
    get_skill_counts,
    load_songs,
    make_parser,
    reset_skill_counter,
    save_results,
    translate_with_claude,
)


def main():
    parser = make_parser("Benchmark Claude Code + Skills translation")
    parser.add_argument("--model", default=None, help="Claude model (e.g. sonnet, opus, haiku)")
    args = parser.parse_args()
    args.bench_method = "cc"

    songs, outdir = load_songs(args)
    reset_skill_counter()

    results = []
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
            model=args.model,
        )
        elapsed = time.time() - t0

        if translations is None:
            print("  FAILED", file=sys.stderr)
            translations = [""] * len(song["source_lines"])

        r = evaluate_song(song, translations)
        r["time_seconds"] = round(elapsed, 2)
        results.append(r)

        print(
            f"  SER={r['ser']:.4f} SCRE={r['scre']:.4f} ARI={r['ari']:.4f} "
            f"match={r['match']} time={elapsed:.1f}s",
            file=sys.stderr,
        )

    save_results(results, "cc-skills", songs, args.seed, outdir, skill_counts=get_skill_counts())


if __name__ == "__main__":
    main()
