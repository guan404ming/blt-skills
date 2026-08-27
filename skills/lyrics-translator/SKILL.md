---
name: lyrics-translator
description: Translate lyrics while preserving musical constraints (syllable counts, rhyme scheme, syllable patterns). Use when the user wants to translate song lyrics from one language to another while maintaining singability.
---

# Lyrics Translator

Translate lyrics between languages so the translation stays singable. Never count syllables or judge rhyme yourself. Always run the sub-skill scripts and use their output.

## Workflow

### Step 0: Extract Constraints

Run these on the source lines before you translate:

1. Syllable count per line:
   ```bash
   python skills/syllable-counter/scripts/count_syllables.py "<line>" "<source_lang>"
   ```
2. Rhyme scheme:
   ```bash
   python skills/rhyme-analyzer/scripts/rhyme_analysis.py --scheme "<source_lang>" "<line1>" "<line2>" ...
   ```
3. Word-level syllable pattern:
   ```bash
   python skills/syllable-pattern-analyzer/scripts/pattern_analysis.py "<source_lang>" "<line1>" "<line2>" ...
   ```

Record the target syllable counts, the rhyme scheme, and the patterns.

### Phase 1: Initial Translation

Translate all lines at once:

- Each line must have EXACTLY the target syllable count.
- Lines that share a rhyme label must rhyme in the target language. Lines with different labels must not rhyme.
- Keep the word-level syllable pattern close to the source when possible.
- Keep the meaning and the emotion of the source.

Rules for Chinese targets: one Han character is one syllable. Write only Han characters. Do not mix Latin letters or digits into a line.

### Phase 2: Syllable Refinement

For each translated line:

1. Count its syllables:
   ```bash
   python skills/syllable-counter/scripts/count_syllables.py "<translation>" "<target_lang>"
   ```
2. If the count differs from the target, rewrite the line:
   - Too long: remove modifiers, use shorter words, merge concepts.
   - Too short: add descriptive words, use longer words.
   - Count again after each rewrite. Stop after 10 attempts and keep the closest attempt.

### Final Validation

Run the validator on all lines. Pass the target counts as a JSON list of integers and the recorded scheme:

```bash
python skills/lyrics-validator/scripts/validate.py "<target_lang>" '[10, 9, 6, 6, 5]' "<line1>" "<line2>" ... --rhyme ABCCD
```

If `syllables_match` is false, return to Phase 2 for the failing lines. If `rhymes_valid` is false, try one rewrite of the failing lines that keeps the syllable counts, then count again.

## Output Format

Return only the final translation:

```
1. <translated line 1>
2. <translated line 2>
...
```

## Sub-Skills Used

- [syllable-counter](../syllable-counter/SKILL.md) - count syllables
- [rhyme-analyzer](../rhyme-analyzer/SKILL.md) - rhyme endings and schemes
- [syllable-pattern-analyzer](../syllable-pattern-analyzer/SKILL.md) - word rhythm patterns
- [lyrics-validator](../lyrics-validator/SKILL.md) - constraint verification
- [phonetic-analyzer](../phonetic-analyzer/SKILL.md) - IPA and phonetic similarity

## Configuration Reference

See [references/config.md](references/config.md) for language codes and defaults.
