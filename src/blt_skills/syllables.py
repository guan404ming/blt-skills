"""Syllable counting using IPA-based analysis."""

from __future__ import annotations

import re

from .phonetics import IPA_DIPHTHONG_PATTERN, normalize_language_code, phonemize_text

# Small kana that combine with the preceding kana and do not add a mora.
_JA_SMALL_KANA = set("ゃゅょぁぃぅぇぉャュョァィゥェォ")
_kakasi = None


def _count_ja_mora(text: str) -> int:
    """Mora count for Japanese: kanji+kana -> katakana via pykakasi, then count
    kana excluding small-y/-vowel modifiers. Sokuon (っ) and chōonpu (ー) are
    moraic and counted; small ゃゅょぁぃぅぇぉ are not."""
    global _kakasi
    if _kakasi is None:
        import pykakasi
        _kakasi = pykakasi.kakasi()
    kana = "".join(item["kana"] for item in _kakasi.convert(text))
    return sum(1 for c in kana if c not in _JA_SMALL_KANA and not c.isspace())


def count_syllables(text: str, language: str) -> int:
    """Count syllables in text.

    For Chinese, each character counts as one syllable.
    For Japanese, mora count via pykakasi.
    For other languages, uses IPA vowel nuclei detection.

    Args:
        text: Text to analyze.
        language: Language code (e.g., 'en-us', 'cmn', 'ja').

    Returns:
        Number of syllables.
    """
    language = normalize_language_code(language)
    cleaned = re.sub(r"[,;.!?，。；！？、\s]+", "", text)
    if not cleaned:
        return 0

    if language == "cmn":
        return len(cleaned)
    if language == "ja":
        return _count_ja_mora(cleaned)

    ipa_text = phonemize_text(cleaned, language)
    nuclei = re.findall(IPA_DIPHTHONG_PATTERN, ipa_text)
    return len(nuclei)
