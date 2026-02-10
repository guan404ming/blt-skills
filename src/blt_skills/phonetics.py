"""IPA conversion and phonetic similarity."""

from __future__ import annotations

import logging
import re

import panphon.distance
from pypinyin import lazy_pinyin

_ft = panphon.distance.Distance()

IPA_VOWEL_PATTERN = (
    r"[iɪeɛæaäɑɒɔoʊuʉɨəɜɞʌyøœɶɐɚɝɯ]"
    r"[\u0300-\u036F\u1AB0-\u1AFF\u1DC0-\u1DFF\u20D0-\u20FF\uFE20-\uFE2F]*"
)

IPA_DIPHTHONG_PATTERN = (
    r"(?:aɪ|eɪ|ɔɪ|aʊ|oʊ|ɪə|eə|ʊə|aɪə|aʊə|"
    r"[iɪeɛæaäɑɒɔoʊuʉɨəɜɞʌyøœɶɐɚɝɯ]"
    r"[\u0300-\u036F\u1AB0-\u1AFF\u1DC0-\u1DFF\u20D0-\u20FF\uFE20-\uFE2F]*ː?)"
)


def normalize_language_code(lang: str) -> str:
    """Normalize language code to espeak-compatible format."""
    lang = lang.lower().strip()
    if lang in ("zh", "zh-cn", "zh-tw", "zh-hant", "chinese"):
        return "cmn"
    if lang in ("en", "en-us", "english"):
        return "en-gb"
    if lang in ("jp", "japanese"):
        return "ja"
    return lang


def phonemize_text(text: str, lang: str) -> str:
    """Convert text to IPA using phonemizer with fallback."""
    try:
        from phonemizer import phonemize

        return phonemize(text, language=lang, backend="espeak", strip=True)
    except Exception as e:
        if "-" in lang:
            try:
                from phonemizer import phonemize

                return phonemize(
                    text, language=lang.split("-")[0], backend="espeak", strip=True
                )
            except Exception:
                pass
        logging.debug("Could not phonemize text for language %s: %s", lang, e)
        return text


def text_to_ipa(text: str, language: str) -> str:
    """Convert text to IPA transcription.

    Args:
        text: Text to convert.
        language: Language code (e.g., 'en-us', 'cmn', 'ja').

    Returns:
        IPA transcription string.
    """
    language = normalize_language_code(language)
    cleaned = re.sub(r"[,;.!?，。；！？、]+", " ", text).strip()
    if not cleaned:
        return ""
    return phonemize_text(cleaned, language)


def calculate_ipa_similarity(
    ipa1: str, ipa2: str, is_chinese: bool = False
) -> float:
    """Calculate phonetic similarity between two IPA strings.

    Args:
        ipa1: First IPA string (or Chinese text if is_chinese).
        ipa2: Second IPA string (or Chinese text if is_chinese).
        is_chinese: Convert Chinese text to pinyin first.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    if not ipa1 and not ipa2:
        return 1.0
    if not ipa1 or not ipa2:
        return 0.0

    if is_chinese:
        ipa1 = " ".join(lazy_pinyin(ipa1))
        ipa2 = " ".join(lazy_pinyin(ipa2))

    ipa1 = ipa1.replace(" ", "").lower()
    ipa2 = ipa2.replace(" ", "").lower()

    if not ipa1:
        return 0.0 if ipa2 else 1.0
    if not ipa2:
        return 0.0

    distance = _ft.feature_edit_distance(ipa1, ipa2)
    max_len = max(len(ipa1), len(ipa2))
    similarity = 1.0 - (distance / max_len)
    return max(0.0, min(1.0, similarity))
