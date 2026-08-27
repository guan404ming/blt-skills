#!/usr/bin/env python3
"""Gold references and translation loaders shared by build_comet_payload.py."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "data" / "bench"

SONGS = json.load(open(next(BENCH.glob("agent_haiku/*_agent/test_songs.json"))))


def gold_lines():
    base = ROOT / "data" / "lyric-trans" / "datasets" / "data_parallel"
    src = (base / "test.source").read_text(encoding="utf-8").splitlines()
    tgt = (base / "test.target").read_text(encoding="utf-8").splitlines()
    return [t.strip()[::-1] for s, t in zip(src, tgt) if s.strip()]


def load_translations(spec):
    if spec.suffix == ".json":
        return json.load(open(spec))
    out = {}
    for f in sorted(spec.glob("ou_*.json")):
        d = json.load(open(f))
        out[d["id"]] = d["translations"]
    return out
