#!/usr/bin/env python3
"""Rebuild every partial result from its saved trace with the current parser and summarizer.

Usage:
    uv run scripts/reparse_runs.py data/bench/agent_haiku/<run> [more run dirs]
"""

import json
import sys
from pathlib import Path

from bench_common import evaluate_song, parse_translations
from run_agent import classify_failure, summarize


def main():
    for run in sys.argv[1:]:
        run = Path(run)
        songs = {s["id"]: s for s in json.load(open(run / "test_songs.json", encoding="utf-8"))}
        changed = 0
        for part in sorted((run / "partial").glob("*.json")):
            d = json.load(open(part, encoding="utf-8"))
            trace = run / "traces" / f"{d['id']}.jsonl"
            if not trace.exists():
                continue
            events = [json.loads(line) for line in open(trace, encoding="utf-8") if line.strip()]
            summary = summarize(events)
            n = len(songs[d["id"]]["source_lines"])
            translations = (
                parse_translations(summary["final_text"], n) if summary["final_text"] else None
            )
            if translations is None or len(translations) != n:
                translations = [""] * n
            before = (d["translations"], d.get("failed"))
            d.update(evaluate_song(songs[d["id"]], translations))
            d["agent"] = summary
            d["failed"] = not any(t.strip() for t in translations)
            d["failure_reason"] = classify_failure(summary, translations)
            d["error"] = summary["final_text"][:200] if summary["is_error"] else ""
            if before != (d["translations"], d["failed"]):
                changed += 1
            json.dump(d, open(part, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"{run}: {changed} items changed", flush=True)


if __name__ == "__main__":
    main()
