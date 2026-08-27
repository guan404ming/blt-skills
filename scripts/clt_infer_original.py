import argparse
import json
from pathlib import Path

import torch
import torch.nn.functional as F

from models.MBarts import MBart50TokenizerFast, MBartForConditionalGenerationCharLevel

REPO = Path("/Users/wchiu/Documents/GitHub/blt-skills")
DATA = REPO / "data" / "lyric-trans" / "datasets" / "data_parallel"


def load_native():
    src = (DATA / "test.source").read_text(encoding="utf-8").splitlines()
    con = (DATA / "constraints" / "source" / "test.target").read_text(encoding="utf-8").splitlines()
    bnd = (DATA / "constraints" / "source" / "test_boundary.target").read_text(encoding="utf-8").splitlines()
    out = {}
    for s, c, b in zip(src, con, bnd):
        if not s.strip():
            continue
        parts = c.split("\t")
        out[s.strip()] = (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0, [int(x) for x in b.strip().split()] if b.strip() else [])
    return out


def translate(model, tok, lines, lengths, rhymes, boundaries, device):
    tok.src_lang = "en_XX"
    tok.tgt_lang = "zh_CN"
    enc = tok(lines, return_tensors="pt", padding=True).to(device)
    t1 = tok([f"len_{x}" for x in lengths], add_special_tokens=False, return_tensors="pt", max_length=1, padding=False, truncation=True)
    t2 = tok([f"rhy_{x}" for x in rhymes], add_special_tokens=False, return_tensors="pt", max_length=1, padding=False, truncation=True)
    stress = ["".join(f"str_{i}" for i in (b[:L] + [0] * max(0, L - len(b)))[::-1]) for b, L in zip(boundaries, lengths)]
    t3 = tok(stress, return_tensors="pt", add_special_tokens=False, padding=True)
    tgt_stress = t3["input_ids"]
    attn_str = t3["attention_mask"]
    pad = 20 - tgt_stress.shape[1]
    if pad > 0:
        tgt_stress = F.pad(tgt_stress, (0, pad, 0, 0), value=1)
        attn_str = F.pad(attn_str, (0, pad, 0, 0), value=1)
    else:
        tgt_stress = tgt_stress[:, :20]
        attn_str = attn_str[:, :20]
    input_ids = torch.cat((t1["input_ids"], tgt_stress, enc["input_ids"].cpu()), dim=1).to(device)
    attention_mask = torch.cat((t1["attention_mask"], attn_str, enc["attention_mask"].cpu()), dim=1).to(device)
    dec = torch.zeros((len(lines), 2), dtype=torch.long)
    dec[:, 0] = t2["input_ids"].squeeze(1)
    dec[:, 1] = 2
    with torch.no_grad():
        gen = model.generate(inputs=input_ids, attention_mask=attention_mask, decoder_input_ids=dec.to(device), num_beams=5, max_length=36, forced_bos_token_id=tok.lang_code_to_id["zh_CN"])
    return [t[::-1] for t in tok.batch_decode(gen, skip_special_tokens=True)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--songs", required=True)
    ap.add_argument("--lengths-json", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default="LongshenOu/lyric-trans-en2zh")
    args = ap.parse_args()
    songs = json.load(open(args.songs, encoding="utf-8"))
    if args.limit:
        songs = songs[: args.limit]
    lengths = json.load(open(args.lengths_json)) if args.lengths_json else None
    native = load_native()
    model = MBartForConditionalGenerationCharLevel.from_pretrained(args.model).to(args.device).eval()
    tok = MBart50TokenizerFast.from_pretrained(args.model)
    out = {}
    if Path(args.out).exists():
        out = json.load(open(args.out, encoding="utf-8"))
    for s in songs:
        if s["id"] in out:
            continue
        nat = [native.get(l.strip(), (None, 0, [])) for l in s["source_lines"]]
        lens = lengths[s["id"]] if lengths else [n[0] for n in nat]
        rhy = [n[1] for n in nat]
        bnd = [n[2] for n in nat]
        out[s["id"]] = translate(model, tok, s["source_lines"], lens, rhy, bnd, args.device)
        print(s["id"], lens, [len(t) for t in out[s["id"]]], out[s["id"]][0][:20], flush=True)
        json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
