"""CLI for lyrics validation."""

import json
import sys
from blt_skills import verify_all_constraints

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python validate.py <language> <target_syllables_json> <line1> [line2] ...")
        print("Example: python validate.py cmn '[5,7,5]' line1 line2 line3")
        sys.exit(1)

    lang = sys.argv[1]
    target = json.loads(sys.argv[2])
    lines = sys.argv[3:]

    result = verify_all_constraints(lines, lang, target)
    print(json.dumps(result, ensure_ascii=False, indent=2))
