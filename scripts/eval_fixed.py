#!/usr/bin/env python3
"""Re-evaluate run outputs with the current metrics (SER/SCRE/ARI/CCVO) and rhymed/unrhymed splits.

Usage:
    uv run scripts/eval_fixed.py --songs <run>/test_songs.json --out data/bench/final_zh_opus.json \
        vanilla=data/bench/vanilla_opus_fixed/<run>/partial agent=data/bench/agent_opus/<run>/partial
"""

import argparse
import glob
import json
import statistics as st
from pathlib import Path

from bench_common import evaluate_song

from blt_skills.ccvo import ccvo_distance


def load(spec):
    p = Path(spec)
    if p.suffix == ".json":
        return {k: {"translations": v} for k, v in json.load(open(p, encoding="utf-8")).items()}
    return {json.load(open(f))["id"]: json.load(open(f)) for f in glob.glob(str(p / "*.json"))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("systems", nargs="+", help="name=partial_dir_or_json")
    ap.add_argument("--songs", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    songs = {s["id"]: s for s in json.load(open(args.songs, encoding="utf-8"))}
    out = {}
    for spec in args.systems:
        name, path = spec.split("=", 1)
        meta = load(path)
        ids = sorted(i for i in meta if i in songs)
        ne = [i for i in ids if any(t.strip() for t in meta[i]["translations"])]
        ev = {i: evaluate_song(songs[i], meta[i]["translations"]) for i in ids}
        cc = {
            i: ccvo_distance(
                songs[i]["source_lines"],
                meta[i]["translations"],
                songs[i]["source_lang"],
                songs[i]["target_lang"],
            )
            for i in ne
        }
        rh = [i for i in ne if len(set(ev[i]["src_rhyme"])) < len(ev[i]["src_rhyme"])]
        nr = [i for i in ne if i not in rh]

        def m(ids_, k):
            return round(st.mean(ev[i][k] for i in ids_), 4) if ids_ else None

        rec = dict(
            n=len(ids),
            n_ok=len(ne),
            ser_all=m(ids, "ser"),
            scre_all=m(ids, "scre"),
            ari_all=m(ids, "ari"),
            ser=m(ne, "ser"),
            scre=m(ne, "scre"),
            ari=m(ne, "ari"),
            n_rhymed=len(rh),
            ari_rhymed=m(rh, "ari"),
            ari_unrhymed=m(nr, "ari"),
            ccvo=round(st.mean(cc.values()), 4) if cc else None,
            time=round(st.median(meta[i]["time_seconds"] for i in ne), 1)
            if ne and "time_seconds" in meta[ne[0]]
            else None,
            per_song={
                i: dict(ser=ev[i]["ser"], scre=ev[i]["scre"], ari=ev[i]["ari"], ccvo=cc.get(i))
                for i in ids
            },
        )
        out[name] = rec
        print(name, {k: v for k, v in rec.items() if k != "per_song"}, flush=True)
    json.dump(out, open(args.out, "w"), indent=1)


if __name__ == "__main__":
    main()
