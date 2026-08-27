"""CLI for rhyme analysis."""

import sys

from blt_skills import check_rhyme, detect_rhyme_scheme, extract_rhyme_ending

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python rhyme_analysis.py <text> <language> [text2]")
        print("       python rhyme_analysis.py --scheme <language> <line1> <line2> ...")
        sys.exit(1)

    if sys.argv[1] == "--scheme":
        lang = sys.argv[2]
        lines = sys.argv[3:]
        print(f"Rhyme scheme: {detect_rhyme_scheme(lines, lang)}")
        for line in lines:
            print(f"  {extract_rhyme_ending(line, lang)}\t{line}")
        sys.exit(0)

    text = sys.argv[1]
    lang = sys.argv[2]
    ending = extract_rhyme_ending(text, lang)
    print(f"Rhyme ending: {ending}")

    if len(sys.argv) >= 4:
        text2 = sys.argv[3]
        rhymes = check_rhyme(text, text2, lang)
        print(f"Rhymes: {rhymes}")
