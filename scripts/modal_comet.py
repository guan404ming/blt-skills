"""COMET/BLEU scoring on Modal (local network too slow for the 2.3GB checkpoint).

Usage:
  modal run scripts/modal_comet.py --payload /tmp/comet_payload.json --out data/bench/semantic_scores.json
"""

import json

import modal

app = modal.App("blt-comet")
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "unbabel-comet==2.2.7", "sacrebleu[ja]", "setuptools<81"
)


@app.function(image=image, gpu="T4", timeout=1800)
def score(payload: dict) -> dict:
    import numpy as np
    import sacrebleu
    from comet import download_model, load_from_checkpoint

    refs, srcs, ids = payload["refs"], payload["srcs"], payload["ids"]
    model = load_from_checkpoint(download_model("Unbabel/wmt22-comet-da"))
    results = {}
    for name, hyps in payload["systems"].items():
        bleu = sacrebleu.corpus_bleu(hyps, [refs], tokenize="zh").score
        chrf = sacrebleu.corpus_chrf(hyps, [refs]).score
        data = [{"src": a, "mt": b, "ref": c} for a, b, c in zip(srcs, hyps, refs)]
        seg = np.array(model.predict(data, batch_size=64, gpus=1).scores)
        song_means = {}
        for i, sid in enumerate(ids):
            song_means.setdefault(sid, []).append(float(seg[i]))
        results[name] = {
            "n_lines": len(hyps),
            "empty": sum(1 for h in hyps if not h.strip()),
            "bleu_zh": round(bleu, 2),
            "chrf": round(chrf, 2),
            "comet22": round(float(seg.mean()), 4),
            "comet_by_song": {k: float(np.mean(v)) for k, v in song_means.items()},
        }
        print(name, results[name]["bleu_zh"], results[name]["comet22"])
    return results


@app.local_entrypoint()
def main(payload: str = "/tmp/comet_payload.json", out: str = "data/bench/semantic_scores.json"):
    p = json.load(open(payload))
    res = score.remote(p)
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
    for name, r in res.items():
        print(
            f"{name:8s} BLEU={r['bleu_zh']:6.2f} chrF={r['chrf']:6.2f} COMET={r['comet22']:.4f} empty={r['empty']}"
        )
    print("saved", out)
