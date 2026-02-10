"""CLI for syllable pattern analysis."""

import sys
from blt_skills import get_syllable_patterns

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python pattern_analysis.py <language> <line1> [line2] ...")
        sys.exit(1)

    lang = sys.argv[1]
    lines = sys.argv[2:]
    patterns = get_syllable_patterns(lines, lang)
    for i, (line, pattern) in enumerate(zip(lines, patterns), 1):
        print(f"Line {i}: {pattern} (total: {sum(pattern)}) - \"{line}\"")
