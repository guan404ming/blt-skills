#!/usr/bin/env python3
"""Intrinsic check of the syllable counter against CMUdict (English) and pyphen (Spanish).

Usage:
    uv run --with cmudict scripts/validate_counter.py --songs <run>/test_songs.json --spanish <es_run>/partial
"""

import argparse
import glob
import json
import re

import cmudict
import pyphen

from blt_skills import count_syllables


def agreement(pairs):
    n = len(pairs)
    exact = sum(a == b for a, b in pairs)
    within = sum(abs(a - b) <= 1 for a, b in pairs)
    return n, exact / n, within / n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--songs", required=True, help="test_songs.json with English source lines")
    ap.add_argument("--spanish", required=True, help="partial dir of a Spanish run (target lines)")
    args = ap.parse_args()

    cmu = cmudict.dict()
    pairs = []
    for song in json.load(open(args.songs, encoding="utf-8")):
        for line in song["source_lines"]:
            words = re.findall(r"[a-zA-Z']+", line.lower())
            if not words or not all(w in cmu for w in words):
                continue
            ref = sum(sum(ph[-1].isdigit() for ph in cmu[w][0]) for w in words)
            pairs.append((ref, count_syllables(line, "en-us")))
    n, exact, within = agreement(pairs)
    print(f"English vs CMUdict: {n} lines, exact {exact:.1%}, within ±1 {within:.1%}")

    hyph = pyphen.Pyphen(lang="es_ES")
    pairs = []
    for path in glob.glob(f"{args.spanish}/*.json"):
        for line in json.load(open(path, encoding="utf-8"))["translations"]:
            if not line.strip():
                continue
            words = re.findall(r"[a-záéíóúüñ']+", line.lower())
            ref = sum(len(hyph.inserted(w).split("-")) for w in words)
            pairs.append((ref, count_syllables(line, "es")))
    n, exact, within = agreement(pairs)
    print(f"Spanish vs pyphen: {n} lines, exact {exact:.1%}, within ±1 {within:.1%}")


if __name__ == "__main__":
    main()
