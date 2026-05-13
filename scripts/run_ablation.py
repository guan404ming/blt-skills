#!/usr/bin/env python3
"""Ablation sweep over a single Claude model.

Runs run_cc.py sequentially across phase / threshold / iter configurations
so the rate limit and CLI process count stay manageable. All configs share
the same dataset / seed so per-case metrics are directly comparable.

Configs:
  Phase ablation:    P0, P1, P1+2, P1+2+3 (default p3_threshold=0.8, max_iter_p2=10)
  Threshold sweep:   P3 with p3_threshold in {0.6, 0.7, 0.9}
  Iter sweep:        P3 with max_iter_p2 in {3, 5, 15}

Usage:
  uv run scripts/run_ablation.py --model haiku -n 50
  uv run scripts/run_ablation.py --model haiku -n 50 --only p3_t0.6 p3_iter3
  uv run scripts/run_ablation.py --model haiku -n 50 --skip p0 p1
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from statistics import mean

# (name, phases, p3_threshold, max_iter_p2)
CONFIGS: list[tuple[str, int, float, int]] = [
    ("p0_vanilla",     0, 0.8, 10),
    ("p1_initial",     1, 0.8, 10),
    ("p1p2",           2, 0.8, 10),
    ("p1p2p3_default", 3, 0.8, 10),
    ("p3_t0.6",        3, 0.6, 10),
    ("p3_t0.7",        3, 0.7, 10),
    ("p3_t0.9",        3, 0.9, 10),
    ("p3_iter3",       3, 0.8, 3),
    ("p3_iter5",       3, 0.8, 5),
    ("p3_iter15",      3, 0.8, 15),
]


def find_existing_run(base: Path) -> Path | None:
    """Return the timestamped run dir under base/ if one exists and has test_songs.json."""
    if not base.exists():
        return None
    for d in sorted(base.iterdir()):
        if d.is_dir() and (d / "test_songs.json").exists():
            return d
    return None


def run_one(name, phases, thr, mi, args, log_dir, base_dir):
    outdir = base_dir / name
    existing = find_existing_run(outdir)
    cmd = [
        "uv", "run", "scripts/run_cc.py",
        "-n", str(args.n),
        "--dataset", "ou",
        "--model", args.model,
        "--phases", str(phases),
        "--workers", str(args.workers),
        "--effort", args.effort,
        "--p3-threshold", str(thr),
        "--max-iter-p2", str(mi),
        "--seed", str(args.seed),
    ]
    if existing is not None:
        cmd += ["--resume", "-o", str(existing)]
        mode = f"resume {existing.name}"
    else:
        outdir.mkdir(parents=True, exist_ok=True)
        cmd += ["-o", str(outdir)]
        mode = "fresh"

    log_path = log_dir / f"{name}.log"
    print(f"\n=== {name}  phases={phases} thr={thr} iter={mi}  [{mode}] ===")
    print(f"  cmd: {' '.join(cmd)}")
    print(f"  log: {log_path}")
    t0 = time.time()
    with open(log_path, "a") as f:
        f.write(f"\n\n=== run start {time.ctime()} ===\n")
        f.flush()
        ret = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
    print(f"  rc={ret.returncode}  elapsed={time.time() - t0:.1f}s")


def summarize(base_dir: Path):
    rows = []
    for name, phases, thr, mi in CONFIGS:
        run = find_existing_run(base_dir / name)
        if run is None or not (run / "results.json").exists():
            rows.append((name, phases, thr, mi, None))
            continue
        data = json.load(open(run / "results.json", encoding="utf-8"))
        results = data.get("results") or []
        if not results:
            rows.append((name, phases, thr, mi, None))
            continue
        rows.append((
            name, phases, thr, mi,
            {
                "n": len(results),
                "ser": mean(r["ser"] for r in results),
                "scre": mean(r["scre"] for r in results),
                "ari": mean(r["ari"] for r in results),
                "time": mean(r.get("time_seconds", 0) for r in results),
                "llm": mean(r.get("llm_calls", 0) for r in results),
            },
        ))

    print("\n" + "=" * 72)
    print(f"{'config':<18} {'ph':>3} {'thr':>5} {'iter':>5} {'n':>4} "
          f"{'SER':>7} {'SCRE':>7} {'ARI':>7} {'time':>7} {'llm':>5}")
    print("-" * 72)
    for name, phases, thr, mi, m in rows:
        if m is None:
            print(f"{name:<18} {phases:>3} {thr:>5} {mi:>5}   --  (no data)")
        else:
            print(f"{name:<18} {phases:>3} {thr:>5} {mi:>5} {m['n']:>4} "
                  f"{m['ser']:>7.4f} {m['scre']:>7.4f} {m['ari']:>7.4f} "
                  f"{m['time']:>7.1f} {m['llm']:>5.1f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, choices=("haiku", "sonnet", "opus"))
    ap.add_argument("-n", type=int, default=50)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--only", nargs="*", default=None,
                    help="run only these config names (default: all)")
    ap.add_argument("--skip", nargs="*", default=[],
                    help="skip these config names")
    ap.add_argument("--summarize-only", action="store_true",
                    help="just print summary table from existing results")
    args = ap.parse_args()

    base_dir = Path("data/bench/ablation") / args.model
    log_dir = Path("data/bench/logs/ablation") / args.model
    base_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    if args.summarize_only:
        summarize(base_dir)
        return

    selected = [c for c in CONFIGS
                if (args.only is None or c[0] in args.only)
                and c[0] not in args.skip]
    print(f"Running {len(selected)} configs on {args.model} (n={args.n}, seed={args.seed})")
    for cfg in selected:
        try:
            run_one(*cfg, args=args, log_dir=log_dir, base_dir=base_dir)
        except KeyboardInterrupt:
            print("\n[interrupt] aborting ablation sweep", file=sys.stderr)
            break

    summarize(base_dir)


if __name__ == "__main__":
    main()
