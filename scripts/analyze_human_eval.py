#!/usr/bin/env python3
"""Analyze blind A/B human-evaluation responses for singability.

Reads per-rater CSVs from data/human_eval/responses/*.csv plus the answer key
(human_eval_key.csv), decodes the A/B labels back to conditions (vanilla vs
blt), and reports:
  - preference rate for BLT over all rater x case judgments and at the case
    level (majority vote, sign test),
  - mean MOS per condition for singability, naturalness, and meaning, with the
    paired difference, a judgment-level bootstrap CI, and a two-way cluster
    bootstrap CI over raters and cases,
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


def cluster_bootstrap_ci(records, stat, *, n_iter=5000, alpha=0.05, seed=0):
    """Two-way cluster bootstrap over raters and cases; records are (rater, case, value)."""
    raters = sorted({r for r, _, _ in records})
    cases = sorted({c for _, c, _ in records})
    rng = random.Random(seed)
    stats = []
    for _ in range(n_iter):
        rc = defaultdict(int)
        for r in rng.choices(raters, k=len(raters)):
            rc[r] += 1
        cc = defaultdict(int)
        for c in rng.choices(cases, k=len(cases)):
            cc[c] += 1
        sample = [v for r, c, v in records for _ in range(rc[r] * cc[c])]
        if sample:
            stats.append(stat(sample))
    stats.sort()
    return stats[int(alpha / 2 * n_iter)], stats[int((1 - alpha / 2) * n_iter)]


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
    metrics = ("singability", "naturalness", "meaning")
    prefs = []
    pref_records = []
    pref_by_case = defaultdict(list)
    mos = {m: defaultdict(list) for m in metrics}
    mos_by_case = {m: defaultdict(list) for m in metrics}
    diff_records = {m: [] for m in metrics}
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
            win = 1 if chosen == "blt" else 0
            prefs.append(win)
            pref_records.append((rater, case, win))
            pref_by_case[case].append(chosen)
            for metric in metrics:
                ca, cb = f"MOS_A_{metric}_1to5", f"MOS_B_{metric}_1to5"
                if ca not in r or not r[ca]:
                    continue
                sa, sb = int(r[ca]), int(r[cb])
                mos[metric][cond_A].append(sa)
                mos[metric][cond_B].append(sb)
                mos_by_case[metric][f"{case}::{cond_A}"].append(sa)
                mos_by_case[metric][f"{case}::{cond_B}"].append(sb)
                blt_score, van_score = (sa, sb) if cond_A == "blt" else (sb, sa)
                diff_records[metric].append((rater, case, blt_score - van_score))

    n_judg = len(prefs)
    print(f"Raters: {len(raters)} ({', '.join(raters)})")
    print(f"Cases: {len(pref_by_case)}  |  total judgments: {n_judg}\n")

    # 1. preference
    wins = sum(prefs)
    rate, lo, hi = bootstrap_ci([float(p) for p in prefs])
    p = sign_test_p(wins, n_judg - wins)
    a_pref = krippendorff_alpha(pref_by_case, level="nominal")
    case_wins = sum(1 for vs in pref_by_case.values() if vs.count("blt") > len(vs) / 2)
    case_losses = sum(1 for vs in pref_by_case.values() if vs.count("blt") < len(vs) / 2)
    clo, chi = cluster_bootstrap_ci(pref_records, mean)
    print("== Preference (BLT vs Vanilla) ==")
    print(
        f"  BLT preferred: {wins}/{n_judg} = {rate * 100:.0f}%  "
        f"(judgment bootstrap 95% CI {lo * 100:.0f}-{hi * 100:.0f}%; "
        f"rater x case cluster bootstrap {clo * 100:.0f}-{chi * 100:.0f}%)"
    )
    print(f"  judgment-level sign test p = {p:.4g}")
    print(
        f"  case-level majority: {case_wins} wins / {case_losses} losses / "
        f"{len(pref_by_case) - case_wins - case_losses} ties, sign test p = "
        f"{sign_test_p(case_wins, case_losses):.3g}"
    )
    print(f"  Krippendorff alpha (nominal): {a_pref:.2f}\n")

    # 2. MOS
    for metric in metrics:
        van = mos[metric]["vanilla"]
        blt = mos[metric]["blt"]
        if not van:
            continue
        mv, lv, hv = bootstrap_ci([float(x) for x in van])
        mp, lp, hp = bootstrap_ci([float(x) for x in blt])
        diff = [float(v) for _, _, v in diff_records[metric]]
        md, ld, hd = bootstrap_ci(diff)
        dlo, dhi = cluster_bootstrap_ci(diff_records[metric], mean)
        a_mos = krippendorff_alpha(mos_by_case[metric], level="ordinal")
        print(f"== MOS {metric} ==")
        print(f"  Vanilla : {mv:.2f}  (95% CI {lv:.2f}-{hv:.2f})")
        print(f"  BLT     : {mp:.2f}  (95% CI {lp:.2f}-{hp:.2f})")
        print(
            f"  diff BLT - Vanilla: {md:+.2f}  (judgment bootstrap 95% CI {ld:+.2f}-{hd:+.2f}; "
            f"cluster bootstrap {dlo:+.2f}-{dhi:+.2f})"
        )
        print(f"  Krippendorff alpha (ordinal): {a_mos:.2f}\n")


if __name__ == "__main__":
    main()
