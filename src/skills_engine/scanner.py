"""
File walker and pattern matcher for the skills scanner.

Scoring uses three dimensions to avoid raw-count inflation:
  - indicator diversity  (how many distinct indicator types matched)
  - file breadth         (how many unique files had matches)
  - project breadth      (how many top-level sub-directories had matches)

Maturity levels:
  Not Detected → Aware → Practiced → Applied → Teaching
"""

import json
import os
import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

# Directories to skip unconditionally
_SKIP_DIRS = {
    ".venv", "venv", ".env", "__pycache__", ".git",
    "node_modules", ".mypy_cache", "dist", "build",
    ".pytest_cache", "archive", ".tox",
}

# Binary / non-text extensions to skip
_SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico",
    ".pdf", ".docx", ".xlsx", ".pptx", ".zip", ".tar", ".gz",
    ".whl", ".lock",
}


@dataclass
class SkillEvidence:
    skill_name: str
    domain: str
    total_indicators: int
    matched_indicator_names: set = field(default_factory=set)
    matched_files: set = field(default_factory=set)
    matched_projects: set = field(default_factory=set)
    has_teaching_evidence: bool = False
    sample_matches: list[str] = field(default_factory=list)

    @property
    def type_ratio(self) -> float:
        return len(self.matched_indicator_names) / max(self.total_indicators, 1)

    @property
    def file_count(self) -> int:
        return len(self.matched_files)

    @property
    def project_count(self) -> int:
        return len(self.matched_projects)

    @property
    def level(self) -> str:
        """Derive maturity level from evidence dimensions."""
        n_types = len(self.matched_indicator_names)
        n_files = self.file_count
        n_projects = self.project_count
        ratio = self.type_ratio

        if n_types == 0:
            return "Not Detected"

        # Teaching requires Applied-level evidence PLUS explicit teaching indicators
        if self.has_teaching_evidence and ratio >= 0.6 and n_files >= 3:
            return "Teaching"

        # Applied: broad indicator coverage across multiple files or projects
        if ratio >= 0.6 and (n_files >= 3 or n_projects >= 2):
            return "Applied"

        # Practiced: multiple indicator types, multiple files
        if ratio >= 0.33 and n_files >= 2:
            return "Practiced"

        # Aware: at least one indicator found somewhere
        return "Aware"

    @property
    def level_num(self) -> int:
        return {"Not Detected": 0, "Aware": 1, "Practiced": 2, "Applied": 3, "Teaching": 4}.get(
            self.level, 0
        )


class CodeScanner:
    def __init__(self, scan_path: str):
        self.scan_path = Path(scan_path).resolve()
        self._file_cache: dict[Path, str] = {}

    # ------------------------------------------------------------------
    # File enumeration
    # ------------------------------------------------------------------

    def _all_files(self) -> list[Path]:
        """Walk scan_path and return all scannable files."""
        results: list[Path] = []
        for root, dirs, files in os.walk(self.scan_path):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
            for name in files:
                p = Path(root) / name
                if p.suffix.lower() not in _SKIP_EXTENSIONS:
                    results.append(p)
        return results

    def _project_of(self, path: Path) -> str:
        """Return the top-level sub-directory name as the 'project'."""
        try:
            rel = path.relative_to(self.scan_path)
            return rel.parts[0] if len(rel.parts) > 1 else "__root__"
        except ValueError:
            return "__root__"

    # ------------------------------------------------------------------
    # File reading
    # ------------------------------------------------------------------

    def _read(self, path: Path) -> str:
        if path in self._file_cache:
            return self._file_cache[path]
        try:
            if path.suffix == ".ipynb":
                text = self._read_notebook(path)
            else:
                text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            text = ""
        self._file_cache[path] = text
        return text

    @staticmethod
    def _read_notebook(path: Path) -> str:
        """Extract source from code cells only."""
        try:
            nb = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            lines: list[str] = []
            for cell in nb.get("cells", []):
                if cell.get("cell_type") == "code":
                    src = cell.get("source", [])
                    lines.append("".join(src) if isinstance(src, list) else src)
            return "\n".join(lines)
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Glob matching
    # ------------------------------------------------------------------

    def _matches_any_glob(self, path: Path, globs: list[str]) -> bool:
        """Check if path matches any glob pattern."""
        name = path.name
        # Full relative path (forward slashes) for patterns like .github/workflows/*.yml
        try:
            rel_str = str(path.relative_to(self.scan_path)).replace("\\", "/")
        except ValueError:
            rel_str = path.name

        for g in globs:
            if fnmatch(name, g) or fnmatch(rel_str, g) or fnmatch(rel_str, f"**/{g}"):
                return True
            # Handle patterns with directory component (e.g. .github/workflows/*.yml)
            if "/" in g and fnmatch(rel_str, g):
                return True
        return False

    # ------------------------------------------------------------------
    # Skill scanning
    # ------------------------------------------------------------------

    def scan_skill(self, skill: dict, files: list[Path]) -> SkillEvidence:
        evidence = SkillEvidence(
            skill_name=skill["name"],
            domain=skill["domain"],
            total_indicators=len(skill["indicators"]),
        )

        for indicator in skill["indicators"]:
            name = indicator["name"]
            is_teaching = indicator.get("is_teaching", False)

            # --- existence check: just finding the file is enough ---
            if "existence_globs" in indicator:
                for path in files:
                    if self._matches_any_glob(path, indicator["existence_globs"]):
                        evidence.matched_indicator_names.add(name)
                        evidence.matched_files.add(str(path))
                        evidence.matched_projects.add(self._project_of(path))
                        if is_teaching:
                            evidence.has_teaching_evidence = True
                        if len(evidence.sample_matches) < 3:
                            evidence.sample_matches.append(f"[exists] {path.relative_to(self.scan_path)}")
                        break  # one file is enough for existence

            # --- content pattern check ---
            if "patterns" in indicator:
                globs = indicator.get("globs", ["*"])
                compiled = [
                    re.compile(p, re.IGNORECASE | re.MULTILINE)
                    for p in indicator["patterns"]
                ]
                indicator_matched_this_file = False

                for path in files:
                    if not self._matches_any_glob(path, globs):
                        continue
                    content = self._read(path)
                    if not content:
                        continue

                    file_matched = False
                    for pattern in compiled:
                        match = pattern.search(content)
                        if match:
                            file_matched = True
                            if not indicator_matched_this_file:
                                evidence.matched_indicator_names.add(name)
                                if is_teaching:
                                    evidence.has_teaching_evidence = True
                                indicator_matched_this_file = True
                            if len(evidence.sample_matches) < 3:
                                snippet = match.group(0)[:70].replace("\n", "↵")
                                try:
                                    rel = path.relative_to(self.scan_path)
                                except ValueError:
                                    rel = path
                                evidence.sample_matches.append(f"{rel}: {snippet}")
                            break  # one pattern match per file is enough

                    if file_matched:
                        evidence.matched_files.add(str(path))
                        evidence.matched_projects.add(self._project_of(path))

        return evidence

    # ------------------------------------------------------------------
    # Main scan entry point
    # ------------------------------------------------------------------

    def scan_all(self, skills: list[dict]) -> tuple[list[SkillEvidence], dict]:
        """Scan all files for all skills. Returns (evidence_list, stats)."""
        files = self._all_files()
        stats = {
            "scan_path": str(self.scan_path),
            "total_files": len(files),
            "extensions": sorted({p.suffix for p in files if p.suffix}),
        }
        evidence_list = [self.scan_skill(skill, files) for skill in skills]
        return evidence_list, stats
