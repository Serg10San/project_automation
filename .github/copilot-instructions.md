# Copilot Instructions - project_automation

## Project Overview
project_automation: Power Automate / Graph API project-tracking automation, scaffolded to mirror moonrox/IRE-AutomateProject

Scaffolded 2026-07-29 from the IRE Python + Skills framework template.

## Language & Runtime
- Python 3.11+
- Virtual environment at `.venv/`

## Conventions
- Source code lives in `src/`
- Tests live in `tests/`
- Use `test_runner.py` for input/output script tests; use `pytest` for unit tests
- Keep secrets in `.env` (never commit)

## Session Startup (mandatory)
- At the start of every Copilot CLI session in this folder, run `az login`
  first (delegated Graph/SharePoint auth — see `GRAPH_AUTH_MODE=delegated`
  in `.env` — expires and must be refreshed each session).
- `az` is not on PATH in this environment; use the full path:
  `C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd login`
- This is required before any task that uploads to SharePoint (e.g.
  `weekly_report.py`, `sharepoint_upload.py`) will succeed.

## Key Files
- `requirements.txt` — runtime dependencies
- `requirements-dev.txt` — dev/test tools
- `pyproject.toml` — project metadata and tool config
- `assess_skills.py` — skills scanner CLI (run `python assess_skills.py`)

## Code Quality Stack

Two tools, one job each — never swap their roles:

| Tool | Role | Command | Config section |
|------|------|---------|----------------|
| **Black** | **Format** — rewrites whitespace, quotes, trailing commas. Opinionated, zero per-rule config. | `black .` | `[tool.black]` |
| **Ruff** | **Lint** — catches errors, unused imports, naming, upgrades. Fast, rule-based. | `ruff check .` | `[tool.ruff.lint]` |
| **mypy** | **Type check** — enforces type annotations. | `mypy src/` | `[tool.mypy]` |

### Run order (always format before lint)
```powershell
black .          # 1. format first — removes style noise from lint output
ruff check .     # 2. lint second — flags real problems
mypy src/        # 3. type-check last
```

### Rules
- **Do not run `ruff format`** — Black owns formatting. `ruff format` and `black` conflict.
- **Do not add `[tool.ruff.format]`** to `pyproject.toml` — same reason.
- Black `line-length = 100` and Ruff `line-length = 100` must always match.
- All three tools are declared in `requirements-dev.txt` and `[project.optional-dependencies].dev`.

## Engineering Skills (`.github/skills/`)
This project ships Matt Pocock's engineering skills — available to Claude, Copilot, and any AI tool that reads this repo:

> ### ⛔ Plan-Before-Code Gate (mandatory, non-negotiable)
> **Never write or modify production code before an approved plan exists.** An
> approved plan is an issue, an approved PRD, an ADR, or a plan the user
> **explicitly approved** in the conversation. A vague request is not a plan.
> If no approved plan exists, **STOP**, invoke `plan-before-code`, write the plan,
> and wait for explicit user approval before coding. The only exceptions are
> `prototype` (throwaway code, clearly labelled) and trivial user-requested fixes
> (typo, one-line doc/format change). When in doubt, stop and ask.

