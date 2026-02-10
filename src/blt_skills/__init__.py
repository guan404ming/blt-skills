"""blt-skills: lyrics analysis utilities."""

from .patterns import (
    analyze_pattern_alignment,
    get_syllable_patterns,
    score_syllable_patterns,
    segment_words,
)
from .phonetics import calculate_ipa_similarity, normalize_language_code, text_to_ipa
from .rhyme import check_rhyme, detect_rhyme_scheme, extract_rhyme_ending
from .syllables import count_syllables
from .validator import verify_all_constraints

__all__ = [
    "normalize_language_code",
    "text_to_ipa",
    "calculate_ipa_similarity",
    "count_syllables",
    "extract_rhyme_ending",
    "check_rhyme",
    "detect_rhyme_scheme",
    "segment_words",
    "get_syllable_patterns",
    "analyze_pattern_alignment",
    "score_syllable_patterns",
    "verify_all_constraints",
]
