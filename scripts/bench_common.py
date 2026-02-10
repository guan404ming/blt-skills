"""Shared utilities for benchmark scripts."""

import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# Skill usage counter

skill_counter: Counter = Counter()


def reset_skill_counter():
    skill_counter.clear()


def get_skill_counts():
    return dict(skill_counter)


# Metric calculations


def levenshtein(seq1, seq2):
    m, n = len(seq1), len(seq2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq1[i - 1] == seq2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp[m][n]


def calc_ser(src_syl, tgt_syl):
    n = max(len(src_syl), len(tgt_syl))
    return levenshtein(src_syl, tgt_syl) / n if n else 0.0


def calc_scre(src_syl, tgt_syl):
    if not src_syl:
        return 0.0
    errs = []
    for s, t in zip(src_syl, tgt_syl):
        errs.append(abs(s - t) / s if s else (0.0 if t == 0 else 1.0))
    return sum(errs) / len(errs)


def scheme_to_labels(scheme):
    m, labels, nxt = {}, [], 0
    for c in scheme:
        if c not in m:
            m[c] = nxt
            nxt += 1
        labels.append(m[c])
    return labels


def calc_ari(src_scheme, tgt_scheme):
    if not src_scheme or not tgt_scheme:
        return 0.0
    from sklearn.metrics import adjusted_rand_score

    sl = scheme_to_labels(src_scheme)
    tl = scheme_to_labels(tgt_scheme)
    if len(sl) != len(tl):
        mx = max(len(sl), len(tl))
        nxt = max(max(sl), max(tl)) + 1
        if len(sl) < mx:
            sl += list(range(nxt, nxt + mx - len(sl)))
        if len(tl) < mx:
            tl += list(range(nxt, nxt + mx - len(tl)))
    return adjusted_rand_score(sl, tl)


# Song sampling


def sample_songs(csv_path, n, seed, lines_per_song, words_per_line):
    import random

    random.seed(seed)
    csv.field_size_limit(10 * 1024 * 1024)
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lyrics = row.get("lyrics", "").strip()
            artist = row.get("artist_name", "").strip() or "unknown"
            if lyrics and len(lyrics.split()) >= lines_per_song * words_per_line:
                rows.append((artist, lyrics))
    chosen = random.sample(rows, min(n, len(rows)))
    songs = []
    for i, (artist, lyrics) in enumerate(chosen, 1):
        words = lyrics.split()
        lines = []
        for j in range(lines_per_song):
            start = j * words_per_line
            end = start + words_per_line
            if end <= len(words):
                lines.append(" ".join(words[start:end]))
        if len(lines) == lines_per_song:
            songs.append(
                {
                    "id": f"genius_{i:03d}",
                    "source_lines": lines,
                    "source_lang": "en-us",
                    "target_lang": "cmn",
                    "metadata": {"artist": artist},
                }
            )
    return songs


# Shared CLI setup


def make_parser(description):
    import argparse

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("-n", type=int, required=True, help="Number of songs")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--lines-per-song", type=int, default=5, help="Lines per song (default: 5)")
    parser.add_argument(
        "--words-per-line", type=int, default=8, help="Words per line when splitting (default: 8)"
    )
    parser.add_argument(
        "-o", "--output-dir", default="data/bench", help="Output directory (default: data/bench)"
    )
    return parser


def load_songs(args):
    script_dir = Path(__file__).resolve().parent
    data_csv = script_dir.parent / "data" / "genius-lyrics" / "english_lyrics_some_with_genres.csv"
    if not data_csv.exists():
        print(f"Error: dataset not found at {data_csv}", file=sys.stderr)
        print(
            "Download with: uvx --from huggingface_hub hf download brunokreiner/genius-lyrics "
            "--repo-type dataset --local-dir data/genius-lyrics",
            file=sys.stderr,
        )
        sys.exit(1)

    method = getattr(args, "bench_method", "all")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = Path(args.output_dir) / f"{ts}_{method}"
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Sampling {args.n} songs (seed={args.seed})...", file=sys.stderr)
    songs = sample_songs(str(data_csv), args.n, args.seed, args.lines_per_song, args.words_per_line)
    if len(songs) < args.n:
        print(f"Warning: only got {len(songs)} songs", file=sys.stderr)

    songs_path = outdir / "test_songs.json"
    with open(songs_path, "w", encoding="utf-8") as f:
        json.dump(songs, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(songs)} songs to {songs_path}", file=sys.stderr)

    return songs, outdir


def evaluate_song(song, translations):
    """Evaluate translations for a single song, return result dict."""
    from blt_skills import count_syllables, detect_rhyme_scheme

    lines = song["source_lines"]
    src_lang = song["source_lang"]
    tgt_lang = song["target_lang"]

    skill_counter["syllable-counter"] += len(lines) + len(translations)
    skill_counter["rhyme-analyzer"] += 2

    src_syl = [count_syllables(line, src_lang) for line in lines]
    src_rhyme = detect_rhyme_scheme(lines, src_lang)
    tgt_syl = [count_syllables(t, tgt_lang) for t in translations]
    tgt_rhyme = detect_rhyme_scheme(translations, tgt_lang)
    matches = sum(1 for a, b in zip(src_syl, tgt_syl) if a == b)

    return {
        "id": song["id"],
        "artist": song["metadata"]["artist"],
        "ser": calc_ser(src_syl, tgt_syl),
        "scre": calc_scre(src_syl, tgt_syl),
        "ari": calc_ari(src_rhyme, tgt_rhyme),
        "src_syl": src_syl,
        "tgt_syl": tgt_syl,
        "src_rhyme": src_rhyme,
        "tgt_rhyme": tgt_rhyme,
        "match": f"{matches}/{len(lines)}",
        "translations": translations,
    }


def save_results(results, method_name, songs, seed, outdir, skill_counts=None):
    """Save results.json and report.md."""

    def avg(vals):
        return sum(vals) / len(vals) if vals else 0.0

    output = {
        "method": method_name,
        "date": datetime.now().isoformat(),
        "n": len(songs),
        "seed": seed,
        "avg_ser": avg([r["ser"] for r in results]),
        "avg_scre": avg([r["scre"] for r in results]),
        "avg_ari": avg([r["ari"] for r in results]),
        "avg_time": avg([r.get("time_seconds", 0) for r in results]),
        "results": results,
    }
    if skill_counts:
        output["skill_counts"] = skill_counts

    results_path = outdir / "results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {results_path}", file=sys.stderr)

    # Report
    lines = []
    lines.append(f"# {method_name} Benchmark Report")
    lines.append("")
    lines.append(f"- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"- **Songs**: {len(songs)}")
    lines.append(f"- **Seed**: {seed}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| **SER** (lower better) | {output['avg_ser']:.4f} |")
    lines.append(f"| **SCRE** (lower better) | {output['avg_scre']:.4f} |")
    lines.append(f"| **ARI** (higher better) | {output['avg_ari']:.4f} |")
    lines.append(f"| **Avg Time (s)** | {output['avg_time']:.2f} |")
    lines.append("")

    if skill_counts:
        lines.append("## Skill Usage")
        lines.append("")
        lines.append("| Skill | Calls |")
        lines.append("|-------|-------|")
        for skill, count in sorted(skill_counts.items()):
            lines.append(f"| {skill} | {count} |")
        lines.append(f"| **Total** | **{sum(skill_counts.values())}** |")
        lines.append("")

    lines.append("## Per-Song Results")
    lines.append("")
    lines.append("| Song | Artist | Match | SER | SCRE | ARI | Time |")
    lines.append("|------|--------|-------|-----|------|-----|------|")
    for r in results:
        lines.append(
            f"| {r['id']} | {r['artist']} | {r['match']} | "
            f"{r['ser']:.2f} | {r['scre']:.2f} | {r['ari']:.2f} | "
            f"{r.get('time_seconds', 0):.1f}s |"
        )
    lines.append("")

    lines.append("## Sample Translations")
    lines.append("")
    for i, (song, r) in enumerate(zip(songs[:3], results[:3])):
        lines.append(f"### {song['id']} ({song['metadata']['artist']})")
        lines.append("")
        lines.append("**Source:**")
        lines.append("```")
        for j, src in enumerate(song["source_lines"], 1):
            lines.append(f"{j}. {src}")
        lines.append("```")
        lines.append("")
        lines.append(f"**Translation** (match {r['match']}):")
        lines.append("```")
        for j, t in enumerate(r["translations"], 1):
            lines.append(f"{j}. {t} [{r['tgt_syl'][j - 1]}]")
        lines.append("```")
        lines.append("")

    report_path = outdir / "report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Saved {report_path}", file=sys.stderr)

    # Print summary to stdout
    print(
        json.dumps(
            {
                "avg_ser": round(output["avg_ser"], 4),
                "avg_scre": round(output["avg_scre"], 4),
                "avg_ari": round(output["avg_ari"], 4),
                "avg_time": round(output["avg_time"], 2),
            },
            indent=2,
        )
    )


