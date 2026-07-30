---
ire_doc:
  type: runbook
  area: governance
  perspective: developer
  intent: knowledge-capture
  author: "jmonroe"
  created: "2026-07-20"
  updated: "2026-07-20"
  status: draft
  schema_version: "1.1"
  ai_index:
    summary_prompt: "Summarize how IRE developers opt into code-review-graph to reduce AI coding-assistant token usage."
    tags:
      - governance
      - developer
      - cross-cutting
      - platform
    do_not_summarize: false
---

# Opt-in CRG token reduction for AI coding assistants

## Overview

AI coding assistants often spend most of their context budget reading whole files before they
know which symbols, callers, tests, or flows matter. `code-review-graph` (CRG) reduces that
waste by building a local SQLite knowledge graph and exposing graph-scoped MCP tools. Agents can
ask for minimal context, callers, callees, dependents, tests, affected flows, and blast radius
before deciding whether any file read is needed.

This template only declares CRG as an optional development dependency. It does not install CRG,
run `code-review-graph install`, start hooks, or build a graph unless a developer explicitly opts
in inside a scaffolded project.

## Verified CRG facts

- PyPI package: `code-review-graph`.
- Pinned version for this template: `2.3.7` / GitHub release tag `v2.3.7`.
- Core setup commands: `pip install code-review-graph`, `code-review-graph install`, and
  `code-review-graph build`.
- Safer installer preview: `code-review-graph install --dry-run`.
- Platform targeting: `code-review-graph install --platform copilot`, `--platform copilot-cli`,
  `--platform cursor`, or `--platform claude-code`.
- Graph storage: `.code-review-graph/graph.db` by default, or an external location through
  `--data-dir` / `CRG_DATA_DIR`.
- MCP server: `code-review-graph serve` starts stdio MCP; `code-review-graph serve --http`
  starts streamable HTTP on localhost, default port 5555.
- Token-saving MCP tools include `get_minimal_context_tool`, `detect_changes_tool`,
  `get_review_context_tool`, `get_impact_radius_tool`, `get_affected_flows_tool`,
  `query_graph_tool`, `semantic_search_nodes_tool`, `get_architecture_overview_tool`,
  `list_flows_tool`, and `list_communities_tool`.

## Opt-in setup for a scaffolded project

From the project root:

```powershell
.venv\Scripts\python.exe -m pip install "code-review-graph==2.3.7"
code-review-graph install --dry-run
code-review-graph install --platform copilot --no-skills --no-hooks -y
code-review-graph build
```

Use `--platform cursor` for Cursor, `--platform claude-code` for Claude Code, or
`--platform copilot-cli` for GitHub Copilot CLI. Restart the editor or agent after install.

Installer write locations verified from CRG v2.3.7 docs/source:

| Platform command | Primary files written |
|---|---|
| `--platform copilot` | `.vscode/mcp.json` and `.github/code-review-graph.instruction.md` unless `--no-instructions` is used |
| `--platform copilot-cli` | `~/.copilot/mcp-config.json` and `.github/code-review-graph.instruction.md` unless `--no-instructions` is used |
| `--platform claude-code` | `.mcp.json`, optional `CLAUDE.md`, `.claude/settings.json`, `.claude/skills/<name>/SKILL.md`, and a git pre-commit hook unless skipped |
| `--platform cursor` | `.cursor/mcp.json`, `.cursorrules`, and user-level `~/.cursor/hooks.json` / `~/.cursor/hooks/*.sh` when Cursor hooks are enabled |


For an IRE project that installs dev extras from `pyproject.toml`, the first command can be:

```powershell
.venv\Scripts\python.exe -m pip install ".[dev]"
```

## Daily usage pattern

1. Build once with `code-review-graph build`.
2. Keep the graph fresh with `code-review-graph update` after meaningful changes, or opt into
   platform hooks only if that is acceptable for the project.
3. Ask the assistant to start with `get_minimal_context_tool(task="...")`.
4. For reviews, use `detect_changes_tool` or `code-review-graph detect-changes --brief`.
5. For impact analysis, use `get_impact_radius_tool`, `get_affected_flows_tool`, and
   `query_graph_tool` with patterns such as `callers_of`, `callees_of`, `imports_of`,
   `importers_of`, `tests_for`, and `file_summary`.
6. Read full files only when the graph result shows that the file is relevant.

Plain English before/after: without CRG, an agent may read every changed file and several nearby
files to infer impact. With CRG, it asks the local graph for a compact list of changed symbols,
callers, tests, and affected flows first, then reads only the few snippets that matter.

## `.github/skills/` collision warning

This template already owns `.github/skills/` for mattpocock-style AI workflow guides. Do not let
third-party installers overwrite that directory.

CRG v2.3.7 writes platform-native skills to locations such as `.claude/skills/`,
`.gemini/skills/`, `.codebuddy/skills/`, or `.qoder/skills/`, and writes Copilot instructions to
`.github/code-review-graph.instruction.md`; it does not need this template's `.github/skills/`.
Use a platform-specific install command and skip generated skills/hooks when all you need is MCP:

```powershell
code-review-graph install --platform copilot --no-skills --no-hooks -y
```

The template `.gitignore` also excludes CRG graph data and common CRG-generated config, hook,
instruction, and skill locations so local opt-in artifacts are not committed by accident.

## Air-gapped and no-egress notes

Core build, review, search, CLI, and MCP workflows are local-first and store data in the local
SQLite graph. Normal graph use does not require cloud APIs.

Avoid optional embeddings in no-egress environments unless approved:

- `code-review-graph[embeddings]` may download a local sentence-transformers model from
  Hugging Face on first use.
- Cloud embedding providers (`openai`, `google`, `minimax`) send embedded source snippets to the
  configured provider only when explicitly selected.
- Cloud providers print an egress warning unless `CRG_ACCEPT_CLOUD_EMBEDDINGS=1` is set.
- OpenAI-compatible providers use `CRG_OPENAI_BASE_URL`, `CRG_OPENAI_API_KEY`, and
  `CRG_OPENAI_MODEL`; local embeddings use `CRG_EMBEDDING_MODEL`.

## Enable the optional PR-review workflow

The template includes `.github/workflows/crg-pr-review.yml`, pinned to the immutable
commit SHA `tirth8205/code-review-graph@6a1ee1c7063cc35cfa5ff12b8198c29360f3e4ad` (tag
`v2.3.7`). Pinning to a SHA rather than a mutable tag prevents a re-pointed tag from
silently changing the CI code that receives `GITHUB_TOKEN`; bump it deliberately (e.g.
via Dependabot). It is disabled unless the repository variable
`CRG_PR_REVIEW_ENABLED` is exactly `true`.

To enable it in a scaffolded GitHub repository:

1. Go to repository **Settings -> Secrets and variables -> Actions -> Variables**.
2. Add `CRG_PR_REVIEW_ENABLED` with value `true`.
3. Open or update a pull request.

The workflow grants `contents: read` and `pull-requests: write`, checks out the code, runs CRG's
composite action, builds or updates `.code-review-graph/` on the runner, runs
`code-review-graph detect-changes --base ...`, and posts a sticky, risk-scored PR comment with
estimated token savings.

Verified action inputs used by the template are `github-token`, `comment`, `fail-on-risk`, and
`python-version`. CRG also exposes a `comment-file` output for split trusted-comment workflows.

## Rollback

Remove local CRG integration from a project with:

```powershell
code-review-graph uninstall --dry-run
code-review-graph uninstall --yes
```

Then delete any remaining ignored local artifacts that your team no longer wants, such as
`.code-review-graph/` or editor-specific MCP config files.
