"""CLI for lyrics validation."""

import argparse
import json

from blt_skills import verify_all_constraints

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate translated lines against syllable, rhyme, and pattern constraints."
    )
    parser.add_argument("language")
    parser.add_argument("target_syllables", help="JSON list, e.g. '[5,7,5]'")
    parser.add_argument("lines", nargs="+")
    parser.add_argument("--rhyme", default="", help="Rhyme scheme, e.g. AABB")
    parser.add_argument("--patterns", default="", help="JSON list of lists, e.g. '[[2,1],[1,1,1]]'")
    args = parser.parse_args()

    result = verify_all_constraints(
        args.lines,
        args.language,
        json.loads(args.target_syllables),
        rhyme_scheme=args.rhyme,
        target_patterns=json.loads(args.patterns) if args.patterns else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
