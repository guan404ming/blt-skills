---
name: lyrics-translator-prompt-only
description: Ablation variant of lyrics-translator with no scripts. Count syllables and judge rhyme in your own reasoning. Use only when explicitly asked for the prompt-only ablation.
---

# Lyrics Translator (prompt-only ablation)

Translate lyrics between languages so the translation stays singable. No scripts or tools are available. Do all counting and rhyme analysis yourself, in your reasoning. Do not try to run commands, read files, or launch agents.

## Workflow

### Step 0: Extract Constraints

For each source line, count its syllables yourself. Write the counts down. Then decide the rhyme scheme (label lines that end in the same sound with the same letter, e.g. ABCCD).

### Phase 1: Initial Translation

Translate all lines at once:

- Each line must have EXACTLY the source syllable count.
- Lines that share a rhyme label must rhyme in the target language. Lines with different labels must not rhyme.
- Keep the meaning and the emotion of the source.

Rules for Chinese targets: one Han character is one syllable. Write only Han characters.

### Phase 2: Syllable Refinement

For each translated line, count its syllables yourself. If the count differs from the target, rewrite the line (too long: remove modifiers, use shorter words; too short: add descriptive words) and count again. Stop after 10 attempts and keep the closest attempt.

### Final Check

Re-count every line and check the rhyme scheme yourself. Fix lines that break the scheme while keeping their counts.

## Output Format

Return only the final translation:

```
1. <translated line 1>
2. <translated line 2>
...
```
