"""
Minimal inference script for the CLT baseline model (Ou et al., ACL 2023).

Uses standard transformers (no custom fork needed). The model is mBART
fine-tuned for English-to-Chinese lyric translation with controllable
length, rhyme, and word boundary constraints.

Usage:
    python scripts/clt_inference.py \
        --model-path /path/to/model/snapshot \
        --lines "There's only one song left for you" "Get me off the streets" \
        --lengths 12 9 \
        --rhymes 1 1

Model weights: https://huggingface.co/LongshenOu/lyric-trans-en2zh
Paper: https://arxiv.org/abs/2305.16816
"""

import argparse
import json
import os

import torch
import torch.nn.functional as F
from transformers import MBartForConditionalGeneration, MBart50TokenizerFast


DEFAULT_MODEL_PATH = "LongshenOu/lyric-trans-en2zh"

BAD_WORDS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "blt",
    "ControllableLyricTranslation", "BartFinetune",
    "tokenizers", "misc", "bad_word_list.json",
)


def load_model(model_path, device="cuda"):
    """Load CLT model and tokenizer."""
    model = MBartForConditionalGeneration.from_pretrained(model_path)
    tokenizer = MBart50TokenizerFast.from_pretrained(model_path)
    model.to(device)
    model.eval()
    return model, tokenizer


def load_bad_words(path=BAD_WORDS_PATH):
    """Load bad word IDs (multi-char tokens to suppress)."""
    if not os.path.exists(path):
        return None
    ids = json.load(open(path))
    return [[i] for i in ids]


def translate(
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
    """
    Translate English lyrics to Chinese with constraints.

    Args:
        lines: list of English source lines
        lengths: list of target character counts per line
        rhymes: list of rhyme type IDs (1-based), default all 1
        boundaries: list of word boundary lists, default all zeros
    """
    n = len(lines)
    if rhymes is None:
        rhymes = [1] * n
    if boundaries is None:
        boundaries = [[0] * l for l in lengths]

    tokenizer.src_lang = "en_XX"
    tokenizer.tgt_lang = "zh_CN"

    # Encode source text
    encoded = tokenizer(lines, return_tensors="pt", padding=True).to(device)
    input_ids = encoded["input_ids"]
    attention_mask = encoded["attention_mask"]

    # Length constraint tokens
    tgt_lens = [f"len_{x}" for x in lengths]
    t1 = tokenizer(tgt_lens, add_special_tokens=False, return_tensors="pt",
                    max_length=1, padding=False, truncation=True)
    tgt_lens = t1["input_ids"].to(device)
    attn_len = t1["attention_mask"].to(device)

    # Rhyme constraint tokens
    tgt_rhymes = [f"rhy_{x}" for x in rhymes]
    t2 = tokenizer(tgt_rhymes, add_special_tokens=False, return_tensors="pt",
                    max_length=1, padding=False, truncation=True)
    tgt_rhymes = t2["input_ids"].to(device)

    # Word boundary constraint tokens
    tgt_stress = ["".join(f"str_{i}" for i in x[::-1]) for x in boundaries]
    t3 = tokenizer(tgt_stress, return_tensors="pt", add_special_tokens=False,
                    padding=True)
    tgt_stress = t3["input_ids"].to(device)
    attn_str = t3["attention_mask"].to(device)
    pad_bit = 20 - tgt_stress.shape[1]
    if pad_bit > 0:
        tgt_stress = F.pad(tgt_stress, (0, pad_bit, 0, 0), value=1).to(device)
        attn_str = F.pad(attn_str, (0, pad_bit, 0, 0), value=1).to(device)

    # Concat constraints with input
    input_ids = torch.cat((tgt_lens, tgt_stress, input_ids), dim=1)
    attention_mask = torch.cat((attn_len, attn_str, attention_mask), dim=1)

    # Decoder input: rhyme token + decoder_start_token_id
    decoder_input_ids = torch.zeros(size=(n, 2), dtype=torch.long).to(device)
    decoder_input_ids[:, 0] = tgt_rhymes.squeeze()
    decoder_input_ids[:, 1] = 2  # decoder_start_token_id

    # Generate
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

    # Decode (CLT outputs are reversed)
    results = []
    for line in tokenizer.batch_decode(generated, skip_special_tokens=True):
        results.append(line[::-1])

    return results


def main():
    parser = argparse.ArgumentParser(description="CLT baseline inference")
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH)
    parser.add_argument("--lines", nargs="+", required=True,
                        help="English source lines")
    parser.add_argument("--lengths", nargs="+", type=int, required=True,
                        help="Target character count per line")
    parser.add_argument("--rhymes", nargs="+", type=int, default=None,
                        help="Rhyme type IDs (default: all 1)")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--json", action="store_true",
                        help="Output as JSON")
    args = parser.parse_args()

    model, tokenizer = load_model(args.model_path, args.device)
    bad_words_ids = load_bad_words()

    translations = translate(
        model, tokenizer, args.lines, args.lengths,
        rhymes=args.rhymes, bad_words_ids=bad_words_ids, device=args.device,
    )

    if args.json:
        print(json.dumps({"translations": translations}, ensure_ascii=False))
    else:
        for i, t in enumerate(translations):
            print(f"{i+1}. {t}")


if __name__ == "__main__":
    main()
