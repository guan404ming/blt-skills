#!/usr/bin/env python3
"""
Benchmark CLT baseline lyrics translation.

Usage:
    uv run scripts/run_clt.py -n 5
    uv run scripts/run_clt.py -n 3 --model-path /path/to/model
    uv run scripts/run_clt.py -n 10 --device cpu -o data/bench_clt
"""

import sys
import time

from bench_common import (
    clt_translate,
    evaluate_song,
    load_clt_bad_words,
    load_clt_model,
    load_songs,
    make_parser,
    save_results,
)

from blt_skills import count_syllables


def main():
    parser = make_parser("Benchmark CLT baseline translation")
    parser.add_argument(
        "--model-path", default=None, help="CLT model path (default: HuggingFace auto-download)"
    )
    parser.add_argument("--device", default="cuda", help="Device for inference (default: cuda)")
    args = parser.parse_args()
    args.bench_method = "clt"

    songs, outdir = load_songs(args)

    mp = args.model_path or "LongshenOu/lyric-trans-en2zh"
    print(f"Loading CLT model from {mp}...", file=sys.stderr)
    model, tokenizer = load_clt_model(mp, args.device)
    bad_words_ids = load_clt_bad_words()

    results = []
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
        results.append(r)

        print(
            f"  SER={r['ser']:.4f} SCRE={r['scre']:.4f} ARI={r['ari']:.4f} "
            f"match={r['match']} time={elapsed:.1f}s",
            file=sys.stderr,
        )

    save_results(results, "clt-baseline", songs, args.seed, outdir)


if __name__ == "__main__":
    main()
