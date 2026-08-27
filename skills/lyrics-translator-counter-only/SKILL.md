---
name: lyrics-translator-counter-only
description: Ablation variant of lyrics-translator that enforces syllable counts only. Use only when explicitly asked for the counter-only ablation.
---

# Lyrics Translator (counter-only ablation)

Translate lyrics between languages so every line keeps the source syllable count. Never count syllables yourself. Always run the script and use its output. Do not analyze or enforce rhyme.

## Workflow

### Step 0: Extract Constraints

Count the syllables of each source line:
```bash
python skills/syllable-counter/scripts/count_syllables.py "<line>" "<source_lang>"
```
Record the target syllable counts.

### Phase 1: Initial Translation

Translate all lines at once. Each line must have EXACTLY the target syllable count. Keep the meaning and the emotion of the source.

Rules for Chinese targets: one Han character is one syllable. Write only Han characters.

### Phase 2: Syllable Refinement

For each translated line:

1. Count its syllables:
   ```bash
   python skills/syllable-counter/scripts/count_syllables.py "<translation>" "<target_lang>"
   ```
2. If the count differs from the target, rewrite the line (too long: remove modifiers, use shorter words; too short: add descriptive words). Count again after each rewrite. Stop after 10 attempts and keep the closest attempt.

### Final Validation

```bash
python skills/lyrics-validator/scripts/validate.py "<target_lang>" '[10, 9, 6, 6, 5]' "<line1>" "<line2>" ...
```
If `syllables_match` is false, return to Phase 2 for the failing lines.

## Output Format

Return only the final translation:

```
1. <translated line 1>
2. <translated line 2>
...
```
