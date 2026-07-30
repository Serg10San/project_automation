"""
weekly_report.py — generate the WW##-SergioSanchez-Weekly.md SRE status
report and distribute it (SharePoint upload + email).

Runs Monday-through-Friday analysis of SRE initiative activity and produces
3 evidence-backed bullets. Designed to run unattended every Friday at noon
via a Windows Scheduled Task (see docs/knowledge/weekly-report-automation.md).

Data sources (no new Graph API consent required):
  1. Git commit history in the source SRE repo (default:
     C:\\scripts\\ire-sergio-analytics, override with WEEKLY_SOURCE_REPO)
  2. Files created/modified in that repo's working tree this week
  3. Outlook desktop calendar (this week's meetings) via COM automation
  4. Outlook desktop Sent Items (this week's outgoing email) via COM automation

Signals are grouped into SRE initiative themes (deep-dive RCA, toil &
automation, proactive alerting, disaster recovery, incident analysis,
predictive/ML, skills & governance). The 3 themes with the most activity
this week become the report's 3 bullets, each citing concrete evidence
(a commit subject, filename, or meeting/email subject) rather than
free-form generated text — no LLM is used, so results are reproducible
and auditable.

Usage
-----
    python -m src.tools.weekly_report
    python -m src.tools.weekly_report --dry-run   # skip upload + email
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from src.tools.sharepoint_upload import SharePointUploadError, upload_file

REPORT_AUTHOR = "SergioSanchez"

# Theme name -> keywords matched (case-insensitive) against commit subjects,
# filenames, meeting subjects, and email subjects.
THEMES: dict[str, list[str]] = {
    "Deep-Dive RCA & Incident Analysis": [
        "deep_dive",
        "deep-dive",
        "rca",
        "incident",
        "inc1",
        "p1",
        "p2",
        "mh_",
    ],
    "Toil Reduction & Automation": [
        "toil",
        "automation",
        "auto_close",
        "auto-close",
    ],
    "Proactive Alerting & Repeat Detection": [
        "proactive",
        "alert",
        "repeat",
    ],
    "Disaster Recovery & Resiliency": [
        "disaster",
        "_dr_",
        "dr plan",
        "dr_plan",
        "hadr",
        "drill",
        "resiliency",
    ],
    "Predictive / ML Modeling": [
        "predict",
        "model",
        " ml ",
        "similarity",
    ],
    "Skills & Governance": [
        "skills",
        "governance",
        "compliance",
    ],
}


@dataclass
class Signal:
    theme: str
    kind: str  # "commit" | "file" | "meeting" | "email"
    evidence: str
    when: datetime


@dataclass
class WeekWindow:
    start: datetime
    end: datetime
    week_number: int

    @classmethod
    def current(cls, now: datetime | None = None) -> WeekWindow:
        now = now or datetime.now()
        monday = now - timedelta(days=now.weekday())
        start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=4, hours=12)  # Friday 12:00 noon
        return cls(start=start, end=end, week_number=now.isocalendar()[1])


def _match_theme(text: str) -> str | None:
    lowered = text.lower()
    for theme, keywords in THEMES.items():
        if any(kw in lowered for kw in keywords):
            return theme
    return None


def collect_git_signals(repo_path: Path, window: WeekWindow) -> list[Signal]:
    """Collect commit-subject signals from the SRE source repo this week."""
    if not (repo_path / ".git").exists():
        return []

    since = window.start.strftime("%Y-%m-%d %H:%M:%S")
    until = window.end.strftime("%Y-%m-%d %H:%M:%S")
    result = subprocess.run(
        [
            "git",
            "log",
            f"--since={since}",
            f"--until={until}",
            "--pretty=format:%ad|%s",
            "--date=iso-strict",
        ],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    signals: list[Signal] = []
    for line in result.stdout.splitlines():
        if "|" not in line:
            continue
        when_str, subject = line.split("|", 1)
        theme = _match_theme(subject)
        if theme:
            when = datetime.fromisoformat(when_str.replace("Z", "+00:00")).replace(tzinfo=None)
            signals.append(Signal(theme=theme, kind="commit", evidence=subject.strip(), when=when))
    return signals


def collect_file_signals(repo_path: Path, window: WeekWindow) -> list[Signal]:
    """Collect signals from files modified in the repo's working tree this week."""
    signals: list[Signal] = []
    if not repo_path.is_dir():
        return signals

    skip_dirs = {
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".code-review-graph",
    }
    for path in repo_path.rglob("*"):
        if not path.is_file() or any(part in skip_dirs for part in path.parts):
            continue
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            continue
        if not (window.start <= mtime <= window.end):
            continue
        theme = _match_theme(path.name)
        if theme:
            signals.append(Signal(theme=theme, kind="file", evidence=path.name, when=mtime))
    return signals


