---
name: lyrics-translator-phase1-only
description: Ablation variant of lyrics-translator that extracts constraints and translates once, with no refinement loop. Use only when explicitly asked for the Phase-1-only ablation.
---

# Lyrics Translator (Phase 1 only ablation)

Translate lyrics between languages so the translation stays singable. Never count syllables or judge rhyme yourself. Run the scripts to extract constraints, then translate once. Do not verify or revise the translation afterwards.

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

Rules for Chinese targets: one Han character is one syllable. Write only Han characters.

Do not run any script on your translation. Output it directly.

## Output Format

Return only the final translation:

```
1. <translated line 1>
2. <translated line 2>
...
```
