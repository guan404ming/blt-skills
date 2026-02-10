"""CLI for phonetic analysis."""

import sys
from blt_skills import text_to_ipa, calculate_ipa_similarity

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python phonetic_analysis.py <text> <language> [text2]")
        sys.exit(1)

    text = sys.argv[1]
    lang = sys.argv[2]

    ipa = text_to_ipa(text, lang)
    print(f"IPA: {ipa}")

    if len(sys.argv) >= 4:
        text2 = sys.argv[3]
        ipa2 = text_to_ipa(text2, lang)
        sim = calculate_ipa_similarity(ipa, ipa2)
        print(f"IPA2: {ipa2}")
        print(f"Similarity: {sim:.3f}")
