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
    summary_prompt: "Summarize how to measure the token-cost reduction that code-review-graph (CRG) delivers in a project, including the benchmark method, the reusable script, and an interpretation of results."
    tags:
      - governance
      - developer
      - token-reduction
      - code-review-graph
      - benchmark
    do_not_summarize: false
---

# How to measure CRG token reduction in your project

This is the companion to [`crg-token-reduction.md`](crg-token-reduction.md). That
doc explains how to *install and activate* `code-review-graph` (CRG); this one
explains how to **prove the token saving** for your own codebase so the benefit
is a verifiable number rather than a claim.

## Why measure

AI coding assistants spend most of their context budget *reading whole files* to
infer relationships (callers, tests, blast radius) before acting. CRG replaces
that with compact, pre-computed graph queries. The size of the win depends on
your repo, so measure it locally.

## Method

For each task an assistant might perform, count context tokens two ways:

- **Baseline (no graph):** the whole relevant files an assistant must read to
  answer the question by inference.
- **With CRG:** the output of the compact CRG commands that answer the same
  question structurally (`query callers_of / callees_of / tests_for /
  importers_of`, `architecture`). Full files are read afterward only for the few
  symbols the graph flags.

Benchmark only *compact* commands. The verbose `impact` CLI can emit >100 KB; an
agent instead consumes the **minimal** MCP variant of blast-radius, so
`query importers_of` + `callers_of` is the faithful, reproducible stand-in.

Use a real tokenizer — `tiktoken` with `o200k_base` (GPT-4o / o-series) — not a
character/4 approximation.

## Steps

```powershell
# 1. Build the graph (once; refresh with `build` / `update` after changes)
.venv\Scripts\code-review-graph.exe build

# 2. Install the tokenizer used for counting
.venv\Scripts\python.exe -m pip install tiktoken

# 3. Add the benchmark script (appendix below) as scripts\measure_token_cost.py,
#    editing SCENARIOS to reference files + symbols that exist in YOUR project.

# 4. Run it
.venv\Scripts\python.exe scripts\measure_token_cost.py
```

The script prints a per-scenario table and writes `docs/token-cost-benchmark.json`.

## Worked example (AI_Adoption_Exploration, 30 files / 304 nodes / 1,821 edges)

| Scenario | Baseline | CRG | Saved | Reduction | Ratio |
|---|--:|--:|--:|--:|--:|
| Refactor review | 8,783 | 1,734 | 7,049 | 80.3% | 5.1× |
| Find callers | 4,350 | 143 | 4,207 | 96.7% | 30.4× |
| Change-impact / dependents | 8,862 | 2,240 | 6,622 | 74.7% | 4.0× |
| Architecture / onboarding | 14,155 | 824 | 13,331 | 94.2% | 17.2× |
| **TOTAL** | **36,150** | **4,941** | **31,209** | **86.3%** | **7.3×** |

## Interpreting results

- **Narrow lookups win biggest** (find-callers ~30×): one small answer vs. reading
  several files to grep.
- **Onboarding/architecture** collapses a large multi-file read into a small map.
- **Everyday refactor/impact** tasks land at 4–5×, since you still read a couple of
  flagged files afterward.
- **Ratios grow with repo size** — baseline file-reading scales with file size,
  graph queries stay roughly flat.

## Caveats

- These are *context-loading* tokens (the dominant cost in agentic review), not a
  full end-to-end session measurement.
- **Query precision matters:** a bare, ambiguous symbol returns a large
  disambiguation payload that can *cost* more tokens than a file read. Query by
  qualified name; use `tests_for` against symbols, not whole file paths.
- CRG tool responses also self-report a `context_savings` estimate — treat the
  tiktoken measurement as the auditable figure.

## Appendix — reusable benchmark script

Save as `scripts/measure_token_cost.py` and edit `SCENARIOS` for your codebase:

```python
"""Benchmark CRG token reduction: whole-file reads vs. compact graph queries."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parents[1]
CRG = ROOT / ".venv" / "Scripts" / "code-review-graph.exe"
ENC = tiktoken.get_encoding("o200k_base")


def toks(text: str) -> int:
    return len(ENC.encode(text))


def crg(args: list[str]) -> str:
    return subprocess.run(
        [str(CRG), *args], cwd=ROOT, capture_output=True, text=True
    ).stdout


def file_tokens(rel: str) -> int:
    return toks((ROOT / rel).read_text(encoding="utf-8"))


@dataclass
class Scenario:
    name: str
    baseline_files: list[str]
    crg_commands: list[list[str]] = field(default_factory=list)


# EDIT these to reference real files + symbols in your project:
SCENARIOS = [
    Scenario(
        "Refactor review",
        ["src/your_module.py", "tests/test_your_module.py"],
        [["query", "callers_of", "your_function"],
         ["query", "tests_for", "your_function"]],
    ),
    Scenario(
        "Architecture / onboarding",
        ["src/your_module.py", "src/other_module.py"],
        [["architecture"]],
    ),
]


def main() -> None:
    rows, tot_b, tot_c = [], 0, 0
    for sc in SCENARIOS:
        b = sum(file_tokens(f) for f in sc.baseline_files)
        c = sum(toks(crg(cmd)) for cmd in sc.crg_commands)
        tot_b, tot_c = tot_b + b, tot_c + c
        pct = (b - c) / b * 100 if b else 0.0
        rows.append({"scenario": sc.name, "baseline": b, "crg": c,
                     "saved": b - c, "reduction_pct": round(pct, 1)})
        print(f"{sc.name:<28}{b:>8,}{c:>8,}{b - c:>9,}{pct:>7.1f}%")
    gp = (tot_b - tot_c) / tot_b * 100 if tot_b else 0.0
    print(f"{'TOTAL':<28}{tot_b:>8,}{tot_c:>8,}{tot_b - tot_c:>9,}{gp:>7.1f}%")
    (ROOT / "docs" / "token-cost-benchmark.json").write_text(
        json.dumps({"scenarios": rows,
                    "totals": {"baseline": tot_b, "crg": tot_c,
                               "reduction_pct": round(gp, 1)}}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
```
