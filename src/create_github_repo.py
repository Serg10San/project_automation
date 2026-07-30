"""Automate creation of a public GitHub repository with a Python .gitignore template.

Wraps the GitHub CLI (`gh repo create`) so repo creation is scriptable and
repeatable. Requires `gh` to be installed and authenticated (`gh auth login`).

Usage:
    python src/create_github_repo.py my-new-repo
    python src/create_github_repo.py my-new-repo --description "My project" --clone
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a public GitHub repository with a Python .gitignore."
    )
    parser.add_argument(
        "name",
        help="Repository name, or 'owner/name' to create under an org/user.",
    )
    parser.add_argument("--description", "-d", default=None, help="Repository description.")
    parser.add_argument(
        "--clone",
        action="store_true",
        help="Clone the repository locally after creation.",
    )
    return parser.parse_args(argv)


def check_gh_available() -> None:
    if shutil.which("gh") is None:
        raise SystemExit(
            "GitHub CLI ('gh') not found on PATH. Install it from https://cli.github.com/ "
            "and run 'gh auth login' before using this script."
        )


def check_gh_authenticated() -> None:
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            "GitHub CLI is not authenticated. Run 'gh auth login' first.\n"
            f"{result.stderr.strip()}"
        )


def create_repo(name: str, description: str | None, clone: bool) -> None:
    cmd = ["gh", "repo", "create", name, "--public", "--gitignore", "Python"]
    if description:
        cmd += ["--description", description]
    if clone:
        cmd.append("--clone")

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"Repo creation failed with exit code {result.returncode}.")
    print(f"Repository '{name}' created successfully (public, Python .gitignore).")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    check_gh_available()
    check_gh_authenticated()
    create_repo(args.name, args.description, args.clone)


if __name__ == "__main__":
    main(sys.argv[1:])
