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
uv sync --all-extras
```

## Data

English lyrics from [brunokreiner/genius-lyrics](https://huggingface.co/datasets/brunokreiner/genius-lyrics) (~481K songs from Genius, with artist/title/language metadata). Stored in `data/`.

```bash
# Download
uvx --from huggingface_hub hf download brunokreiner/genius-lyrics --repo-type dataset --local-dir data/genius-lyrics
```

## Benchmark

Benchmark translation methods on random songs from genius-lyrics. All scripts share the same interface (`-n`, `--seed`, `--lines-per-song`, `-o`).

```bash
# Run both methods and generate comparison
uv run scripts/run_bench.py -n 5

# Run individually
uv run scripts/run_cc.py -n 5 --model sonnet
uv run scripts/run_clt.py -n 5 --device cpu
```

Outputs `results.json` and `report.md` in the output directory (`data/bench/` by default).

## Dependencies

- `phonemizer` - IPA conversion via espeak
- `pypinyin` - Chinese pinyin extraction
- `panphon` - IPA phonetic similarity
- `jieba` - Chinese word segmentation
- `pydantic` - data models
- `torch`, `transformers`, `sentencepiece` - CLT baseline only (optional, `uv sync --extra clt`)
- `ruff` - linting and formatting (optional, `uv sync --extra dev`)