# CC+Skills translation


def extract_constraints(lines, lang):
    from blt_skills import count_syllables, detect_rhyme_scheme, get_syllable_patterns

    skill_counter["syllable-counter"] += len(lines)
    skill_counter["rhyme-analyzer"] += 1
    skill_counter["syllable-pattern-analyzer"] += 1
    return {
        "syllables": [count_syllables(line, lang) for line in lines],
        "rhyme_scheme": detect_rhyme_scheme(lines, lang),
        "patterns": get_syllable_patterns(lines, lang),
    }


def parse_translations(text, expected_count):
    import re

    translations = []
    for line in text.strip().split("\n"):
        m = re.match(r"\d+[\.\)]\s*(.+)", line.strip())
        if m:
            val = m.group(1).strip()
            if (val.startswith('"') and val.endswith('"')) or (
                val.startswith("'") and val.endswith("'")
            ):
                val = val[1:-1]
            val = re.split(r"\s*[\(（]", val)[0].strip()
            val = re.split(r"\s+[-—]\s+", val)[0].strip()
            if val:
                translations.append(val)
    if len(translations) >= expected_count:
        return translations[:expected_count]
    return None


def call_claude(prompt, model=None):
    import subprocess

    cmd = ["claude", "-p", prompt]
    if model:
        cmd.extend(["--model", model])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"claude error: {result.stderr}", file=sys.stderr)
        return None
    return result.stdout.strip()


