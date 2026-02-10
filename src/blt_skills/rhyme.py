"""Rhyme analysis: ending extraction, rhyme checking, scheme detection."""

from __future__ import annotations

import re

from .phonetics import IPA_VOWEL_PATTERN, normalize_language_code, phonemize_text


def extract_rhyme_ending(text: str, language: str) -> str:
    """Extract the rhyme ending from text.

    For Chinese, returns the pinyin final of the last character.
    For other languages, returns IPA from the last vowel onward.

    Args:
        text: Text to analyze.
        language: Language code.

    Returns:
        Rhyme ending string.
    """
    language = normalize_language_code(language)
    text = text.strip()
    if not text:
        return ""

    if language == "cmn":
        from pypinyin import Style, pinyin

        finals = pinyin(text, style=Style.FINALS, strict=False)
        if finals and finals[-1]:
            return finals[-1][0]
        return text

    ipa_text = phonemize_text(text, language)
    vowel_matches = list(re.finditer(IPA_VOWEL_PATTERN, ipa_text))
    if not vowel_matches:
        return ""

    last_vowel_pos = vowel_matches[-1].start()
    return ipa_text[last_vowel_pos:]


def check_rhyme(text1: str, text2: str, language: str) -> bool:
    """Check if two texts rhyme.

    Args:
        text1: First text.
        text2: Second text.
        language: Language code.

    Returns:
        True if texts rhyme.
    """
    rhyme1 = extract_rhyme_ending(text1, language)
    rhyme2 = extract_rhyme_ending(text2, language)
    if not rhyme1 or not rhyme2:
        return False
    return rhyme1 == rhyme2 or rhyme1 in rhyme2 or rhyme2 in rhyme1


def detect_rhyme_scheme(lines: list[str], language: str) -> str:
    """Detect the rhyme scheme from a list of lines.

    Args:
        lines: List of text lines.
        language: Language code.

    Returns:
        Rhyme scheme string (e.g., "AABB", "ABAB").
    """
    if len(lines) < 2:
        return "A"

    rhyme_endings = [extract_rhyme_ending(line, language) for line in lines]

    scheme = []
    rhyme_map: dict[str, str] = {}
    current_label = ord("A")

    for ending in rhyme_endings:
        if ending in rhyme_map:
            scheme.append(rhyme_map[ending])
        else:
            label = chr(current_label)
            rhyme_map[ending] = label
            scheme.append(label)
            current_label += 1

    return "".join(scheme)
