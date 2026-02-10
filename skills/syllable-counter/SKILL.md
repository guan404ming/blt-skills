---
name: syllable-counter
description: Count syllables in text for any supported language. Use when checking syllable counts for lyrics translation, poetry, or rhythm analysis.
---

# Syllable Counter

Count syllables in text using IPA-based vowel nuclei detection.

## Usage

```bash
python skills/syllable-counter/scripts/count_syllables.py "<text>" "<language>"
```

Output: `Syllables: <count>`

## How It Works

- **Chinese** (`cmn`, `zh`): Each character = 1 syllable. Punctuation and whitespace are stripped.
- **Other languages**: Converts text to IPA via phonemizer, then counts diphthongs and vowel nuclei.

## Examples

```bash
python skills/syllable-counter/scripts/count_syllables.py "Let it go" en-us
# Syllables: 3

python skills/syllable-counter/scripts/count_syllables.py "随它吧" cmn
# Syllables: 3
```
