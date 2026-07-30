"""
hello.py — Entry point for project_automation.

Run this first to verify your environment is set up correctly.

Usage:
    .venv\\Scripts\\activate
    pip install -r requirements.txt
    # Edit .env directly and fill in any required values
    python hello.py
"""
from __future__ import annotations

import sys

from version import __version__, log_run


def main() -> None:
    # Ensure Unicode output works on Windows terminals (cp1252 can't encode ✅)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"\n  project_automation  v{__version__}")
    print("  Environment OK ✅\n")
    log_run("hello.py", "startup", "environment check passed", success=True)


if __name__ == "__main__":
    main()
