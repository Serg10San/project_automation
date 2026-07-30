"""
Report formatter — console (with optional color) and JSON/CSV output.
"""

import json
import csv
import io
from collections import defaultdict
from .scanner import SkillEvidence

# ANSI color codes (disabled automatically when not a TTY)
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_GREEN  = "\033[32m"
_BLUE   = "\033[34m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_DIM    = "\033[2m"
_RED    = "\033[31m"

LEVEL_COLORS = {
    "Teaching":     _GREEN + _BOLD,
    "Applied":      _GREEN,
    "Practiced":    _CYAN,
    "Aware":        _YELLOW,
    "Not Detected": _DIM,
}

LEVEL_ICONS = {
    "Teaching":     "★",
    "Applied":      "✅",
    "Practiced":    "🔵",
    "Aware":        "○",
    "Not Detected": "–",
}


def _colorize(text: str, code: str, use_color: bool) -> str:
    return f"{code}{text}{_RESET}" if use_color else text


def print_console_report(
    evidence_list: list[SkillEvidence],
    stats: dict,
    verbose: bool = False,
    use_color: bool = True,
) -> None:
    """Print a human-readable skills assessment to stdout."""
    # Group by domain
    by_domain: dict[str, list[SkillEvidence]] = defaultdict(list)
    for ev in evidence_list:
        by_domain[ev.domain].append(ev)

    # Summary counts
    level_counts: dict[str, int] = defaultdict(int)
    for ev in evidence_list:
        level_counts[ev.level] += 1

    # --- Header ---
    header = "SKILL MATURITY ASSESSMENT — CODEBASE EVIDENCE REPORT"
    print()
    print(_colorize(header, _BOLD, use_color))
    print("─" * len(header))
    print(f"Scanned : {stats['scan_path']}")
    print(f"Files   : {stats['total_files']}")
    print(f"Types   : {', '.join(stats['extensions'][:12])}")
    print()
    print(_colorize(
        "NOTE: Levels reflect evidence found in this codebase, not an absolute personal skill score.",
        _DIM, use_color
    ))
    print()

    # --- Domain sections ---
    for domain, skill_list in by_domain.items():
        print(_colorize(f"  {domain}", _BOLD + _BLUE, use_color))
        print(_colorize("  " + "─" * (len(domain) + 2), _DIM, use_color))

        for ev in sorted(skill_list, key=lambda e: -e.level_num):
            icon  = LEVEL_ICONS[ev.level]
            color = LEVEL_COLORS[ev.level]
            level_str = ev.level.ljust(13)
            name_str  = ev.skill_name

            detail = (
                f"{ev.file_count} file{'s' if ev.file_count != 1 else ''}, "
                f"{ev.project_count} project{'s' if ev.project_count != 1 else ''}, "
                f"{len(ev.matched_indicator_names)}/{ev.total_indicators} indicators"
            )

            line = f"    {icon}  {_colorize(level_str, color, use_color)}  {name_str}"
            print(line)
            print(f"         {_colorize(detail, _DIM, use_color)}")

            if verbose and ev.sample_matches:
                for sample in ev.sample_matches[:2]:
                    print(f"         {_colorize('→ ' + sample, _DIM, use_color)}")

        print()

    # --- Summary table ---
    print(_colorize("  SUMMARY", _BOLD, use_color))
    print("  " + "─" * 46)
    order = ["Teaching", "Applied", "Practiced", "Aware", "Not Detected"]
    for level in order:
        count = level_counts.get(level, 0)
        if count == 0 and level == "Not Detected":
            continue
        bar = "█" * count
        color = LEVEL_COLORS[level]
        print(f"  {_colorize(level.ljust(14), color, use_color)}  {bar}  {count}")
    print()

    detected = sum(level_counts.get(l, 0) for l in ["Teaching", "Applied", "Practiced", "Aware"])
    total    = len(evidence_list)
    print(f"  Skills with evidence: {detected}/{total}")
    print()


def to_json(evidence_list: list[SkillEvidence], stats: dict) -> str:
    """Serialize results to JSON string."""
    data = {
        "scan_stats": stats,
        "results": [
            {
                "domain": ev.domain,
                "skill": ev.skill_name,
                "level": ev.level,
                "level_num": ev.level_num,
                "indicators_matched": sorted(ev.matched_indicator_names),
                "indicator_coverage": f"{len(ev.matched_indicator_names)}/{ev.total_indicators}",
                "file_count": ev.file_count,
                "project_count": ev.project_count,
                "has_teaching_evidence": ev.has_teaching_evidence,
                "sample_matches": ev.sample_matches,
            }
            for ev in evidence_list
        ],
    }
    return json.dumps(data, indent=2)


def to_csv(evidence_list: list[SkillEvidence]) -> str:
    """Serialize results to CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Domain", "Skill", "Level", "Level_Num",
        "Indicators_Matched", "Total_Indicators", "Files", "Projects",
        "Teaching_Evidence",
    ])
    for ev in evidence_list:
        writer.writerow([
            ev.domain, ev.skill_name, ev.level, ev.level_num,
            len(ev.matched_indicator_names), ev.total_indicators,
            ev.file_count, ev.project_count,
            ev.has_teaching_evidence,
        ])
    return buf.getvalue()
