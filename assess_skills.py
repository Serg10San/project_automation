#!/usr/bin/env python3
"""
assess_skills.py — Scan a codebase and report skill maturity evidence.

Automatically discovers all skills:
  • Built-in skills from src/skills/registry.py
  • Any *.yaml / *.yml skill files in src/skills/
  • Optional extra skills directory via --skills-dir

Usage:
    python assess_skills.py [PATH] [OPTIONS]

Arguments:
    PATH            Directory to scan (default: parent of this script)

Options:
    -v, --verbose       Show sample code matches for each skill
    --json              Output raw JSON instead of console report
    --csv               Output CSV instead of console report
    --no-color          Disable ANSI color codes
    --domain DOMAIN     Filter to a specific domain (partial, case-insensitive)
    --min-level LEVEL   Only show skills at or above this level
                        (aware | practiced | applied | teaching)
    --skills-dir DIR    Load additional YAML skills from DIR
    --list-skills       Print discovered skill names and exit

Examples:
    python assess_skills.py
    python assess_skills.py C:/scripts/ai_scripts --verbose
    python assess_skills.py --domain "governance"
    python assess_skills.py --domain "singapore"
    python assess_skills.py --min-level applied
    python assess_skills.py --json > results.json
    python assess_skills.py --csv  > results.csv
    python assess_skills.py --list-skills
"""

import argparse
import sys
import os
from pathlib import Path

# ── path bootstrap ────────────────────────────────────────────────────────────
# Allow running from any working directory: add src/ to sys.path so that
# ``from skills_engine import ...`` and ``from skills import ...`` work.
_HERE = Path(__file__).resolve().parent
_SRC = _HERE / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from skills_engine.scanner import CodeScanner
from skills_engine.report import print_console_report, to_json, to_csv
from skills.loader import load_skills

_LEVEL_ORDER = {"not detected": 0, "aware": 1, "practiced": 2, "applied": 3, "teaching": 4}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan a codebase and report skill maturity evidence.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    default_path = str(_HERE.parent)
    parser.add_argument(
        "path",
        nargs="?",
        default=default_path,
        help=f"Directory to scan (default: {default_path})",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show sample matches")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--csv", action="store_true", dest="csv_out", help="Output CSV")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    parser.add_argument("--domain", default="", help="Filter by domain (partial, case-insensitive)")
    parser.add_argument(
        "--min-level",
        default="",
        choices=["aware", "practiced", "applied", "teaching"],
        metavar="LEVEL",
        help="Minimum level to display (aware|practiced|applied|teaching)",
    )
    parser.add_argument(
        "--skills-dir",
        default="",
        metavar="DIR",
        help="Load additional YAML skill definitions from this directory",
    )
    parser.add_argument(
        "--list-skills",
        action="store_true",
        help="Print discovered skill names and domains, then exit",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    extra_dir = Path(args.skills_dir).resolve() if args.skills_dir else None
    skills = load_skills(extra_dir=extra_dir)

    if args.list_skills:
        print(f"\nDiscovered {len(skills)} skill(s):\n")
        from collections import defaultdict
        by_domain: dict[str, list[str]] = defaultdict(list)
        for s in skills:
            by_domain[s["domain"]].append(s["name"])
        for domain, names in sorted(by_domain.items()):
            print(f"  {domain}")
            for name in sorted(names):
                print(f"    • {name}")
        print()
        return

    # Apply domain filter
    if args.domain:
        skills = [s for s in skills if args.domain.lower() in s["domain"].lower()
                  or args.domain.lower() in s["name"].lower()]
        if not skills:
            print(f"No skills found for domain filter: '{args.domain}'", file=sys.stderr)
            sys.exit(1)

    scan_path = Path(args.path).resolve()
    if not scan_path.exists():
        print(f"ERROR: Path not found: {scan_path}", file=sys.stderr)
        sys.exit(1)
    if not scan_path.is_dir():
        print(f"ERROR: Not a directory: {scan_path}", file=sys.stderr)
        sys.exit(1)

    scanner = CodeScanner(str(scan_path))
    evidence_list, stats = scanner.scan_all(skills)

    # Apply min-level filter
    if args.min_level:
        min_num = _LEVEL_ORDER[args.min_level.lower()]
        evidence_list = [e for e in evidence_list if e.level_num >= min_num]

    use_color = not args.no_color and sys.stdout.isatty()

    if args.json:
        print(to_json(evidence_list, stats))
    elif args.csv_out:
        print(to_csv(evidence_list))
    else:
        print_console_report(evidence_list, stats, verbose=args.verbose, use_color=use_color)


if __name__ == "__main__":
    main()