def translate_with_claude(lines, source_lang, target_lang, constraints, model=None):
    from blt_skills import count_syllables

    target_syls = constraints["syllables"]
    rhyme = constraints["rhyme_scheme"]
    n = len(lines)

    prompt = f"""Translate these {source_lang} lyrics to {target_lang}.

Source lines:
{chr(10).join(f"{i + 1}. {line}" for i, line in enumerate(lines))}

Constraints:
- Target syllable counts per line: {target_syls}
- Source rhyme scheme: {rhyme}
- For Chinese: each character = 1 syllable, strip punctuation when counting.
- Preserve poetic meaning and emotional impact.

IMPORTANT: Return ONLY numbered translated lines.
NO explanations, NO annotations, NO syllable counts. Example format:
1. 中文翻译
2. 中文翻译"""

    max_attempts = 5
    translations = None

    for attempt in range(max_attempts):
        print(f"  Attempt {attempt + 1}/{max_attempts}...", file=sys.stderr)
        output = call_claude(prompt, model=model)
        if output is None:
            continue

        translations = parse_translations(output, n)
        if translations is None:
            print(f"  Could not parse {n} lines from output", file=sys.stderr)
            continue

        skill_counter["syllable-counter"] += len(translations)
        actual = [count_syllables(t, target_lang) for t in translations]
        mismatches = [
            (i, actual[i], target_syls[i]) for i in range(n) if actual[i] != target_syls[i]
        ]

        if not mismatches:
            print(f"  All lines match on attempt {attempt + 1}", file=sys.stderr)
            return translations

        print(f"  {len(mismatches)} mismatches, refining...", file=sys.stderr)

        fix_lines = []
        for i, act, tgt in mismatches:
            fix_lines.append(
                f'Line {i + 1}: got {act} syllables, need {tgt}. Current: "{translations[i]}"'
            )

        prompt = f"""Fix these {target_lang} lyric translations.
Each Chinese character = 1 syllable (strip punctuation).

{chr(10).join(fix_lines)}

Keep the other lines unchanged. Return ONLY ALL {n} lines numbered, NO explanations:
{chr(10).join(f"{i + 1}. {translations[i]}" for i in range(n))}"""

    return translations


