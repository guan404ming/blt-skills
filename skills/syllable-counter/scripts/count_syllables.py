"""CLI for syllable counting."""

import sys
from blt_skills import count_syllables

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python count_syllables.py <text> <language>")
        sys.exit(1)

    text = sys.argv[1]
    lang = sys.argv[2]
    count = count_syllables(text, lang)
    print(f"Syllables: {count}")
