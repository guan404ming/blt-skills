#!/usr/bin/env python3
"""Standalone CLT inference (no blt_skills deps) for an isolated transformers-4.x venv.

Reproduces the Ou 2023 CLT baseline: loads the mBART checkpoint, feeds each line
the dataset's native length/rhyme/boundary constraint tokens, suppresses control
tokens, and saves raw translations. Metrics (SER/SCRE/ARI/CCVO) are computed
separately in the main venv (which has blt_skills).

Usage (in .venv-clt):
    python scripts/clt_infer_standalone.py \
        --songs data/bench/ou_clt_v2/<ts>/test_songs.json \
        --out   data/bench/clt_native_translations.json --device cpu
"""

import argparse
import json
import re
from pathlib import Path

import torch
import torch.nn.functional as F
from transformers import MBart50TokenizerFast, MBartForConditionalGeneration

REPO = Path(__file__).resolve().parent.parent
MODEL = "LongshenOu/lyric-trans-en2zh"
DATA = REPO / "data" / "lyric-trans" / "datasets" / "data_parallel"


def load_constraints(kind="source"):
    src = (DATA / "test.source").read_text(encoding="utf-8").splitlines()
    con = (DATA / "constraints" / kind / "test.target").read_text(encoding="utf-8").splitlines()
    bnd = (DATA / "constraints" / kind / "test_boundary.target").read_text(encoding="utf-8").splitlines()
    lengths, rhymes, boundaries = [], [], []
    for s, c, b in zip(src, con, bnd):
        if not s.strip():
            continue
        parts = c.split("\t")
        lengths.append(int(parts[0]))
        rhymes.append(int(parts[1]) if len(parts) > 1 else 1)
        boundaries.append([int(ch) for ch in b.strip()])
    return lengths, rhymes, boundaries


def derive_bad_words(tokenizer):
    pat = re.compile(r"(len_|rhy_|str_|boundary_|<pref>|</pref>|<brk>)")
    vocab = tokenizer.get_vocab()
    bad = [tid for tok, tid in vocab.items() if pat.match(tok) or "DEACTIVATED" in tok.upper()]
    return [[tid] for tid in sorted(set(bad))]


def clt_translate(model, tok, lines, lengths, rhymes, boundaries, bad_words_ids,
                  device, num_beams=5, max_length=36):
    n = len(lines)
    tok.src_lang = "en_XX"
    tok.tgt_lang = "zh_CN"
    enc = tok(lines, return_tensors="pt", padding=True).to(device)
    input_ids, attention_mask = enc["input_ids"], enc["attention_mask"]

    t1 = tok([f"len_{x}" for x in lengths], add_special_tokens=False, return_tensors="pt",
             max_length=1, padding=False, truncation=True)
    tgt_lens, attn_len = t1["input_ids"].to(device), t1["attention_mask"].to(device)
    t2 = tok([f"rhy_{x}" for x in rhymes], add_special_tokens=False, return_tensors="pt",
             max_length=1, padding=False, truncation=True)
    tgt_rhymes = t2["input_ids"].to(device)
    tgt_stress = ["".join(f"str_{i}" for i in x[::-1]) for x in boundaries]
    t3 = tok(tgt_stress, return_tensors="pt", add_special_tokens=False, padding=True)
    tgt_stress, attn_str = t3["input_ids"].to(device), t3["attention_mask"].to(device)
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
            inputs=input_ids, attention_mask=attention_mask,
            decoder_input_ids=decoder_input_ids, num_beams=num_beams,
            max_length=max_length, forced_bos_token_id=tok.lang_code_to_id["zh_CN"],
            bad_words_ids=bad_words_ids,
        )
    # bad_words suppresses the control/placeholder tokens during beam search, but a
    # rare beam can still surface DEACTIVATED_TOKEN; strip it before the right-to-left flip.
    decoded = tok.batch_decode(generated, skip_special_tokens=True)
    return [re.sub(r"DEACTIVATED_TOKEN", "", line)[::-1] for line in decoded]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--songs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--model", default=MODEL, help="model id or local snapshot path")
    ap.add_argument("--constraints", default="source", choices=("source", "reference"))
    args = ap.parse_args()

    songs = json.load(open(args.songs, encoding="utf-8"))
    model = MBartForConditionalGeneration.from_pretrained(args.model).to(args.device).eval()
    tok = MBart50TokenizerFast.from_pretrained(args.model)
    bad = derive_bad_words(tok)
    print(f"transformers inference: {len(songs)} songs, {len(bad)} bad-word tokens, constraints={args.constraints}")
    clen, crhy, cbnd = load_constraints(args.constraints)

    out = {}
    if Path(args.out).exists():  # resume
        out = json.load(open(args.out, encoding="utf-8"))
        print(f"resuming: {len(out)} songs already done")
    for i, s in enumerate(songs, 1):
        if s["id"] in out:
            continue
        st = s["metadata"]["test_start_line"]
        nl = len(s["source_lines"])
        tr = clt_translate(model, tok, s["source_lines"],
                           clen[st:st + nl], crhy[st:st + nl], cbnd[st:st + nl],
                           bad, args.device)
        out[s["id"]] = tr
        print(f"{s['id']}: len={clen[st:st+nl]} -> chars={[len(re.sub(chr(32),'',t)) for t in tr]}")
        if i % 10 == 0:  # incremental save
            json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"saved {args.out} ({len(out)} songs)")


if __name__ == "__main__":
    main()
