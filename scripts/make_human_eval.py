#!/usr/bin/env python3
"""Build a blind A/B human-evaluation sheet for singability.

Pairs Vanilla vs Phase 1+2 (Opus, en->zh) translations for a sample of cases,
randomizes left/right per case, and writes two files:
  - human_eval_sheet.csv : what raters see (no condition labels)
  - human_eval_key.csv   : A/B -> condition mapping + case ids (kept separate)

Usage:
    uv run scripts/make_human_eval.py -n 25 --seed 7
"""

import argparse
import csv
import glob
import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VANILLA = "data/bench/ou_opus_vanilla_v2"
P1P2 = "data/bench/ou_opus_p1p2_v2"


def load_run(pat):
    run_dir = sorted(glob.glob(str(REPO / pat / "*")))[0]
    songs = {s["id"]: s for s in json.load(open(f"{run_dir}/test_songs.json"))}
    trans = {}
    for p in glob.glob(f"{run_dir}/partial/*.json"):
        r = json.load(open(p))
        trans[r["id"]] = r.get("translations", [])
    return songs, trans


def nonempty(lines):
    return lines and all(str(x).strip() for x in lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=25, help="number of cases to sample")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("-o", "--out-dir", default="data/human_eval")
    args = ap.parse_args()

    songs, van = load_run(VANILLA)
    _, p12 = load_run(P1P2)

    # cases where both conditions produced full non-empty translations
    ids = [
        sid for sid in songs
        if nonempty(van.get(sid)) and nonempty(p12.get(sid))
    ]
    rng = random.Random(args.seed)
    rng.shuffle(ids)
    ids = sorted(ids[: args.n])

    out = REPO / args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    sheet_rows, key_rows = [], []
    for sid in ids:
        src = songs[sid]["source_lines"]
        # randomize which side is which
        if rng.random() < 0.5:
            a_cond, b_cond = "vanilla", "p1p2"
            a_lines, b_lines = van[sid], p12[sid]
        else:
            a_cond, b_cond = "p1p2", "vanilla"
            a_lines, b_lines = p12[sid], van[sid]
        sheet_rows.append({
            "case": sid,
            "english_source": " / ".join(src),
            "version_A": " / ".join(a_lines),
            "version_B": " / ".join(b_lines),
            "more_singable_A_or_B": "",
            "MOS_A_singability_1to5": "",
            "MOS_B_singability_1to5": "",
            "MOS_A_naturalness_1to5": "",
            "MOS_B_naturalness_1to5": "",
        })
        key_rows.append({"case": sid, "version_A": a_cond, "version_B": b_cond})

    sheet_path = out / "human_eval_sheet.csv"
    with open(sheet_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(sheet_rows[0].keys()))
        w.writeheader()
        w.writerows(sheet_rows)
    key_path = out / "human_eval_key.csv"
    with open(key_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["case", "version_A", "version_B"])
        w.writeheader()
        w.writerows(key_rows)

    print(f"Wrote {len(sheet_rows)} cases to {sheet_path}")
    print(f"Answer key (keep separate from raters): {key_path}")
    print("\nRater instructions to include:")
    print("- Judge each pair as a singable Chinese version of the English source,")
    print("  imagining both sung to the original melody (same number of notes).")
    print("- Pick the more singable version (A or B), then rate each 1-5 on")
    print("  singability (fits the melody) and naturalness (reads as fluent Chinese).")


if __name__ == "__main__":
    main()
