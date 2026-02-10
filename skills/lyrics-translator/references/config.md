# Configuration Reference

## Supported Languages

| Code | Language |
|------|----------|
| `en-us`, `en` | English |
| `cmn`, `zh`, `zh-cn`, `zh-tw` | Chinese (Mandarin) |
| `ja` | Japanese |
| `ko` | Korean |
| `es` | Spanish |
| `fr` | French |
| `de` | German |

## Defaults

- Source language: `en-us`
- Target language: `cmn`
- Max refinement attempts per line: 10
- Pattern similarity skip threshold: 75%
- Minimum pattern improvement threshold: 15%

## Chinese-Specific Rules

- Each Chinese character = 1 syllable.
- Strip all punctuation and whitespace before counting: `，。；！？、`
- Word segmentation uses jieba.
- Rhyme endings use pypinyin finals (yunmu).
