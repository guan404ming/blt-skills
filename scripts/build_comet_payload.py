#!/usr/bin/env python3
"""Build the payload consumed by modal_comet.py from one or more run directories.

Usage:
    uv run scripts/build_comet_payload.py --out /tmp/comet_payload.json \
        blt=data/bench/agent_haiku/<run>/partial vanilla=data/bench/vanilla_haiku_fixed/<run>/partial \
        clt=data/bench/clt_fork_translations.json
"""

import argparse
import json
from pathlib import Path

from score_semantics import SONGS, gold_lines, load_translations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("systems", nargs="+", help="name=path (partial dir or json)")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    gold = gold_lines()
    refs, srcs, ids = [], [], []
    for s in SONGS:
        st = s["metadata"]["test_start_line"]
        refs.extend(gold[st : st + len(s["source_lines"])])
        srcs.extend(s["source_lines"])
        ids.extend([s["id"]] * len(s["source_lines"]))

    systems = {}
    for spec in args.systems:
        name, path = spec.split("=", 1)
        tr = load_translations(Path(path))
        hyps = []
        for s in SONGS:
            t = tr[s["id"]]
            assert len(t) == len(s["source_lines"]), (name, s["id"])
            hyps.extend(t)
        systems[name] = hyps

    json.dump(
        {"refs": refs, "srcs": srcs, "ids": ids, "systems": systems},
        open(args.out, "w"),
        ensure_ascii=False,
    )
    print("saved", args.out, {k: len(v) for k, v in systems.items()})


if __name__ == "__main__":
    main()
