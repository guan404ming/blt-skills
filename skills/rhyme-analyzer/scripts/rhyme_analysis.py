"""CLI for rhyme analysis."""

import sys
from blt_skills import extract_rhyme_ending, check_rhyme

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python rhyme_analysis.py <text> <language> [text2]")
        sys.exit(1)

    text = sys.argv[1]
    lang = sys.argv[2]
    ending = extract_rhyme_ending(text, lang)
    print(f"Rhyme ending: {ending}")

    if len(sys.argv) >= 4:
        text2 = sys.argv[3]
        rhymes = check_rhyme(text, text2, lang)
        print(f"Rhymes: {rhymes}")
