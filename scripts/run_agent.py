#!/usr/bin/env python3
"""
Benchmark agent-invoked Skills: the LLM discovers and runs the skill scripts itself.

Usage:
    uv run scripts/run_agent.py -n 3 --model haiku
    uv run scripts/run_agent.py -n 100 --model haiku --workers 4 --resume -o data/bench/agent_haiku/<run>
"""

import json
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from bench_common import evaluate_song, load_songs, make_parser, parse_translations, save_results

REPO = Path(__file__).resolve().parent.parent
ALLOWED_TOOLS = "Skill,Read,Bash(python skills/*),Bash(uv run *)"

_print_lock = Lock()


def log(msg):
    with _print_lock:
        print(msg, file=sys.stderr, flush=True)


VANILLA_TOOLS = "Bash,Agent,Task,Skill,Read,Glob,Grep,Edit,Write,WebSearch,WebFetch,ToolSearch,Monitor,NotebookEdit"


def build_prompt(song, skill):
    src = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(song["source_lines"]))
    if skill == "none":
        return (
            f"Translate the following {len(song['source_lines'])} song lyric lines "
            f"from {song['source_lang']} to {song['target_lang']}.\n\n"
            f"Source lines:\n{src}\n\n"
            f"Output exactly {len(song['source_lines'])} translated lines, numbered 1-{len(song['source_lines'])}. "
            "No explanations, no annotations."
        )
    return (
        f"Use the {skill} skill to translate these {len(song['source_lines'])} lines "
        f"from {song['source_lang']} to {song['target_lang']}.\n\n"
        f"Source lines:\n{src}\n\n"
        "Follow the skill workflow exactly and run its scripts for every count. "
        "Your final message must contain only the numbered translated lines."
    )


def run_claude(prompt, model, effort, timeout, allowed_tools, disallowed_tools):
    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--allowedTools",
        allowed_tools,
    ]
    if disallowed_tools:
        cmd += ["--disallowedTools", disallowed_tools]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--effort", effort]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=REPO)
    events = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events, proc.stderr


def summarize(events):
    tools = Counter()
    scripts = Counter()
    skills = Counter()
    turns = 0
    for ev in events:
        if ev.get("type") != "assistant":
            continue
        turns += 1
        for block in ev.get("message", {}).get("content", []):
            if block.get("type") != "tool_use":
                continue
            name = block.get("name", "?")
            tools[name] += 1
            inp = block.get("input", {})
            if name == "Skill":
                skills[inp.get("skill") or inp.get("name") or "?"] += 1
            elif name == "Bash":
                cmd = inp.get("command", "")
                for part in cmd.split("&&"):
                    part = part.strip()
                    if "skills/" in part:
                        tail = part.split("skills/", 1)[1].split()
                        if tail:
                            scripts[tail[0].split("/")[0]] += 1
    result = next((ev for ev in events if ev.get("type") == "result"), {})
    model_id = next(
        (ev["message"].get("model") for ev in events if ev.get("type") == "assistant"), None
    )
    return {
        "model_id": model_id,
        "assistant_turns": turns,
        "tool_calls": dict(tools),
        "skill_loads": dict(skills),
        "script_calls": dict(scripts),
        "num_turns": result.get("num_turns"),
        "cost_usd": result.get("total_cost_usd"),
        "usage": result.get("usage"),
        "final_text": result.get("result", ""),
        "is_error": result.get("is_error", False),
    }


def process_song(song, args, partial_dir, trace_dir):
    sid = song["id"]
    partial_path = partial_dir / f"{sid}.json"
    if args.resume and partial_path.exists():
        with open(partial_path, encoding="utf-8") as f:
            return json.load(f)

    n = len(song["source_lines"])
    log(f"[start ] {sid}")
    t0 = time.time()
    events, stderr = [], ""
    for attempt in range(args.retries + 1):
        try:
            events, stderr = run_claude(
                build_prompt(song, args.skill),
                args.model,
                args.effort,
                args.timeout,
                args.allowed_tools,
                args.disallowed_tools,
            )
        except subprocess.TimeoutExpired:
            events, stderr = [], "timeout"
        if events and not summarize(events)["is_error"]:
            break
        log(
            f"[retry ] {sid} attempt {attempt + 1} failed: {summarize(events)['final_text'][:80] if events else stderr[:80]}"
        )
    elapsed = time.time() - t0

    with open(trace_dir / f"{sid}.jsonl", "w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    summary = summarize(events)
    translations = parse_translations(summary["final_text"], n) if summary["final_text"] else None
    if translations is None or len(translations) != n:
        log(f"[fail  ] {sid} parse failed: {stderr[:200]}")
        translations = [""] * n

    r = evaluate_song(song, translations)
    r["time_seconds"] = round(elapsed, 2)
    r["model"] = args.model or "default"
    r["skill"] = args.skill
    r["allowed_tools"] = args.allowed_tools
    r["disallowed_tools"] = args.disallowed_tools
    r["agent"] = summary
    r["failed"] = not any(t.strip() for t in translations)
    r["error"] = summary["final_text"][:200] if summary["is_error"] else ""

    with open(partial_path, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
    log(
        f"[done  ] {sid} SER={r['ser']:.3f} ARI={r['ari']:.3f} match={r['match']} "
        f"turns={summary['num_turns']} scripts={sum(summary['script_calls'].values())} "
        f"cost=${summary['cost_usd'] or 0:.3f} time={elapsed:.0f}s"
    )
    return r


def main():
    parser = make_parser("Benchmark agent-invoked Skills translation")
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--effort", choices=("low", "medium", "high", "xhigh", "max"), default="medium"
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument(
        "--skill",
        default="lyrics-translator",
        help="skill name, or 'none' for the tool-free single-prompt baseline",
    )
    parser.add_argument("--allowed-tools", default=ALLOWED_TOOLS)
    parser.add_argument("--disallowed-tools", default="")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.skill == "none":
        args.bench_method = "vanilla"
        args.disallowed_tools = args.disallowed_tools or VANILLA_TOOLS
    else:
        args.bench_method = (
            "agent"
            if args.skill == "lyrics-translator"
            else f"agent_{args.skill.replace('lyrics-translator-', '')}"
        )
        if args.disallowed_tools:
            args.bench_method += "_no" + args.disallowed_tools.replace(",", "")

    if args.resume and (Path(args.output_dir) / "test_songs.json").exists():
        outdir = Path(args.output_dir)
        with open(outdir / "test_songs.json", encoding="utf-8") as f:
            songs = json.load(f)
    else:
        songs, outdir = load_songs(args)

    partial_dir = outdir / "partial"
    trace_dir = outdir / "traces"
    partial_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)
    if not (REPO / ".claude" / "skills").exists():
        sys.exit("missing .claude/skills symlink; run: ln -s ../skills .claude/skills")

    log(
        f"agent model={args.model or 'default'} effort={args.effort} workers={args.workers} n={len(songs)}"
    )
    results_by_id = {}
    if args.workers <= 1:
        for song in songs:
            r = process_song(song, args, partial_dir, trace_dir)
            results_by_id[r["id"]] = r
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(process_song, s, args, partial_dir, trace_dir): s for s in songs}
            for fut in as_completed(futs):
                try:
                    r = fut.result()
                except Exception as exc:  # noqa: BLE001
                    log(f"[error ] {futs[fut]['id']}: {exc}")
                    continue
                results_by_id[r["id"]] = r

    results = [results_by_id[s["id"]] for s in songs if s["id"] in results_by_id]
    save_results(results, "agent-skills", songs, args.seed, outdir)


if __name__ == "__main__":
    main()
