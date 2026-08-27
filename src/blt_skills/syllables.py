"""Syllable counting using IPA-based analysis."""

from __future__ import annotations

import re

from .phonetics import IPA_DIPHTHONG_PATTERN, normalize_language_code, phonemize_text

# Small kana that combine with the preceding kana and do not add a mora.
_JA_SMALL_KANA = set("ゃゅょぁぃぅぇぉャュョァィゥェォ")
_PUNCT = r"[,;.!?，。；！？、、\"'“”‘’()（）\[\]【】…—-]+"
_HAN = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")
_LATIN_RUN = re.compile(r"[A-Za-z][A-Za-z']*")
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

    For Chinese, each Han character counts as one syllable; embedded Latin words are counted via IPA.
    For Japanese, mora count via pykakasi.
    For other languages, uses IPA vowel nuclei detection.

    Args:
        text: Text to analyze.
        language: Language code (e.g., 'en-us', 'cmn', 'ja').

    Returns:
        Number of syllables.
    """
    language = normalize_language_code(language)
    cleaned = re.sub(_PUNCT, "", text)
    if language == "cmn":
        return _count_cmn(cleaned)
    if language == "ja":
        return _count_ja_mora(re.sub(r"\s+", "", cleaned))
    return _count_ipa_nuclei(cleaned, language)


def _count_ipa_nuclei(text: str, language: str) -> int:
    text = text.strip()
    if not text:
        return 0
    return len(re.findall(IPA_DIPHTHONG_PATTERN, phonemize_text(text, language)))


def _count_cmn(text: str) -> int:
    han = len(_HAN.findall(text))
    latin = " ".join(_LATIN_RUN.findall(text))
    return han + (_count_ipa_nuclei(latin, "en-us") if latin else 0)
