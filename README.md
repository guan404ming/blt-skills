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
sudo apt install espeak-ng

# Symlink an existing venv or create one
ln -s /path/to/existing/.venv .venv
# or
uv sync
```

## Dependencies

- `phonemizer` - IPA conversion via espeak
- `pypinyin` - Chinese pinyin extraction
- `panphon` - IPA phonetic similarity
- `jieba` - Chinese word segmentation
- `pydantic` - data models