def collect_outlook_signals(window: WeekWindow) -> list[Signal]:
    """
    Collect calendar meeting + Sent Items email subjects this week via the
    local Outlook desktop client (COM automation). Returns an empty list
    (rather than raising) if Outlook isn't installed/running — this data
    source is best-effort.
    """
    signals: list[Signal] = []
    try:
        import win32com.client
    except ImportError:
        return signals

    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")

        # Calendar — olFolderCalendar = 9
        calendar = namespace.GetDefaultFolder(9).Items
        calendar.Sort("[Start]")
        calendar.IncludeRecurrences = True
        restriction = (
            f"[Start] >= '{window.start.strftime('%m/%d/%Y %H:%M %p')}' AND "
            f"[Start] <= '{window.end.strftime('%m/%d/%Y %H:%M %p')}'"
        )
        for item in calendar.Restrict(restriction):
            theme = _match_theme(item.Subject or "")
            if theme:
                signals.append(
                    Signal(theme=theme, kind="meeting", evidence=item.Subject, when=window.start)
                )

        # Sent Items — olFolderSentMail = 5
        sent = namespace.GetDefaultFolder(5).Items
        sent.Sort("[SentOn]")
        restriction = (
            f"[SentOn] >= '{window.start.strftime('%m/%d/%Y %H:%M %p')}' AND "
            f"[SentOn] <= '{window.end.strftime('%m/%d/%Y %H:%M %p')}'"
        )
        for item in sent.Restrict(restriction):
            theme = _match_theme(getattr(item, "Subject", "") or "")
            if theme:
                signals.append(
                    Signal(theme=theme, kind="email", evidence=item.Subject, when=window.start)
                )
    except Exception as exc:  # pragma: no cover - COM failures vary by environment
        print(f"Warning: Outlook COM signal collection failed ({exc}); continuing without it.")

    return signals


def build_bullets(signals: list[Signal]) -> list[str]:
    """Rank themes by activity count and render the top 3 as evidence-backed bullets."""
    by_theme: dict[str, list[Signal]] = defaultdict(list)
    for sig in signals:
        by_theme[sig.theme].append(sig)

    ranked = sorted(by_theme.items(), key=lambda kv: len(kv[1]), reverse=True)[:3]

    bullets = []
    for theme, sigs in ranked:
        counts: dict[str, int] = defaultdict(int)
        for s in sigs:
            counts[s.kind] += 1
        count_str = ", ".join(f"{n} {kind}{'s' if n != 1 else ''}" for kind, n in counts.items())
        example = sorted(sigs, key=lambda s: s.when, reverse=True)[0].evidence
        bullets.append(f'**{theme}** — {count_str} this week (e.g., "{example}").')

    while len(bullets) < 3:
        bullets.append("_No detected activity in an additional theme this week._")

    return bullets


def render_report(window: WeekWindow, bullets: list[str]) -> str:
    date_range = f"{window.start:%Y-%m-%d} to {window.end:%Y-%m-%d}"
    lines = [
        f"# Weekly Status — WW{window.week_number:02d}",
        "",
        "**Author:** Sergio Sanchez",
        f"**Week:** {date_range}",
        "",
        "## SRE Initiatives This Week",
        "",
    ]
    lines += [f"- {bullet}" for bullet in bullets]
    lines += [
        "",
        "---",
        "*Auto-generated from git activity in ire-sergio-analytics, "
        "Outlook calendar, and Sent Items. No LLM used — themes are ranked "
        "by matched-keyword activity count for reproducibility.*",
    ]
    return "\n".join(lines) + "\n"


def send_email_via_outlook(subject: str, body: str, attachment_path: Path | None = None) -> None:
    """Send the report to the current Outlook user's own mailbox."""
    import win32com.client

    outlook = win32com.client.Dispatch("Outlook.Application")
    namespace = outlook.GetNamespace("MAPI")
    me = namespace.CurrentUser.AddressEntry.GetExchangeUser().PrimarySmtpAddress

    mail = outlook.CreateItem(0)  # olMailItem
    mail.To = me
    mail.Subject = subject
    mail.Body = body
    if attachment_path is not None:
        mail.Attachments.Add(str(attachment_path))
    mail.Send()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate the report file locally only; skip SharePoint upload and email",
    )
    args = parser.parse_args()

    load_dotenv()

    source_repo = Path(os.environ.get("WEEKLY_SOURCE_REPO", r"C:\scripts\ire-sergio-analytics"))
    window = WeekWindow.current()
    filename = f"WW{window.week_number:02d}-{REPORT_AUTHOR}-Weekly.md"

    signals = (
        collect_git_signals(source_repo, window)
        + collect_file_signals(source_repo, window)
        + collect_outlook_signals(window)
    )
    bullets = build_bullets(signals)
    content = render_report(window, bullets)

    out_dir = Path(__file__).resolve().parent.parent.parent / "docs" / "weeklies"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    out_path.write_text(content, encoding="utf-8")
    print(f"Report written: {out_path}")

    if args.dry_run:
        print("Dry run — skipping SharePoint upload and email.")
        return 0

    try:
        result = upload_file(out_path, filename)
        print(f"Uploaded: {result.get('webUrl', '(no webUrl)')}")
    except SharePointUploadError as exc:
        print(f"Warning: SharePoint upload failed: {exc}", file=sys.stderr)

    try:
        send_email_via_outlook(
            subject=f"Weekly SRE Report — WW{window.week_number:02d}",
            body=content,
            attachment_path=out_path,
        )
        print("Email sent via Outlook.")
    except Exception as exc:  # pragma: no cover - COM failures vary by environment
        print(f"Warning: Email send failed: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
