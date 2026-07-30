"""
Skills loader — merges built-in skills (registry.py) with any YAML skill
definitions found in this directory (src/skills/).

YAML skill format
─────────────────
Each YAML file must contain a top-level ``skill:`` key:

    skill:
      name: "My Skill Name"
      domain: "My Domain"
      description: "Optional human-readable description."
      indicators:
        - name: "indicator label"
          description: "Optional."
          patterns:
            - "regex_pattern_1"
            - "regex_pattern_2"
          globs:
            - "*.py"
            - "*.yaml"
          is_teaching: false      # optional; marks teaching-level evidence

        - name: "file existence check"
          existence_globs:
            - "agent_manifest.yaml"

Portability
───────────
A skill YAML is a self-contained, shareable artefact.  To share a skill:

  1. Copy the YAML file to another project's ``src/skills/`` directory.
  2. Run ``python assess_skills.py`` — the skill is automatically discovered.

No code changes needed.  No re-installation needed.

Standalone repo vs. Python template
─────────────────────────────────────
- **This template** is sufficient for internal sharing and team workflows.
- Create a **standalone GitHub repo** when you want to:
    * ``pip install`` the skill package from CI/CD pipelines.
    * Publish skill YAMLs to a shared catalogue for cross-team use.
    * Version and release skills independently.
  A standalone repo only needs a ``pyproject.toml``, the YAML files, and a
  thin ``load_skills()`` shim — no scanner code required.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from .registry import BUILTIN_SKILLS

_SKILLS_DIR = Path(__file__).parent


def load_yaml_skills(directory: Path | None = None) -> list[dict]:
    """Load all ``*.yaml`` / ``*.yml`` skill files from *directory*.

    Each file must have a top-level ``skill:`` key.  Files that do not
    match the expected schema are skipped with a warning.

    Args:
        directory: Folder to scan.  Defaults to ``src/skills/``.

    Returns:
        List of skill dicts in the same format as BUILTIN_SKILLS.
    """
    directory = directory or _SKILLS_DIR
    skills: list[dict] = []

    for path in sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            print(f"[skills.loader] WARNING: could not parse {path.name}: {exc}", file=sys.stderr)
            continue

        if not isinstance(raw, dict) or "skill" not in raw:
            continue  # not a skill definition file

        skill_data = raw["skill"]
        if not isinstance(skill_data, dict):
            print(f"[skills.loader] WARNING: {path.name} 'skill:' is not a mapping — skipped.", file=sys.stderr)
            continue

        required = {"name", "domain", "indicators"}
        missing = required - set(skill_data.keys())
        if missing:
            print(
                f"[skills.loader] WARNING: {path.name} missing required keys {missing} — skipped.",
                file=sys.stderr,
            )
            continue

        # Normalise indicators: convert list-style patterns to the format
        # expected by CodeScanner (list[str]).
        indicators: list[dict] = []
        for ind in skill_data.get("indicators", []):
            normalised: dict = {"name": ind["name"]}
            if "patterns" in ind:
                normalised["patterns"] = ind["patterns"]
            if "globs" in ind:
                normalised["globs"] = ind["globs"]
            if "existence_globs" in ind:
                normalised["existence_globs"] = ind["existence_globs"]
            if ind.get("is_teaching"):
                normalised["is_teaching"] = True
            indicators.append(normalised)

        skills.append(
            {
                "domain": skill_data["domain"],
                "name": skill_data["name"],
                "indicators": indicators,
            }
        )

    return skills


def load_skills(extra_dir: Path | None = None) -> list[dict]:
    """Return merged skill list: built-in registry + YAML-defined skills.

    Deduplicates by ``(domain, name)`` — YAML skills override built-in
    entries with the same key so you can customise built-in skills by
    dropping a YAML file with the same name.

    Args:
        extra_dir: Additional directory to scan for YAML skills.

    Returns:
        Deduplicated, merged list of skill dicts.
    """
    all_skills: dict[tuple[str, str], dict] = {}

    # 1. Built-ins first (lowest priority)
    for skill in BUILTIN_SKILLS:
        key = (skill["domain"], skill["name"])
        all_skills[key] = skill

    # 2. YAML skills from src/skills/ — override built-ins with same key
    for skill in load_yaml_skills(_SKILLS_DIR):
        key = (skill["domain"], skill["name"])
        all_skills[key] = skill

    # 3. Optional extra directory (e.g. user-supplied paths at runtime)
    if extra_dir:
        for skill in load_yaml_skills(extra_dir):
            key = (skill["domain"], skill["name"])
            all_skills[key] = skill

    return list(all_skills.values())
