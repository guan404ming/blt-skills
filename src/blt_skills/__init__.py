"""blt-skills: lyrics analysis utilities."""

from .phonetics import text_to_ipa, calculate_ipa_similarity, normalize_language_code
from .syllables import count_syllables
from .rhyme import extract_rhyme_ending, check_rhyme, detect_rhyme_scheme
from .patterns import (
    segment_words,
    get_syllable_patterns,
    analyze_pattern_alignment,
    score_syllable_patterns,
)
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
