#!/usr/bin/env python3
"""
Benchmark Claude Code + Skills lyrics translation (multi-phase, batch-capable).

Usage:
    uv run scripts/run_cc.py -n 5
    uv run scripts/run_cc.py -n 100 --model opus --phases 3 --workers 4
    uv run scripts/run_cc.py -n 100 --resume -o data/bench/20260510_cc_p3
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from bench_common import (
    evaluate_song,
    extract_constraints,
    get_skill_counts,
    load_songs,
    make_parser,
    reset_skill_counter,
    save_results,
    translate_with_claude_phases,
)
from collections import Counter


_print_lock = Lock()


def log(msg):
    with _print_lock:
        print(msg, file=sys.stderr, flush=True)


def process_song(song, args, partial_dir):
    sid = song["id"]
    artist = song["metadata"].get("artist", "?")
    partial_path = partial_dir / f"{sid}.json"

    if args.resume and partial_path.exists():
        with open(partial_path, encoding="utf-8") as f:
            r = json.load(f)
        log(f"[resume] {sid} ({artist}) cached")
        return r

    constraints = extract_constraints(song["source_lines"], song["source_lang"])
    log(f"[start ] {sid} ({artist}) src_syl={constraints['syllables']}")

    pre_counts = Counter(get_skill_counts())
    metrics: dict = {}

    t0 = time.time()
    translations = translate_with_claude_phases(
        song["source_lines"],
        song["source_lang"],
        song["target_lang"],
        constraints,
        model=args.model,
        phases=args.phases,
        max_iter_p2=args.max_iter_p2,
        p3_threshold=args.p3_threshold,
        metrics_out=metrics,
        ablation=args.ablation,
    )
    elapsed = time.time() - t0

    if translations is None:
        log(f"[fail  ] {sid}")
        translations = [""] * len(song["source_lines"])

    r = evaluate_song(song, translations)
    r["time_seconds"] = round(elapsed, 2)
    r["phases"] = args.phases
    r["model"] = args.model or "default"

    post_counts = Counter(get_skill_counts())
    r["skill_calls"] = dict(post_counts - pre_counts)
    r["llm_calls"] = sum(
        v for k, v in metrics.items() if k.endswith("_calls")
    )
    r["phase_metrics"] = {k: round(v, 3) if isinstance(v, float) else v
                          for k, v in metrics.items()}

    with open(partial_path, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)

    log(
        f"[done  ] {sid} SER={r['ser']:.4f} SCRE={r['scre']:.4f} "
        f"ARI={r['ari']:.4f} match={r['match']} llm={r['llm_calls']} "
        f"skill={sum(r['skill_calls'].values())} time={elapsed:.1f}s"
    )
    return r


def main():
    parser = make_parser("Benchmark Claude Code + Skills translation (multi-phase)")
    parser.add_argument(
        "--model", default=None, help="Claude model (e.g. sonnet, opus, haiku)"
    )
    parser.add_argument(
        "--phases",
        type=int,
        default=3,
        choices=(0, 1, 2, 3),
        help="0=vanilla (no skills/constraints), 1=Phase 1, 2=1+2, 3=1+2+3 (default 3)",
    )
    parser.add_argument(
        "--workers", type=int, default=1, help="Parallel song workers (default 1)"
    )
    parser.add_argument(
        "--max-iter-p2",
        type=int,
        default=10,
        help="Max Phase 2 refinement iterations per line (default 10)",
    )
    parser.add_argument(
        "--p3-threshold",
        type=float,
        default=0.8,
        help="Phase 3 acceptance threshold on pattern similarity (default 0.8)",
    )
    parser.add_argument(
        "--effort",
        choices=("low", "medium", "high", "xhigh", "max"),
        default=None,
        help="Claude reasoning effort level passed to `claude --effort`",
    )
    parser.add_argument(
        "--ablation",
        choices=("none", "sc-only", "prompt-verify"),
        default="none",
        help="Ablation condition: 'sc-only' (Phase 1 exposes only syllable counts, "
        "no rhyme/pattern) or 'prompt-verify' (multi-round in-prompt self-verification, "
        "no external counter). Default: none (full pipeline).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from per-song partial files in --output-dir/partial/",
    )
    args = parser.parse_args()
    args.bench_method = f"cc_p{args.phases}"

    # Apply --effort globally for this run; bench_common.call_claude reads it.
    import bench_common
    bench_common.CLAUDE_EFFORT = args.effort

    if args.resume:
        # When resuming, point load_songs at the existing run directory rather than
        # creating a fresh timestamped one.
        existing = Path(args.output_dir)
        if not existing.exists() or not (existing / "test_songs.json").exists():
            print(
                f"--resume requires an existing run at {existing}/ "
                "with test_songs.json; falling back to a fresh sample.",
                file=sys.stderr,
            )
            songs, outdir = load_songs(args)
        else:
            with open(existing / "test_songs.json", encoding="utf-8") as f:
                songs = json.load(f)
            outdir = existing
            print(f"Resuming from {outdir} ({len(songs)} songs)", file=sys.stderr)
    else:
        songs, outdir = load_songs(args)

    partial_dir = outdir / "partial"
    partial_dir.mkdir(parents=True, exist_ok=True)

    reset_skill_counter()

    log(
        f"phases={args.phases} workers={args.workers} model={args.model or 'default'} "
        f"effort={args.effort or 'default'} max_iter_p2={args.max_iter_p2} "
        f"p3_threshold={args.p3_threshold}"
    )

    results_by_id: dict[str, dict] = {}

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
                except Exception as exc:  # noqa: BLE001 - log and continue
                    sid = futs[fut]["id"]
                    log(f"[error ] {sid}: {exc}")
                    continue
                results_by_id[r["id"]] = r

    # Preserve original song order in the final results.json.
    results = [results_by_id[s["id"]] for s in songs if s["id"] in results_by_id]

    save_results(
        results,
        f"cc-skills-p{args.phases}",
        songs,
        args.seed,
        outdir,
        skill_counts=get_skill_counts(),
    )


if __name__ == "__main__":
    main()