| Skill | When to invoke |
|-------|---------------|
| `plan-before-code` | **BEFORE any production code** — hard gate confirming an approved plan (issue/PRD/ADR/approved conversation plan) exists |
| `codebase-design` | Designing or improving a module's interface, finding deepening opportunities |
| `diagnosing-bugs` | Hard bugs, performance regressions — "diagnose this" / "debug this" |
| `domain-modeling` | Pinning down domain terminology, writing CONTEXT.md or ADRs |
| `implement` | Implementing a planned task |
| `improve-codebase-architecture` | Architecture improvement analysis and HTML report |
| `prototype` | Rapid prototyping before committing to an approach |
| `resolving-merge-conflicts` | Resolving merge conflicts |
| `tdd` | Test-driven development workflow |
| `to-issues` | Breaking a PRD into actionable GitHub issues |
| `to-prd` | Converting an idea or brief into a Product Requirements Document |
| `triage` | Triaging and labelling incoming issues |
| `avoiding-agent-conflicts` | Multi-agent conflict prevention — goal alignment, deadlock detection, kill switches |
| `knowledge-identity` | Reading/writing/drafting docs with IRE Knowledge Identity front matter and author profiles |
| `analytical-integrity` | Verifiable claims standard — VERIFIED/INFERRED/UNVERIFIED tagging, citation, exportable evidence |
| `paginating-api-fetches` | Pagination pattern for any API returning total/count — prevents silent data truncation |
| `singapore-ai-governance` | IMDA 4-dimension governance: risk bound, human accountability, technical controls, deskilling prevention |
| `fable5-agentic-patterns` | Claude Fable 5/Mythos 5 scaffolding: effort levels, memory system, send_to_user, progress grounding, boundary instructions |
| `last-mile-authorization` | Any agent data read/write, action, or external API call — validate authorization at the moment of use via a central Policy Decision Point (Zero Trust); cached decisions are never permanent |

