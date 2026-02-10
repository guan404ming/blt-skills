---
name: rhyme-analyzer
description: Extract rhyme endings, check if texts rhyme, and detect rhyme schemes. Use when analyzing or preserving rhyme in lyrics translation or poetry.
---

# Rhyme Analyzer

Analyze rhyme endings, check rhyme pairs, and detect rhyme schemes.

## Usage

### Extract rhyme ending

```bash
python skills/rhyme-analyzer/scripts/rhyme_analysis.py "<text>" "<language>"
```

### Check if two texts rhyme

```bash
python skills/rhyme-analyzer/scripts/rhyme_analysis.py "<text1>" "<language>" "<text2>"
```

### Detect rhyme scheme (from Python)

```python
from rhyme_analysis import detect_rhyme_scheme
scheme = detect_rhyme_scheme(["line1", "line2", "line3", "line4"], "en-us")
# e.g., "ABAB"
```

## How It Works

- **Chinese**: Uses pypinyin to extract the final (yunmu) of the last character.
- **Other languages**: Converts to IPA, finds the last vowel position, returns everything from that vowel onward.
- Rhyme check: two texts rhyme if their endings match or one contains the other.
