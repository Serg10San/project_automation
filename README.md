# project_automation

> Power Automate / Graph API project-tracking automation, scaffolded to mirror moonrox/IRE-AutomateProject

Scaffolded 2026-07-29 from the IRE Python + Skills framework template.

## Setup

```powershell
# 1. Activate the virtual environment
.venv\Scripts\activate

# 2. Install runtime dependencies
pip install -r requirements.txt

# 3. Install dev tools
pip install -r requirements-dev.txt

# 4. Configure secrets
# Edit .env directly and fill in any required values

# 5. Run tests
pytest
```

## AI Coding Tools (optional) - token reduction

This scaffold includes an opt-in `code-review-graph` (CRG) integration for developers who use
GitHub Copilot, Claude Code, Cursor, or similar agentic AI tools. CRG builds a local code graph so
assistants can query callers, dependents, tests, affected flows, and blast radius before reading
whole files, reducing LLM token consumption during reviews and debugging.

CRG is declared only in the `dev` optional dependency group. This scaffold did not install CRG,
build a graph, or write MCP/editor config unless you chose *"Install and activate CRG now?"*
during scaffolding (or passed `--install-crg`). To activate it later, or for `.github/skills/`
collision guidance, air-gapped caveats, and the optional PR-review workflow, see
[docs/knowledge/crg-token-reduction.md](docs/knowledge/crg-token-reduction.md).

## Project structure

```
project_automation/
├── .env                       # Config + secrets (git-ignored, edit directly)
├── .gitignore
├── .github/
│   └── copilot-instructions.md  # Copilot context for this project
├── pyproject.toml             # Project metadata and tool config (ruff, mypy, pytest)
├── requirements.txt           # Runtime deps
├── requirements-dev.txt       # Dev/test tools
├── assess_skills.py           # CLI — scan codebase for skill maturity evidence
├── test_runner.py             # I/O script test runner entry point
├── src/
│   ├── __init__.py
│   ├── tracker.py             # Project lifecycle tracker (SQLite)
│   ├── skills/                # Skill definitions
│   │   ├── __init__.py
│   │   ├── loader.py          # Merges built-in + YAML skills
│   │   ├── registry.py        # Built-in skills (AI, Python, M365, SRE, …)
│   │   └── singapore_agentic_ai_governance.yaml  # IMDA governance skill
│   └── skills_engine/         # Scanner & report engine
│       ├── __init__.py
│       ├── scanner.py         # File walker + pattern matcher
│       └── report.py          # Console / JSON / CSV formatter
└── tests/
    ├── test_runner.py         # I/O test harness (add scripts here)
    └── test_tracker.py        # Unit tests for the project tracker
```

## Skills Scanner

The built-in skills scanner detects evidence of skills across your codebase and
reports a maturity level (Aware → Practiced → Applied → Teaching).

```bash
# Scan this project
python assess_skills.py

# Scan a specific path
python assess_skills.py C:\scripts\ai_scripts

# Filter to AI governance skills only
python assess_skills.py --domain "governance"

# Filter to Singapore Agentic AI Governance framework
python assess_skills.py --domain "singapore"

# Show only Applied or Teaching level skills
python assess_skills.py --min-level applied

# Verbose — show code snippets that matched
python assess_skills.py --verbose

# Export as JSON or CSV
python assess_skills.py --json > results.json
python assess_skills.py --csv  > results.csv

# List all discovered skills
python assess_skills.py --list-skills
```

### Adding a new skill (YAML — no code changes)

Drop a `.yaml` file in `src/skills/` with this format:

```yaml
skill:
  name: "My New Skill"
  domain: "My Domain"
  description: "Optional description."
  indicators:
    - name: "code pattern check"
      patterns:
        - "regex_pattern_1"
        - "regex_pattern_2"
      globs:
        - "*.py"

    - name: "file existence check"
      existence_globs:
        - "my_config.yaml"

    - name: "documentation / teaching evidence"
      patterns:
        - "teaching phrase to find"
      globs:
        - "*.md"
      is_teaching: true   # counts toward "Teaching" maturity level
```

The scanner picks it up automatically — no registration step needed.

### Maturity levels

| Level | Criteria |
|-------|----------|
| **Not Detected** | No indicators matched |
| **Aware** | ≥1 indicator type matched |
| **Practiced** | ≥33 % indicator types, ≥2 files |
| **Applied** | ≥60 % indicator types, ≥3 files or 2 projects |
| **Teaching** | Applied + `is_teaching` indicator + ≥60 % coverage |

## Running Tests

```bash
# Unit tests
pytest

# I/O script tests (add cases to tests/test_runner.py)
python test_runner.py
```

## Environment Variables

Edit `.env` directly and fill in values before running.
