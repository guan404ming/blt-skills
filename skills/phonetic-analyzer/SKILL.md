---
name: phonetic-analyzer
description: Convert text to IPA (International Phonetic Alphabet) and calculate phonetic similarity between texts. Use when analyzing pronunciation, comparing sounds across languages, or checking phonetic distance.
---

# Phonetic Analyzer

Convert text to IPA transcription and measure phonetic similarity.

## Tools

Run scripts from this skill's `scripts/` directory using the shared `.venv`:

### text_to_ipa

```bash
python skills/phonetic-analyzer/scripts/phonetic_analysis.py "<text>" "<language>"
```

Returns the IPA transcription of the input text.

### calculate_ipa_similarity

```bash
python skills/phonetic-analyzer/scripts/phonetic_analysis.py "<text1>" "<language>" "<text2>"
```

Returns IPA for both texts and a similarity score (0.0 to 1.0).

## Supported Languages

- `en-us`, `en` - English
- `cmn`, `zh`, `zh-cn`, `zh-tw` - Chinese (Mandarin)
- `ja` - Japanese
- Any language supported by espeak

## Notes

- Uses phonemizer with espeak backend for IPA conversion.
- Similarity uses panphon feature-based edit distance.
- For Chinese, set `is_chinese=True` to convert via pinyin first.
