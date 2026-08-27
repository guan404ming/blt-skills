#!/usr/bin/env python3
"""Analyze blind A/B human-evaluation responses for singability.

Reads per-rater CSVs from data/human_eval/responses/*.csv plus the answer key
(human_eval_key.csv), decodes the A/B labels back to conditions (vanilla vs
p1p2), and reports:
  - preference rate for Phase 1+2 (% of rater x case judgments) with a
    bootstrap CI and a two-sided sign test,
  - mean MOS per condition for singability and naturalness, with the paired
    difference and a bootstrap CI,
  - inter-rater agreement via Krippendorff's alpha (nominal for the forced
    choice, ordinal for the MOS scales).

Usage:
    uv run scripts/analyze_human_eval.py
"""

from __future__ import annotations

import argparse
import csv
import glob
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean

REPO = Path(__file__).resolve().parent.parent
KEY = REPO / "data/human_eval/human_eval_key.csv"
RESPONSES = REPO / "data/human_eval/responses"


def bootstrap_ci(values, *, n_iter=5000, alpha=0.05, seed=0):
    """Percentile bootstrap CI for the mean of a sample."""
    if not values:
        return (0.0, 0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_iter):
        means.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    lo = means[int(alpha / 2 * n_iter)]
    hi = means[int((1 - alpha / 2) * n_iter)]
    return (mean(values), lo, hi)


def sign_test_p(wins, losses):
    """Two-sided sign test p-value (ties excluded), exact binomial at p=0.5."""
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    tail = sum(math.comb(n, j) for j in range(0, k + 1)) / (2**n)
    return min(1.0, 2 * tail)


def krippendorff_alpha(unit_values, level="nominal"):
    """Krippendorff's alpha from {unit: [values]} (values are comparable scalars).

    Units with fewer than two values are ignored. Supports 'nominal' and
    'ordinal' difference functions.
    """
    units = [vs for vs in unit_values.values() if len(vs) >= 2]
    if not units:
        return float("nan")

    # coincidence matrix over the set of observed values
    coinc = defaultdict(float)
    for vs in units:
        m = len(vs)
        for a in range(m):
            for b in range(m):
                if a != b:
                    coinc[(vs[a], vs[b])] += 1.0 / (m - 1)

    vals = sorted({v for vs in units for v in vs})
    nc = {c: sum(coinc[(c, k)] for k in vals) for c in vals}
    n = sum(nc.values())
    if n <= 1:
        return float("nan")

    def delta(c, k):
        if level == "nominal":
            return 0.0 if c == k else 1.0
        # ordinal: squared interval of accumulated marginals between c and k
        lo, hi = sorted((c, k))
        between = [g for g in vals if lo <= g <= hi]
        s = sum(nc[g] for g in between) - (nc[lo] + nc[hi]) / 2.0
        return s * s

    do = sum(coinc[(c, k)] * delta(c, k) for c in vals for k in vals)
    de = sum(nc[c] * nc[k] * delta(c, k) for c in vals for k in vals) / (n - 1)
    if de == 0:
        return float("nan")
    return 1.0 - do / de


def load_key():
    with open(KEY, encoding="utf-8") as f:
        return {r["case"]: r for r in csv.DictReader(f)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--responses", default=str(RESPONSES))
    args = ap.parse_args()

    key = load_key()
    files = sorted(glob.glob(str(Path(args.responses) / "*.csv")))
    if not files:
        raise SystemExit(f"No response CSVs found in {args.responses}")

    # decoded judgments
    prefs = []  # 1 if p1p2 preferred, else 0
    pref_by_case = defaultdict(list)  # case -> [chosen condition] for alpha
    mos = {"singability": defaultdict(list), "naturalness": defaultdict(list)}
    mos_by_case = {
        "singability": defaultdict(list),
        "naturalness": defaultdict(list),
    }  # (metric) -> "case::condition" -> [scores]
    raters = []

    for fp in files:
        with open(fp, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        rater = rows[0]["rater"] if rows else Path(fp).stem
        raters.append(rater)
        for r in rows:
            case = r["case"]
            if case not in key:
                continue
            cond_A = key[case]["version_A"]
            cond_B = key[case]["version_B"]
            chosen = cond_A if r["more_singable_A_or_B"] == "A" else cond_B
            prefs.append(1 if chosen == "p1p2" else 0)
            pref_by_case[case].append(chosen)
            for metric, (ca, cb) in {
                "singability": ("MOS_A_singability_1to5", "MOS_B_singability_1to5"),
                "naturalness": ("MOS_A_naturalness_1to5", "MOS_B_naturalness_1to5"),
            }.items():
                sa, sb = int(r[ca]), int(r[cb])
                mos[metric][cond_A].append(sa)
                mos[metric][cond_B].append(sb)
                mos_by_case[metric][f"{case}::{cond_A}"].append(sa)
                mos_by_case[metric][f"{case}::{cond_B}"].append(sb)

    n_judg = len(prefs)
    print(f"Raters: {len(raters)} ({', '.join(raters)})")
    print(f"Cases: {len(pref_by_case)}  |  total judgments: {n_judg}\n")

    # 1. preference
    wins = sum(prefs)
    rate, lo, hi = bootstrap_ci([float(p) for p in prefs])
    p = sign_test_p(wins, n_judg - wins)
    a_pref = krippendorff_alpha(pref_by_case, level="nominal")
    print("== Preference (Phase 1+2 vs Vanilla) ==")
    print(
        f"  P1+2 preferred: {wins}/{n_judg} = {rate * 100:.0f}%  "
        f"(95% CI {lo * 100:.0f}-{hi * 100:.0f}%)"
    )
    print(f"  sign test p = {p:.4g}")
    print(f"  Krippendorff alpha (nominal): {a_pref:.2f}\n")

    # 2. MOS
    for metric in ("singability", "naturalness"):
        van = mos[metric]["vanilla"]
        p12 = mos[metric]["p1p2"]
        mv, lv, hv = bootstrap_ci([float(x) for x in van])
        mp, lp, hp = bootstrap_ci([float(x) for x in p12])
        # paired diff per (rater x case)
        diff = [a - b for a, b in zip(p12, van)]
        md, ld, hd = bootstrap_ci([float(x) for x in diff])
        a_mos = krippendorff_alpha(mos_by_case[metric], level="ordinal")
        print(f"== MOS {metric} ==")
        print(f"  Vanilla : {mv:.2f}  (95% CI {lv:.2f}-{hv:.2f})")
        print(f"  P1+2    : {mp:.2f}  (95% CI {lp:.2f}-{hp:.2f})")
        print(f"  diff P1+2 - Vanilla: {md:+.2f}  (95% CI {ld:+.2f}-{hd:+.2f})")
        print(f"  Krippendorff alpha (ordinal): {a_mos:.2f}\n")


if __name__ == "__main__":
    main()