# CLT baseline inference


CLT_DEFAULT_MODEL = "LongshenOu/lyric-trans-en2zh"

CLT_BAD_WORDS_PATH = str(
    Path(__file__).resolve().parent.parent.parent
    / "blt"
    / "ControllableLyricTranslation"
    / "BartFinetune"
    / "tokenizers"
    / "misc"
    / "bad_word_list.json"
)


def load_clt_model(model_path=None, device="cuda"):
    from transformers import MBart50TokenizerFast, MBartForConditionalGeneration

    mp = model_path or CLT_DEFAULT_MODEL
    model = MBartForConditionalGeneration.from_pretrained(mp)
    tokenizer = MBart50TokenizerFast.from_pretrained(mp)
    model.to(device)
    model.eval()
    return model, tokenizer


def load_clt_bad_words(path=None):
    import os

    p = path or CLT_BAD_WORDS_PATH
    if not os.path.exists(p):
        return None
    ids = json.load(open(p))
    return [[i] for i in ids]


def clt_translate(
    model,
    tokenizer,
    lines,
    lengths,
    rhymes=None,
    boundaries=None,
    bad_words_ids=None,
    device="cuda",
    num_beams=5,
    max_length=36,
):
    import torch
    import torch.nn.functional as F

    n = len(lines)
    if rhymes is None:
        rhymes = [1] * n
    if boundaries is None:
        boundaries = [[0] * length for length in lengths]

    tokenizer.src_lang = "en_XX"
    tokenizer.tgt_lang = "zh_CN"

    encoded = tokenizer(lines, return_tensors="pt", padding=True).to(device)
    input_ids = encoded["input_ids"]
    attention_mask = encoded["attention_mask"]

    tgt_lens = [f"len_{x}" for x in lengths]
    t1 = tokenizer(
        tgt_lens,
        add_special_tokens=False,
        return_tensors="pt",
        max_length=1,
        padding=False,
        truncation=True,
    )
    tgt_lens = t1["input_ids"].to(device)
    attn_len = t1["attention_mask"].to(device)

    tgt_rhymes = [f"rhy_{x}" for x in rhymes]
    t2 = tokenizer(
        tgt_rhymes,
        add_special_tokens=False,
        return_tensors="pt",
        max_length=1,
        padding=False,
        truncation=True,
    )
    tgt_rhymes = t2["input_ids"].to(device)

    tgt_stress = ["".join(f"str_{i}" for i in x[::-1]) for x in boundaries]
    t3 = tokenizer(tgt_stress, return_tensors="pt", add_special_tokens=False, padding=True)
    tgt_stress = t3["input_ids"].to(device)
    attn_str = t3["attention_mask"].to(device)
    pad_bit = 20 - tgt_stress.shape[1]
    if pad_bit > 0:
        tgt_stress = F.pad(tgt_stress, (0, pad_bit, 0, 0), value=1).to(device)
        attn_str = F.pad(attn_str, (0, pad_bit, 0, 0), value=1).to(device)

    input_ids = torch.cat((tgt_lens, tgt_stress, input_ids), dim=1)
    attention_mask = torch.cat((attn_len, attn_str, attention_mask), dim=1)

    decoder_input_ids = torch.zeros(size=(n, 2), dtype=torch.long).to(device)
    decoder_input_ids[:, 0] = tgt_rhymes.squeeze()
    decoder_input_ids[:, 1] = 2

    with torch.no_grad():
        generated = model.generate(
            inputs=input_ids,
            attention_mask=attention_mask,
            decoder_input_ids=decoder_input_ids,
            num_beams=num_beams,
            max_length=max_length,
            forced_bos_token_id=tokenizer.lang_code_to_id["zh_CN"],
            bad_words_ids=bad_words_ids,
        )

    results = []
    for line in tokenizer.batch_decode(generated, skip_special_tokens=True):
        results.append(line[::-1])
    return results
