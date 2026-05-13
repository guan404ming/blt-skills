#!/usr/bin/env python3
"""Post-hoc analysis of bench results.json: bootstrap CIs, quintiles, PanPhon-ARI.

Usage:
    uv run scripts/analyze_results.py data/bench/ou_opus/2026*/results.json
    uv run scripts/analyze_results.py --panphon-threshold 0.3 path/to/results.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from statistics import mean

from blt_skills.phonetics import normalize_language_code
from blt_skills.rhyme import extract_rhyme_ending


def bootstrap_ci(values, *, n_iter=2000, alpha=0.05, seed=0):
    """Percentile bootstrap CI for the mean of a sample."""
    if not values:
        return (0.0, 0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_iter):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(alpha / 2 * n_iter)]
    hi = means[int((1 - alpha / 2) * n_iter)]
    return (mean(values), lo, hi)


def per_quintile(results, key):
    """Sort results by ``key`` and return mean of key per quintile (5 bins)."""
    sorted_r = sorted(results, key=lambda r: r[key])
    n = len(sorted_r)
    bins = []
    for i in range(5):
        a = int(i * n / 5)
        b = int((i + 1) * n / 5)
        chunk = sorted_r[a:b]
        if not chunk:
            continue
        bins.append(
            {
                "bin": i + 1,
                "start": a,
                "end": b,
                f"mean_{key}": mean(r[key] for r in chunk),
            }
        )
    return bins


# ---------- PanPhon-distance rhyme scheme ----------


_PANPHON_DIST = None


def _panphon_distance(s1, s2):
    global _PANPHON_DIST
    if _PANPHON_DIST is None:
        import panphon.distance

        _PANPHON_DIST = panphon.distance.Distance()
    if not s1 or not s2:
        return 1.0
    return _PANPHON_DIST.feature_edit_distance(s1, s2)


def panphon_scheme(lines, language, threshold):
    """Build a rhyme scheme by PanPhon feature-edit-distance threshold instead of exact match."""
    language = normalize_language_code(language)
    endings = []
    for ln in lines:
        try:
            e = extract_rhyme_ending(ln, language)
        except Exception:
            e = ""
        endings.append(e)

    labels = []
    reps = []
    next_label = 0
    for e in endings:
        matched = None
        for i, rep in enumerate(reps):
            if e and rep:
                d = _panphon_distance(e, rep)
                if d <= threshold:
                    matched = i
                    break
        if matched is None:
            reps.append(e)
            labels.append(chr(ord("A") + next_label))
            next_label += 1
        else:
            labels.append(chr(ord("A") + matched))
    return "".join(labels)


def calc_ari_from_schemes(src_scheme, tgt_scheme):
    from sklearn.metrics import adjusted_rand_score

    def to_labels(s):
        m, out, n = {}, [], 0
        for c in s:
            if c not in m:
                m[c] = n
                n += 1
            out.append(m[c])
        return out

    if not src_scheme or not tgt_scheme:
        return 0.0
    sl = to_labels(src_scheme)
    tl = to_labels(tgt_scheme)
    if len(sl) != len(tl):
        mx = max(len(sl), len(tl))
        nxt = max(max(sl), max(tl)) + 1
        if len(sl) < mx:
            sl += list(range(nxt, nxt + mx - len(sl)))
        if len(tl) < mx:
            tl += list(range(nxt, nxt + mx - len(tl)))
    return adjusted_rand_score(sl, tl)


def panphon_ari(results, src_lang, tgt_lang, songs, threshold):
    """Recompute ARI using PanPhon-distance scheme construction. Skip rows missing data."""
    aris = []
    by_id = {s["id"]: s for s in songs}
    for r in results:
        song = by_id.get(r["id"])
        if not song:
            continue
        if all(t == "" for t in r["translations"]):
            continue
        try:
            src_scheme = panphon_scheme(song["source_lines"], src_lang, threshold)
            tgt_scheme = panphon_scheme(r["translations"], tgt_lang, threshold)
        except Exception as exc:
            print(f"  panphon error on {r['id']}: {exc}", file=sys.stderr)
            continue
        aris.append(calc_ari_from_schemes(src_scheme, tgt_scheme))
    return aris


# ---------- Skill / phase summaries ----------


def per_case_skills(results):
    counts = {"syllable-counter": [], "rhyme-analyzer": [], "syllable-pattern-analyzer": []}
    llm = []
    for r in results:
        sc = r.get("skill_calls", {})
        for k in counts:
            counts[k].append(sc.get(k, 0))
        llm.append(r.get("llm_calls", 0))
    return {
        "llm_calls_per_case": mean(llm) if llm else 0.0,
        **{f"{k}_per_case": (mean(v) if v else 0.0) for k, v in counts.items()},
    }


def phase_breakdown(results):
    """Aggregate phase_metrics across cases."""
    keys = [
        "phase0_time_s", "phase0_calls",
        "phase1_time_s", "phase1_calls", "phase1_match",
        "phase2_time_s", "phase2_calls", "phase2_match",
        "phase3_time_s", "phase3_calls", "phase3_match",
        "phase3_accepted", "phase3_rejected_syl", "phase3_rejected_sim", "phase3_skipped",
    ]
    out = {}
    for k in keys:
        vals = [r.get("phase_metrics", {}).get(k, 0) for r in results]
        if vals and any(v for v in vals):
            out[k] = sum(vals)
            out[f"{k}_mean"] = mean(vals)
    return out


# ---------- Main ----------


def analyze(results_path, *, panphon_threshold=0.3, n_boot=2000, seed=0):
    with open(results_path, encoding="utf-8") as f:
        data = json.load(f)
    results = data.get("results") or []
    method = data.get("method", "?")
    n = data.get("n", len(results))

    print(f"\n=== {method}  (n={n}, file={results_path}) ===\n")

    # Bootstrap CIs
    print("Metric            mean    [95% CI]")
    for key in ("ser", "scre", "ari"):
        m, lo, hi = bootstrap_ci([r[key] for r in results], n_iter=n_boot, seed=seed)
        print(f"  {key.upper():<14} {m:.4f}  [{lo:.4f}, {hi:.4f}]")

    # Time
    times = [r.get("time_seconds", 0) for r in results]
    print(f"  Time (s)       {mean(times):.2f}  [min {min(times):.1f}, max {max(times):.1f}]")

    # Skill / LLM usage
    print("\nPer-case usage (mean):")
    for k, v in per_case_skills(results).items():
        print(f"  {k:<35} {v:.2f}")

    # Phase-level breakdown
    pb = phase_breakdown(results)
    if pb:
        print("\nPhase totals (sum across cases):")
        for k in sorted(pb):
            if not k.endswith("_mean"):
                print(f"  {k:<28} {pb[k]:.2f}")

    # Quintiles by SCRE
    print("\nPer-quintile mean SCRE (sorted ascending):")
    for b in per_quintile(results, "scre"):
        print(f"  q{b['bin']} ({b['start']}-{b['end']}): {b['mean_scre']:.4f}")

    # PanPhon-ARI variant
    songs_path = Path(results_path).parent / "test_songs.json"
    if songs_path.exists():
        with open(songs_path, encoding="utf-8") as f:
            songs = json.load(f)
        if songs:
            src_lang = songs[0]["source_lang"]
            tgt_lang = songs[0]["target_lang"]
            print(f"\nPanPhon-distance ARI (threshold={panphon_threshold}):")
            aris = panphon_ari(results, src_lang, tgt_lang, songs, panphon_threshold)
            if aris:
                m, lo, hi = bootstrap_ci(aris, n_iter=n_boot, seed=seed)
                print(f"  panphon_ari    {m:.4f}  [{lo:.4f}, {hi:.4f}]   (n={len(aris)})")
            else:
                print("  (no eligible rows)")


def main():
    ap = argparse.ArgumentParser(description="Analyze bench results.json")
    ap.add_argument("paths", nargs="+", help="path(s) to results.json")
    ap.add_argument(
        "--panphon-threshold",
        type=float,
        default=0.3,
        help="PanPhon feature-edit-distance threshold for rhyme grouping (default 0.3)",
    )
    ap.add_argument("--n-boot", type=int, default=2000, help="bootstrap iterations (default 2000)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    for p in args.paths:
        analyze(p, panphon_threshold=args.panphon_threshold, n_boot=args.n_boot, seed=args.seed)


if __name__ == "__main__":
    main()
