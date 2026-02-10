"""Syllable counting using IPA-based analysis."""

from __future__ import annotations

import re

from .phonetics import IPA_DIPHTHONG_PATTERN, normalize_language_code, phonemize_text


def count_syllables(text: str, language: str) -> int:
    """Count syllables in text.

    For Chinese, each character counts as one syllable.
    For other languages, uses IPA vowel nuclei detection.

    Args:
        text: Text to analyze.
        language: Language code (e.g., 'en-us', 'cmn').

    Returns:
        Number of syllables.
    """
    language = normalize_language_code(language)
    cleaned = re.sub(r"[,;.!?，。；！？、\s]+", "", text)
    if not cleaned:
        return 0

    if language == "cmn":
        return len(cleaned)

    ipa_text = phonemize_text(cleaned, language)
    nuclei = re.findall(IPA_DIPHTHONG_PATTERN, ipa_text)
    return len(nuclei)
