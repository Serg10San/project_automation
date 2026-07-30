---
name: implement
description: "Implement a piece of work based on a PRD or set of issues."
disable-model-invocation: true
---

Implement the work described by the user in the PRD or issues.

> **STOP — Plan-Before-Code Gate (mandatory).** Before writing or modifying any
> production code, confirm an **approved plan exists** (an issue, an approved
> PRD, an ADR, or a plan the user explicitly approved in this conversation).
> If no approved plan exists, **do not code** — invoke `plan-before-code`, write
> the plan, and get explicit user approval first. The only exceptions are
> `prototype` (throwaway code) and trivial user-requested fixes.

Use /tdd where possible, at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Once done, use /review to review the work.

Commit your work to the current branch.
