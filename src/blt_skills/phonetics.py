"""IPA conversion and phonetic similarity."""

from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path

import panphon.distance
from pypinyin import lazy_pinyin

_ft = panphon.distance.Distance()


def _ensure_espeak_library() -> None:
    """Locate libespeak-ng and expose it to phonemizer if not already set."""
    if os.environ.get("PHONEMIZER_ESPEAK_LIBRARY"):
        return
    candidates = [
        "/opt/homebrew/lib/libespeak-ng.dylib",
        "/opt/homebrew/lib/libespeak-ng.1.dylib",
        "/usr/local/lib/libespeak-ng.dylib",
        "/usr/local/lib/libespeak-ng.1.dylib",
        "/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1",
        "/usr/lib/libespeak-ng.so.1",
    ]
    for path in candidates:
        if Path(path).exists():
            os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = path
            return


_ensure_espeak_library()

# Espeak is not thread-safe; serialize all phonemize calls behind one lock and
# reuse one EspeakBackend per language to avoid repeated init deadlocks.
_backend_cache: dict[str, object] = {}
_backend_lock = threading.Lock()


def _phonemize_via_backend(text: str, lang: str) -> str:
    from phonemizer.backend import EspeakBackend

    with _backend_lock:
        be = _backend_cache.get(lang)
        if be is None:
            be = EspeakBackend(lang)
            _backend_cache[lang] = be
        return be.phonemize([text], strip=True)[0]


IPA_VOWEL_PATTERN = (
    r"[iɪeɛæaäɑɒɔoʊuʉɨəɜɞʌyøœɶɐɚɝɯ]"
    r"[\u0300-\u036F\u1AB0-\u1AFF\u1DC0-\u1DFF\u20D0-\u20FF\uFE20-\uFE2F]*"
)

IPA_DIPHTHONG_PATTERN = (
    r"(?:aɪə|aʊə|aɪ|eɪ|ɔɪ|aʊ|oʊ|əʊ|ɪə|eə|ɛə|ʊə|"
    r"[iɪeɛæaäɑɒɔoʊuʉɨəɜɞʌyøœɶɐɚɝɯ]"
    r"[\u0300-\u036F\u1AB0-\u1AFF\u1DC0-\u1DFF\u20D0-\u20FF\uFE20-\uFE2F]*ː?)"
)


def normalize_language_code(lang: str) -> str:
    """Normalize language code to espeak-compatible format."""
    lang = lang.lower().strip()
    if lang in ("zh", "zh-cn", "zh-tw", "zh-hant", "chinese"):
        return "cmn"
    if lang in ("en", "english"):
        return "en-us"
    if lang in ("jp", "japanese"):
        return "ja"
    return lang


def phonemize_text(text: str, lang: str) -> str:
    """Convert text to IPA via a cached, lock-protected EspeakBackend."""
    try:
        return _phonemize_via_backend(text, lang)
    except Exception as e:
        if "-" in lang:
            try:
                return _phonemize_via_backend(text, lang.split("-")[0])
            except Exception:
                pass
        logging.warning("Could not phonemize text for language %s: %s; using raw text", lang, e)
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


def calculate_ipa_similarity(ipa1: str, ipa2: str, is_chinese: bool = False) -> float:
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