Source: [mattpocock/skills](https://github.com/mattpocock/skills) — Skills for Real Engineers.

## Skills Framework
This project uses the IRE skills scanner. Skills are defined in `src/skills/`:
- `registry.py` — built-in skills (AI, Python, M365, SRE, Governance, …)
- `loader.py` — merges built-in skills with any `*.yaml` skill definitions
- `*.yaml` — drop additional skill YAML files here; picked up automatically

The `src/skills_engine/` package contains the scanner and report engine.
Do not modify scanner/report internals unless you are extending the engine itself.

## Deferred Skills — Add Only When Triggered

These skills were analyzed and deliberately **not added** to the registry. The scanner must
detect real evidence — adding a skill with no codebase evidence breaks the zero-gap record.
Add the skill YAML **only when the trigger condition is met**.

### Batch Processing

**Decision (2026-06-27):** Not added. Current pipelines process all data in memory at once.
No chunking, queue, retry, or checkpoint patterns exist. Adding the skill now would create a
Not Detected gap with zero value.

**Add `batch_processing.yaml` when ANY of these conditions is true:**

| Trigger | Signal | Action |
|---|---|---|
| Pipeline hits `MemoryError` | Dataset no longer fits in memory | Add `batch_size` chunking to that pipeline |
| API calls get rate-limited | HTTP 429 / throttle errors from lake, Graph, or LLM endpoints | Add batch loop + exponential backoff + retry queue |
| Pipeline fails mid-run and must restart from scratch | Reprocessing costs > 5 minutes | Add checkpointing (write last-processed ID to disk) |
| Processing 10K+ records and need visibility | Long-running pipeline with no progress signal | Add `tqdm` progress bar + chunk loop |
| Chunks can be processed independently | No cross-chunk dependencies | Wire into `Orchestrator.run_parallel()` — sub-agent scaffold already handles this |

**Patterns to detect when adding the skill:**
```python
batch_size       # chunk sizing parameter
for chunk in     # chunked iteration
checkpoint(      # resumable state write
retry_queue      # dead-letter / retry
tqdm(            # progress tracking
run_parallel(    # parallel chunk execution (already in src/agents/)
```

**Related skills already active:** Sub-agent Orchestration (`run_parallel`), Dynamic Context
Injection (token-aware trimming is a form of batching for LLM inputs).

## Model Selection Framework

Choose the right model for the task — the larger the context window, the higher the cost.

| Tier | Model | When to use |
|------|-------|-------------|
| Triage | `claude-haiku-4.5` | Status checks, file searches, log reads, config edits |
| Analysis | `claude-sonnet-4.6` | **Default** — code, debugging, endpoints, investigations |
| Decision | `claude-opus-4.8` | ADRs, architecture changes, security review, trade-offs |

### Switching models mid-session
```
/model claude-haiku-4.5    # switch to Haiku for cheap tasks
/model claude-opus-4.8     # switch to Opus for high-stakes decisions
/model auto                # let Copilot choose
```

### Per-subagent defaults
| Agent type | Default model |
|------------|--------------|
| `explore`, `task` | Haiku — background scans and builds |
| `general-purpose`, `code-review` | Sonnet — default analysis |
| `security-review`, `rubber-duck` | Opus — high-stakes review |

Configure subagent defaults persistently with `/subagents`.

## Knowledge Identity Layer (Optional)

If `docs/ire-knowledge-schema.yaml` exists in this project with `enabled: true`,
the IRE Knowledge Identity Layer is active. Apply it when writing, reviewing,
or ingesting any documentation.

| File | Purpose |
|------|---------|
| `docs/ire-knowledge-schema.yaml` | Feature toggle + project config |
| `docs/ire-taxonomy.yaml` | Valid values for all front matter fields |
| `docs/authors/{username}.md` | Author writing profiles (voice + attribution) |
| `docs/knowledge/_doc-template.md` | Front matter template for new documents |

**When writing a new `.md` doc:** copy `_doc-template.md`, fill in the `ire_doc`
front matter, and use `docs/ire-taxonomy.yaml` for valid field values.

**When drafting for an author:** load `docs/authors/{username}.md` first and
match their `tone`, `structure`, and `vocabulary` exactly.

**Full instructions:** invoke the `knowledge-identity` skill
(`/skill knowledge-identity` or see `.github/skills/knowledge-identity.md`).

**To disable:** set `enabled: false` in `docs/ire-knowledge-schema.yaml`,
or delete the file. Scanner will report "Not Detected" — this is not a gap.

## code-review-graph (Optional) — token reduction

This project ships an **opt-in** `code-review-graph` (CRG) integration. CRG builds
a local Tree-sitter code graph so AI assistants can query callers, callees, tests,
affected flows, and blast radius **before** reading whole files — cutting token
usage on reviews and debugging.

**Availability vs. activation — two separate things:**
- *Available (always):* CRG is declared in the `dev` dependency group, documented
  in `docs/knowledge/crg-token-reduction.md`, and wired into the optional
  `.github/workflows/crg-pr-review.yml`. Nothing runs automatically.
- *Active (opt-in):* only after a developer installs it — either at scaffold time
  (the scaffolder's "Install and activate CRG now?" prompt / `--install-crg`) or
  later via the runbook. Activation pip-installs CRG, registers a local MCP server,
  and builds `.code-review-graph/graph.db`.

**When CRG is active** (a `.code-review-graph/` graph exists and
`.github/code-review-graph.instruction.md` is present), **prefer the graph tools
FIRST** for code exploration and review:

| Task | Use graph tool first |
|------|----------------------|
| Find relationships | `query_graph_tool` (callers_of / callees_of / tests_for) |
| Minimal context for a task | `get_minimal_context_tool` |
| Change/impact review | `detect_changes_tool`, `get_impact_radius_tool`, `get_affected_flows_tool` |
| Find code by keyword | `semantic_search_nodes_tool` |
| High-level structure | `get_architecture_overview_tool` |

Fall back to file/search tools only when the graph does not cover what you need.
Keep the graph fresh with `code-review-graph update` (git repos) or
`code-review-graph build` after meaningful changes.

> **Protect `.github/skills/`:** always install CRG with `--no-skills --no-hooks`
> so its generated skills never overwrite this project's engineering skills.

**Full setup, air-gapped caveats, and the PR-review workflow:**
see `docs/knowledge/crg-token-reduction.md`.

## How to Use a Skill in This Project


1. **Drop a YAML file** in `src/skills/` (no code changes required).
2. Run `python assess_skills.py --list-skills` to verify it was discovered.
3. Run `python assess_skills.py` to scan for evidence in this codebase.
4. Use `--domain "your domain"` to filter results.

Example skill YAML (`src/skills/my_skill.yaml`):
```yaml
skill:
  name: "My Skill"
  domain: "My Domain"
  indicators:
    - name: "usage pattern"
      patterns:
        - "regex_pattern"
      globs:
        - "*.py"
    - name: "docs evidence"
      patterns:
        - "teaching phrase"
      globs:
        - "*.md"
      is_teaching: true
```
