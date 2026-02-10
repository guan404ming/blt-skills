# Pipeline Architecture

The lyrics translation follows a 3-phase pipeline.

## Phase 1: Constraint Extraction

Extract musical constraints from source lyrics:
- **Syllable counts**: Total syllables per line (IPA-based for most languages, character count for Chinese).
- **Rhyme scheme**: Detected pattern like AABB, ABAB based on ending sounds.
- **Syllable patterns**: Per-word syllable distribution, e.g., `[1, 2, 1]` means 3 words with 1, 2, 1 syllables.

## Phase 2: Initial Translation

Translate all lines at once, considering all 3 constraints simultaneously. This produces a first draft that balances meaning, syllable count, rhyme, and rhythm.

## Phase 3: Iterative Refinement

Two sub-phases:

### 3a: Syllable Count Refinement
For each line where the syllable count doesn't match:
- Prompt adjustments (shorten or lengthen).
- Verify with the syllable counter after each attempt.
- Track the best result by closest match.
- Up to 10 attempts per line.

### 3b: Pattern Refinement
After syllable counts are matched:
- Skip if average pattern similarity >75%.
- For each mismatched line, adjust word choice to match target pattern.
- Require >15% improvement to accept changes.
- Verify rhyme is preserved before accepting.

## Scoring

Final metrics:
- **Syllable accuracy**: Percentage of lines with exact syllable count match.
- **Pattern distribution score**: Weighted combination of exact matches (70%) and fuzzy matches (30%).
- **Overall score**: exact_match_rate (40%) + average_similarity (30%) + syllable_score (30%).
