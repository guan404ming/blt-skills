---
name: syllable-pattern-analyzer
description: Analyze word-level syllable distribution in text lines. Get syllable patterns, compare against targets, and score pattern quality. Use when matching word rhythm in lyrics translation.
---

# Syllable Pattern Analyzer

Analyze how syllables are distributed across words in each line.

## Usage

### Get syllable patterns

```bash
python skills/syllable-pattern-analyzer/scripts/pattern_analysis.py "<language>" "<line1>" "<line2>" ...
```

Output shows per-word syllable counts for each line, e.g., `Line 1: [1, 2, 1] (total: 4)`.

### From Python

```python
from pattern_analysis import get_syllable_patterns, analyze_pattern_alignment, score_syllable_patterns

# Get patterns
patterns = get_syllable_patterns(["Let it go", "Can't hold it back"], "en-us")
# [[1, 1, 1], [1, 1, 1, 1]]

# Compare against target
result = analyze_pattern_alignment([1, 1, 1], [2, 1])
# {'matches': False, 'similarity': 0.58, 'differences': [...], 'suggestions': [...]}

# Score multiple lines
score = score_syllable_patterns(target_patterns, current_patterns)
# {'overall_score': 0.85, 'exact_match_rate': 0.5, ...}
```

## How It Works

- **Chinese**: Segments words using jieba, each character = 1 syllable.
- **Other languages**: Splits on whitespace, counts syllables per word via IPA.
- Alignment scoring uses position differences (50%), length match (25%), total syllable match (25%).
