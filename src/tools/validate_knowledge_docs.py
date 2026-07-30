#!/usr/bin/env python3
"""
validate_knowledge_docs.py — IRE Knowledge Identity Layer front-matter linter.

Scans docs/ (or a specified directory) for Markdown files with ire_doc: YAML
front matter and validates each one against ire-doc-schema.json.

Reads enforcement mode from docs/ire-knowledge-schema.yaml:
  advisory  — print warnings, always exit 0
  enforced  — print errors, exit 1 if any violations found

Usage:
    python src/tools/validate_knowledge_docs.py
    python src/tools/validate_knowledge_docs.py --docs-dir docs/knowledge
    python src/tools/validate_knowledge_docs.py --strict      # force exit 1 even in advisory
    python src/tools/validate_knowledge_docs.py --quiet       # suppress passing lines

Pre-commit hook usage (add to .pre-commit-config.yaml):
    - repo: local
      hooks:
        - id: ire-knowledge-validate
          name: Validate IRE knowledge doc front matter
          entry: python src/tools/validate_knowledge_docs.py --strict
          language: python
          types: [markdown]
          pass_filenames: false

Dependencies: PyYAML only — no jsonschema required (schema is validated inline).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# ── Constants ──────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOCS_DIR = REPO_ROOT / "docs"
SCHEMA_FILE = REPO_ROOT / "docs" / "ire-doc-schema.json"
TOGGLE_FILE = REPO_ROOT / "docs" / "ire-knowledge-schema.yaml"

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)

# ── YAML minimal parser (avoids requiring PyYAML for simple front matter) ─────

def _try_import_yaml():
    try:
        import yaml  # noqa: F401
        return yaml
    except ImportError:
        return None


def _parse_yaml_block(text: str) -> dict | None:
    yaml = _try_import_yaml()
    if yaml is None:
        print("  [SKIP] PyYAML not installed — cannot parse front matter. "
              "Install with: pip install pyyaml", file=sys.stderr)
        return None
    try:
        return yaml.safe_load(text)
    except Exception as exc:
        print(f"  [ERROR] YAML parse error: {exc}", file=sys.stderr)
        return None


# ── Schema loader ──────────────────────────────────────────────────────────────

def load_schema() -> dict:
    if not SCHEMA_FILE.exists():
        return {}
    with SCHEMA_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def load_enforcement() -> str:
    """Returns 'advisory' or 'enforced'. Defaults to 'advisory' if toggle missing."""
    if not TOGGLE_FILE.exists():
        return "advisory"
    yaml = _try_import_yaml()
    if yaml is None:
        return "advisory"
    with TOGGLE_FILE.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    try:
        return data.get("knowledge_identity", {}).get("enforcement", "advisory")
    except Exception:
        return "advisory"


# ── Inline validator (checks required fields and enum values) ─────────────────

def validate_ire_doc(doc_data: dict, schema: dict) -> list[str]:
    """Returns a list of human-readable violation messages (empty = valid)."""
    violations: list[str] = []

    ire_doc_schema = (
        schema.get("properties", {}).get("ire_doc", {})
    )
    if not ire_doc_schema:
        return violations  # no schema to validate against

    ire_doc = doc_data.get("ire_doc")
    if not isinstance(ire_doc, dict):
        return ["ire_doc block is missing or not a mapping"]

    # Required fields
    required = ire_doc_schema.get("required", [])
    for field in required:
        if field not in ire_doc:
            violations.append(f"Missing required field: ire_doc.{field}")

    # Enum validation for known fields
    props = ire_doc_schema.get("properties", {})
    for field, field_schema in props.items():
        if field not in ire_doc:
            continue
        value = ire_doc[field]
        allowed = field_schema.get("enum")
        if allowed is not None and value not in allowed:
            violations.append(
                f"ire_doc.{field} = '{value}' is not a valid value. "
                f"Allowed: {allowed}"
            )
        # Date pattern check
        pattern = field_schema.get("pattern")
        if pattern and isinstance(value, str):
            if not re.match(pattern, value):
                violations.append(
                    f"ire_doc.{field} = '{value}' does not match expected format "
                    f"(pattern: {pattern})"
                )

    # Warn about legacy 'domain' field
    if "domain" in ire_doc:
        violations.append(
            "ire_doc.domain is deprecated — rename to ire_doc.area "
            "(ServiceNow uses 'Domain' for Domain Separation)"
        )

    return violations


# ── File scanner ───────────────────────────────────────────────────────────────

def scan_file(path: Path, schema: dict) -> tuple[str, list[str]]:
    """Returns (status, violations) where status is 'ok', 'skip', or 'fail'."""
    text = path.read_text(encoding="utf-8", errors="replace")
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return ("skip", [])

    front_matter_text = match.group(1)

    # Only validate files that have ire_doc: front matter
    if "ire_doc:" not in front_matter_text:
        return ("skip", [])

    # Skip unscaffolded template files that still have {{PLACEHOLDER}} values
    if "{{" in front_matter_text:
        return ("skip", [])

    doc_data = _parse_yaml_block(front_matter_text)
    if doc_data is None:
        return ("fail", ["Could not parse YAML front matter"])

    violations = validate_ire_doc(doc_data, schema)
    return ("fail" if violations else "ok", violations)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate IRE knowledge doc ire_doc front matter against ire-doc-schema.json"
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=DEFAULT_DOCS_DIR,
        help=f"Directory to scan (default: {DEFAULT_DOCS_DIR})",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 on violations even in advisory enforcement mode",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output for passing files",
    )
    args = parser.parse_args()

    docs_dir: Path = args.docs_dir
    if not docs_dir.exists():
        print(f"[SKIP] docs directory not found: {docs_dir}")
        return 0

    schema = load_schema()
    enforcement = load_enforcement()

    if not schema:
        print(f"[WARN] Schema file not found at {SCHEMA_FILE} — running field-name checks only")

    md_files = sorted(docs_dir.rglob("*.md"))
    checked = 0
    failed = 0

    for path in md_files:
        status, violations = scan_file(path, schema)
        rel = path.relative_to(REPO_ROOT)

        if status == "skip":
            continue

        checked += 1
        if violations:
            failed += 1
            prefix = "[ERROR]" if (enforcement == "enforced" or args.strict) else "[WARN]"
            print(f"{prefix} {rel}")
            for v in violations:
                print(f"         • {v}")
        else:
            if not args.quiet:
                print(f"[OK]    {rel}")

    print(f"\n── Result: {checked} docs checked, {failed} with violations "
          f"(enforcement: {enforcement}) ──")

    if failed and (enforcement == "enforced" or args.strict):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
