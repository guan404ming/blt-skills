#!/usr/bin/env python3
"""Build a blind A/B human-evaluation sheet for singability.

Pairs Vanilla vs BLT (Opus 5, en->zh) translations for a sample of cases whose
source windows do not overlap, randomizes left/right per case, and writes two files:
  - human_eval_sheet.csv : what raters see (no condition labels)
  - human_eval_key.csv   : A/B -> condition mapping + case ids (kept separate)

Usage:
    uv run scripts/make_human_eval.py -n 10 --seed 7
    uv run scripts/make_human_eval.py --manifest data/human_eval/human_eval_key.csv   # reproduce the published sheet
"""

import argparse
import csv
import glob
import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VANILLA = "data/bench/vanilla_opus"
BLT = "data/bench/agent_opus"


def to_traditional(lines):
    try:
        from opencc import OpenCC
    except ImportError:
        return lines
    cc = OpenCC("s2twp")
    return [cc.convert(x) for x in lines]


def load_run(pat):
    run_dir = sorted(glob.glob(str(REPO / pat / "*")))[0]
    songs = {s["id"]: s for s in json.load(open(f"{run_dir}/test_songs.json"))}
    trans = {}
    for p in glob.glob(f"{run_dir}/partial/*.json"):
        r = json.load(open(p))
        if not r.get("failed"):
            trans[r["id"]] = r.get("translations", [])
    return songs, trans


REFUSAL_MARKERS = ("略過", "版權", "copyright", "[", "]")


def nonempty(lines):
    return bool(lines) and all(
        str(x).strip() and not any(m in str(x) for m in REFUSAL_MARKERS) for x in lines
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=25, help="number of cases to sample")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("-o", "--out-dir", default="data/human_eval")
    ap.add_argument(
        "--manifest",
        default=None,
        help="existing human_eval_key.csv to reproduce its items and A/B sides",
    )
    args = ap.parse_args()

    songs, van = load_run(VANILLA)
    _, blt = load_run(BLT)

    ids = [sid for sid in songs if nonempty(van.get(sid)) and nonempty(blt.get(sid))]
    rng = random.Random(args.seed)
    rng.shuffle(ids)
    chosen, used = [], set()
    for sid in ids:
        lines = set(songs[sid]["source_lines"])
        if lines & used:
            continue
        chosen.append(sid)
        used |= lines
        if len(chosen) == args.n:
            break
    ids = sorted(chosen)
    manifest = {}
    if args.manifest:
        with open(args.manifest, encoding="utf-8") as f:
            manifest = {r["case"]: r for r in csv.DictReader(f)}
        ids = sorted(manifest)

    out = REPO / args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    sheet_rows, key_rows = [], []
    for sid in ids:
        src = songs[sid]["source_lines"]
        # randomize which side is which
        side_a = (
            manifest[sid]["version_A"] if manifest else ("vanilla" if rng.random() < 0.5 else "blt")
        )
        if side_a == "vanilla":
            a_cond, b_cond = "vanilla", "blt"
            a_lines, b_lines = to_traditional(van[sid]), to_traditional(blt[sid])
        else:
            a_cond, b_cond = "blt", "vanilla"
            a_lines, b_lines = to_traditional(blt[sid]), to_traditional(van[sid])
        sheet_rows.append(
            {
                "case": sid,
                "english_source": " / ".join(src),
                "version_A": " / ".join(a_lines),
                "version_B": " / ".join(b_lines),
                "more_singable_A_or_B": "",
                "MOS_A_singability_1to5": "",
                "MOS_B_singability_1to5": "",
                "MOS_A_naturalness_1to5": "",
                "MOS_B_naturalness_1to5": "",
                "MOS_A_meaning_1to5": "",
                "MOS_B_meaning_1to5": "",
            }
        )
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
    print("  singability (fits the melody), naturalness (fluent Chinese), and")
    print("  meaning (keeps the sense and feeling of the English).")


if __name__ == "__main__":
    main()
