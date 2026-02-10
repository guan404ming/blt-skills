---
name: lyrics-translator
description: Translate lyrics while preserving musical constraints (syllable counts, rhyme scheme, syllable patterns). Use when the user wants to translate song lyrics from one language to another while maintaining singability.
---

# Lyrics Translator

Translate lyrics between languages while preserving syllable counts, rhyme scheme, and word-level syllable patterns so the translation remains singable.

## Workflow

Follow this 3-phase pipeline. Use the sub-skill scripts to verify at each step.

### Phase 1: Extract Constraints

Before translating, analyze the source lyrics to extract targets:

1. Count syllables per line:
   ```bash
   python skills/syllable-counter/scripts/count_syllables.py "<line>" "<source_lang>"
   ```

2. Get syllable patterns (word-level distribution):
   ```bash
   python skills/syllable-pattern-analyzer/scripts/pattern_analysis.py "<source_lang>" "<line1>" "<line2>" ...
   ```

3. Detect rhyme scheme:
   ```python
   from rhyme_analysis import detect_rhyme_scheme
   scheme = detect_rhyme_scheme(lines, source_lang)
   ```

Record the target syllable counts, patterns, and rhyme scheme.

### Phase 2: Initial Translation

Translate all lines at once, considering all 3 constraints:

- Each line must have EXACTLY the target syllable count.
- Lines sharing a rhyme label must rhyme in the target language.
- Word-level syllable distribution should match the target pattern.
- Maintain poetic quality and emotional impact.

Key rules for Chinese targets:
- Each Chinese character = 1 syllable.
- Strip all punctuation when counting.

### Phase 3: Iterative Refinement

For each line, verify and refine:

1. **Check syllable count**:
   ```bash
   python skills/syllable-counter/scripts/count_syllables.py "<translation>" "<target_lang>"
   ```

2. If count is wrong, adjust the translation:
   - Too long: remove adjectives, use shorter words, merge concepts.
   - Too short: add descriptive words, use longer alternatives.
   - Re-check after each adjustment. Repeat up to 10 times.

3. **Check syllable patterns**:
   ```bash
   python skills/syllable-pattern-analyzer/scripts/pattern_analysis.py "<target_lang>" "<translated_line>"
   ```
   - Skip refinement if average pattern similarity is already >75%.
   - Only accept pattern changes that improve similarity by >15%.

4. **Verify rhyme preservation** after pattern adjustments using the rhyme-analyzer.

### Final Validation

Run the full validator on all translated lines:

```bash
python skills/lyrics-validator/scripts/validate.py "<target_lang>" '<target_syllables_json>' "<line1>" "<line2>" ...
```

## Output Format

Present the final translation as:

```
1. <translated line 1>
2. <translated line 2>
...

Syllable accuracy: X/Y lines match
Pattern similarity: X%
Rhyme scheme: <scheme>
```

## Sub-Skills Used

- [syllable-counter](../syllable-counter/SKILL.md) - count syllables
- [rhyme-analyzer](../rhyme-analyzer/SKILL.md) - rhyme detection
- [syllable-pattern-analyzer](../syllable-pattern-analyzer/SKILL.md) - word rhythm patterns
- [lyrics-validator](../lyrics-validator/SKILL.md) - constraint verification
- [phonetic-analyzer](../phonetic-analyzer/SKILL.md) - IPA and phonetic similarity

## Configuration Reference

See [references/config.md](references/config.md) for language codes and defaults.
See [references/graph-pipeline.md](references/graph-pipeline.md) for pipeline architecture details.
