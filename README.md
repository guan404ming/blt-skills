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

Expose the skills to Claude Code, then run the agent benchmark on the Ou et al. (2023) en-zh test windows (`-n`, `--seed`, `--target-lang`, `-o`):

```bash
ln -s ../skills .claude/skills
uv run scripts/run_agent.py -n 100 --model haiku --workers 4
uv run scripts/run_agent.py -n 30 --model haiku --target-lang ja
uv run scripts/run_vanilla.py -n 100 --model haiku --workers 4   # single-prompt baseline
uv run scripts/run_agent.py -n 100 --model haiku --skill lyrics-translator-prompt-only --disallowed-tools Bash,Agent,Task
```

Each agent item is one `claude -p` call that receives only the source lines; the trace of every tool call is saved under `data/bench/<run>/traces/`. Evaluate and score with:

```bash
uv run scripts/eval_fixed.py --songs <run>/test_songs.json --out data/bench/final.json vanilla=<vanilla_run>/partial agent=<run>/partial
uv run scripts/build_comet_payload.py --out /tmp/comet.json blt=<run>/partial vanilla=<vanilla_run>/partial
modal run scripts/modal_comet.py --payload /tmp/comet.json --out data/bench/semantic_scores.json
```

The CLT baseline (`data/bench/clt_translations.json`) comes from `scripts/clt_infer_original.py`, run inside a checkout of [ControllableLyricTranslation](https://github.com/Sonata165/ControllableLyricTranslation) with our syllable targets (`data/bench/clt_lengths_fixed.json`).

## Dependencies

- `phonemizer` - IPA conversion via espeak
- `pypinyin` - Chinese pinyin extraction
- `panphon` - IPA phonetic similarity
- `jieba` - Chinese word segmentation
- `pydantic` - data models
- `torch`, `transformers`, `sentencepiece` - CLT baseline only (optional, `uv sync --extra clt`)
- `ruff` - linting and formatting (optional, `uv sync --extra dev`)
