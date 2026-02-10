# blt-skills

Agent Skills for lyrics translation, following the [Agent Skills spec](https://agentskills.io/specification).

Translate lyrics between languages while preserving syllable counts, rhyme scheme, and word-level syllable patterns.

## Skills

| Skill | Description |
|-------|-------------|
| [lyrics-translator](skills/lyrics-translator/SKILL.md) | Orchestrates the full translation pipeline |
| [syllable-counter](skills/syllable-counter/SKILL.md) | Count syllables in text |
| [rhyme-analyzer](skills/rhyme-analyzer/SKILL.md) | Detect rhyme endings and schemes |
| [syllable-pattern-analyzer](skills/syllable-pattern-analyzer/SKILL.md) | Analyze word-level syllable distribution |
| [phonetic-analyzer](skills/phonetic-analyzer/SKILL.md) | IPA conversion and phonetic similarity |
| [lyrics-validator](skills/lyrics-validator/SKILL.md) | Verify translation constraints |

## Setup

Requires Python 3.11+ and espeak (for phonemizer).

```bash
# Install espeak
brew install espeak-ng

# Install pkg
uv sync
```

## CLT Baseline

A minimal inference script for the [Controllable Lyric Translation](https://arxiv.org/abs/2305.16816) (Ou et al., ACL 2023) baseline model.

```bash
# Install with CLT dependencies (torch + transformers)
uv pip install -e ".[clt]"

# Run inference
python scripts/clt_inference.py \
    --lines "There's only one song left for you" "Get me off the streets of this city" \
    --lengths 12 9 \
    --rhymes 1 1
```

Requires model weights from [HuggingFace](https://huggingface.co/LongshenOu/lyric-trans-en2zh).

## Dependencies

- `phonemizer` - IPA conversion via espeak
- `pypinyin` - Chinese pinyin extraction
- `panphon` - IPA phonetic similarity
- `jieba` - Chinese word segmentation
- `pydantic` - data models
- `torch`, `transformers`, `sentencepiece` - CLT baseline only (optional, `pip install -e ".[clt]"`)
