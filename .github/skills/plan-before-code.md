---
name: plan-before-code
description: >
  MANDATORY pre-flight gate — run before writing or modifying any production
  code. Enforces that an approved plan (PRD, issue, ADR, or an explicitly
  user-approved plan in the conversation) exists before implementation begins.
  This is a hard STOP, not a recommendation.
disable-model-invocation: true
---

# Plan-Before-Code Gate

**Do not write or modify production code until an approved plan exists.** This is
a hard gate. If the gate is not satisfied, **STOP and get approval first** — do
not begin coding, scaffolding real logic, or editing source files.

This gate exists because unplanned code produces rework, scope drift, and
untraceable changes. Every production change must be traceable to an approved
intent.

---

## Step 1 — Check for an approved plan

A plan is **approved** when at least one of the following is true:

| Evidence of an approved plan | Where it lives |
|------------------------------|----------------|
| An issue the user told you to implement | issue tracker (`/to-issues`) |
| A PRD the user approved | `docs/` or the conversation (`/to-prd`) |
| An ADR recording the decision | `docs/adr/` or `adr.html` |
| A plan written in this conversation that the user **explicitly approved** | the conversation |

"Explicitly approved" means the user said yes to a written plan — a vague request
("add feature X") is **not** an approved plan.

If **none** apply → **the gate is NOT satisfied. Go to Step 3.**

---

## Step 2 — Confirm the plan is current and in scope

Even when a plan exists, confirm:

- The code you are about to write is **covered by** the approved plan (not scope creep).
- The plan has not been invalidated by newer decisions in the conversation.
- For test-driven work, behaviours and seams are agreed — invoke `tdd` and
  "Get user approval on the plan" before writing code.

If the change falls outside the approved plan → **STOP** and get the extension
approved before coding.

---

## Step 3 — If there is no approved plan, STOP and produce one

Do **not** start coding. Instead:

1. Tell the user plainly: *"There's no approved plan for this yet — I need to
   write one and get your approval before I start coding."*
2. Produce the smallest appropriate plan:
   - Non-trivial feature → `/to-prd` then `/to-issues`.
   - Single scoped task → a short written plan (goal, approach, files touched,
     acceptance criteria) presented for approval.
   - Architectural decision → `/domain-modeling` and/or an ADR.
3. **Wait for explicit user approval.** Do not proceed on silence or assumption.

---

## Exceptions (the only ones)

The gate does **not** block:

- **`prototype`** — explicitly throwaway, experimental code that will be deleted
  or absorbed. Say so out loud, keep it isolated, and do not ship it as production.
- **Trivial, obviously-safe fixes** the user directly asked for (typo, one-line
  doc fix, formatting). When in doubt, treat it as needing a plan.

For everything else, an approved plan is required.

---

## The one-line rule

> **No approved plan, no production code. If unsure, STOP and ask.**
