---
name: lyrics-validator
description: Verify translated lyrics against musical constraints including syllable counts, rhyme scheme, and syllable patterns. Use after translating lyrics to check quality.
---

# Lyrics Validator

Verify that translated lyrics meet all musical constraints at once.

## Usage

```bash
python skills/lyrics-validator/scripts/validate.py "<language>" '<target_syllables_json>' "<line1>" "<line2>" ...
```

Example:

```bash
python skills/lyrics-validator/scripts/validate.py cmn '[5,7,5]' "随风而去吧" "在那遥远的天边飞" "随它去吧"
```

Output is JSON with:
- `syllables`: actual syllable counts per line
- `syllables_match`: whether all match targets
- `rhyme_endings`: detected rhyme endings
- `rhymes_valid`: whether rhyme scheme is satisfied
- `feedback`: human-readable constraint feedback

## Constraint Priority

1. **Syllable patterns** (highest) - word-level syllable distribution
2. **Syllable counts** - total syllables per line must match exactly
3. **Rhyme scheme** (lowest) - lines with same label must rhyme

## From Python

```python
from validate import verify_all_constraints

result = verify_all_constraints(
    lines=["line1", "line2"],
    language="cmn",
    target_syllables=[5, 7],
    rhyme_scheme="AA",
    target_patterns=[[2, 3], [3, 4]],
)
```
