#!/usr/bin/env python3
"""
Single-prompt baseline: one plain translation call per item, no skills, no constraints.

Usage:
    uv run scripts/run_vanilla.py -n 100 --model haiku --workers 4
    uv run scripts/run_vanilla.py -n 30 --model haiku --target-lang ja
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import bench_common
from bench_common import evaluate_song, load_songs, make_parser, save_results, translate_vanilla

_print_lock = Lock()


def log(msg):
    with _print_lock:
        print(msg, file=sys.stderr, flush=True)


def process_song(song, args, partial_dir):
    sid = song["id"]
    partial_path = partial_dir / f"{sid}.json"
    if args.resume and partial_path.exists():
        with open(partial_path, encoding="utf-8") as f:
            return json.load(f)

    n = len(song["source_lines"])
    log(f"[start ] {sid}")
    stats = {}
    t0 = time.time()
    translations = translate_vanilla(
        song["source_lines"], song["source_lang"], song["target_lang"], args.model, stats
    )
    elapsed = time.time() - t0
    if translations is None:
        log(f"[fail  ] {sid}")
        translations = [""] * n
    translations = (list(translations) + [""] * n)[:n]

    r = evaluate_song(song, translations)
    r["time_seconds"] = round(elapsed, 2)
    r["model"] = args.model or "default"
    r["llm_calls"] = stats.get("phase0_calls", 0)
    r["failed"] = not any(t.strip() for t in translations)
    with open(partial_path, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
    log(
        f"[done  ] {sid} SER={r['ser']:.3f} ARI={r['ari']:.3f} match={r['match']} time={elapsed:.0f}s"
    )
    return r


def main():
    parser = make_parser("Single-prompt translation baseline")
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--effort", choices=("low", "medium", "high", "xhigh", "max"), default="medium"
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    args.bench_method = "vanilla"
    bench_common.CLAUDE_EFFORT = args.effort

    songs, outdir = load_songs(args)
    partial_dir = outdir / "partial"
    partial_dir.mkdir(parents=True, exist_ok=True)
    log(
        f"vanilla model={args.model or 'default'} effort={args.effort} workers={args.workers} n={len(songs)}"
    )

    results_by_id = {}
    if args.workers <= 1:
        for song in songs:
            r = process_song(song, args, partial_dir)
            results_by_id[r["id"]] = r
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(process_song, s, args, partial_dir): s for s in songs}
            for fut in as_completed(futs):
                try:
                    r = fut.result()
                except Exception as exc:  # noqa: BLE001
                    log(f"[error ] {futs[fut]['id']}: {exc}")
                    continue
                results_by_id[r["id"]] = r

    results = [results_by_id[s["id"]] for s in songs if s["id"] in results_by_id]
    save_results(results, "vanilla", songs, args.seed, outdir)


if __name__ == "__main__":
    main()
