---
name: fable5-agentic-patterns
description: >
  Prompting and scaffolding patterns specific to Claude Fable 5 and Claude Mythos 5.
  Use when building any long-running agent, autonomous pipeline, or multi-agent system
  that targets Fable 5 or Mythos 5. Covers: effort levels, boundary instructions,
  progress grounding, agent memory, send_to_user, context-budget behavior, re-grounding
  final messages, and the reasoning-extraction refusal category. Invoke when the words
  "Fable 5", "Mythos 5", "long-running agent", "autonomous pipeline", or "overnight run"
  appear in the conversation.
---

# Claude Fable 5 / Mythos 5 — Agentic Patterns

This skill covers the behavioral differences and scaffolding patterns specific to
Claude Fable 5 and Claude Mythos 5. For techniques that apply to all models, use
the `context-window-management` and `sub_agent_orchestration` skills. For multi-agent
safety rules, use `avoiding-agent-conflicts` and `singapore-ai-governance`.

---

## 1. Effort Level Selection

Effort is the primary cost/intelligence/latency trade-off on Fable 5.

| Effort | When to use |
|--------|-------------|
| `low` | Quick lookups, simple Q&A, formatting tasks |
| `medium` | Routine development work, standard code generation |
| `high` | **Default for most tasks** — exploration, debugging, analysis |
| `xhigh` | Hardest unsolved problems, architecture design, critical bug hunts |

**Rule:** Lower effort on Fable 5 still often exceeds `xhigh` on prior models.
Reduce effort if a task completes correctly but runs longer than needed.

At higher effort, Fable 5 can over-gather context and over-deliberate on simple
tasks. Add this instruction when that happens:

> When you have enough information to act, act. Do not re-derive facts already
> established in the conversation, re-litigate a decision the user has already
> made, or narrate options you will not pursue. If you are weighing a choice,
> give a recommendation, not an exhaustive survey.

To prevent unrequested refactoring at higher effort:

> Don't add features, refactor, or introduce abstractions beyond what the task
> requires. A bug fix doesn't need surrounding cleanup. Do the simplest thing
> that works well. Don't design for hypothetical future requirements.

---

## 2. Boundary Instructions

Fable 5 can take unrequested actions (drafting an email when none was asked for,
creating defensive git-branch backups). Add this block to any agent system prompt:

```
When the user is describing a problem, asking a question, or thinking out loud
rather than requesting a change, the deliverable is your assessment. Report your
findings and stop. Don't apply a fix until they ask for one. Before running a
command that changes system state (restarts, deletes, config edits), check that
the evidence actually supports that specific action.
```

---

## 3. Progress Grounding (Long Runs)

On long autonomous runs, Fable 5 can fabricate status reports if not instructed
otherwise. Add this block to any agent that runs for more than 10 tool calls:

```
Before reporting progress, audit each claim against a tool result from this
session. Only report work you can point to evidence for. If something is not yet
verified, say so explicitly. If tests fail, say so with the output. If a step
was skipped, say that. When something is done and verified, state it plainly
without hedging.
```

---

## 4. Checkpoint / Pause Behavior

To have Fable 5 stop only when it genuinely needs you:

```
Pause for the user only when the work genuinely requires them: a destructive or
irreversible action, a real scope change, or input that only they can provide.
If you hit one of these, ask and end the turn. Do not end on a promise.
```

For fully autonomous pipelines (no user watching):

```
You are operating autonomously. The user is not watching in real time and cannot
answer questions mid-task. For reversible actions that follow from the original
request, proceed without asking. Before ending your turn, check your last
paragraph. If it is a plan, an analysis, a question, a list of next steps, or a
promise about work you have not done ("I'll…"), do that work now with tool calls.
End your turn only when the task is complete or you are blocked on input only
the user can provide.
```

---

## 5. Agent Memory System

Fable 5 performs particularly well when it can record and reference lessons
across runs. The `agent_memory/` directory (added when `fable5-agent-mode` is
enabled in scaffold) is the canonical store.

**Format — one file per lesson:**
```markdown
# [one-line summary of the lesson]
Date: YYYY-MM-DD

## What happened
[specific event or finding]

## What to do differently
[the corrected approach]

## Why it matters
[what was at stake]
```

**Rules for writing lessons:**
- Store one lesson per file — never bundle multiple lessons
- Record corrections and confirmed approaches alike, including why they mattered
- Don't save what the repo or chat history already records
- Update an existing note rather than creating a duplicate
- Delete notes that turn out to be wrong

**System prompt instruction to activate memory:**
```
Before starting, read all files in agent_memory/. After completing the task,
write one lesson file if you learned something the repo doesn't already capture.
Store it as agent_memory/YYYY-MM-DD-{slug}.md with a one-line summary at the top.
```

**To bootstrap from existing history:**
```
Reflect on the previous sessions we've had together. Use subagents to identify
core themes and lessons, and store them in agent_memory/. Make sure you know
to reference agent_memory/ for future use.
```

---

## 6. send_to_user Tool

For long asynchronous agents, define this tool to deliver verbatim messages to
the user without ending the turn. Tool inputs are never summarized by the API.

```json
{
  "name": "send_to_user",
  "description": "Display a message directly to the user. Use for progress updates, partial results, or content the user must see exactly as written before the task finishes.",
  "input_schema": {
    "type": "object",
    "properties": {
      "message": {
        "type": "string",
        "description": "The content to display to the user."
      }
    },
    "required": ["message"]
  }
}
```

**System prompt instruction to activate it:**
```
Between tool calls, when you have content the user must read verbatim (a partial
deliverable, a direct answer to their question, a progress update with specific
numbers), call send_to_user with that content. Use send_to_user only for
user-facing content — not for narration or reasoning.
```

The stub handler is in `src/tools/send_to_user_tool.py` (generated when
`fable5-agent-mode` is enabled in scaffold).

---

## 7. Re-Grounding Final Messages

In extended sessions, Fable 5 can produce hard-to-follow summaries full of
working shorthand. Add this to any agent that runs without the user watching:

```
Your final summary is for a reader who didn't see any of the tool calls.
Write it as a re-grounding, not a continuation of your working thread.
Open with the outcome: one sentence on what happened or what you found.
Then the supporting detail. Write complete sentences. Spell out terms.
Don't use arrow chains, hyphen-stacked compounds, or labels you invented
during the run. When you mention files, commits, or identifiers, give each
its own plain-language clause.
```

---

## 8. Reasoning Extraction Refusal — What Triggers It and What to Avoid

Fable 5 runs a safety classifier for **reasoning extraction** — attempts to make
the model echo, transcribe, or explain its internal thinking as response text.

**What triggers it:**
- "Show your thinking"
- "Explain your reasoning step by step"
- "Transcribe your internal reasoning"
- "Echo your thought process"
- Instructions that ask the model to reproduce summarized thinking blocks

**What does NOT trigger it:**
- Asking for a structured explanation of a decision (this is output, not thinking)
- "Walk me through your approach" when framing a plan
- Adaptive thinking blocks read from the API directly (structured, not text-echoed)

**Audit checklist for existing skills and system prompts:**
- [ ] Search for "show your thinking" / "explain your reasoning" — remove or reframe
- [ ] Replace with "explain your decision" or "walk me through your recommendation"
- [ ] If you need reasoning visibility, read `thinking` blocks from the API response
      directly — do not ask the model to echo them

---

## 9. Self-Verification for Long Runs

Separate verifier subagents outperform self-critique. For any long-running build:

```
Establish a method for checking your own work at an interval of [X] as you
build. Run this every [X interval], verifying your work with subagents against
the specification.
```

For the verifier subagent system prompt:
```
You are a verifier. Your only job is to check whether [specification] is met.
Do not fix anything. Report pass/fail for each criterion with specific evidence.
```

---

## Composable System Prompt — Full Fable 5 Agent Template

Copy and adapt. Each block is independent — include only what the run needs.

```
[EFFORT]
Use high effort. Escalate to xhigh only for the hardest reasoning steps.

[BOUNDARY]
When the user describes a problem or thinks out loud, your deliverable is your
assessment. Report and stop. Don't apply fixes until asked. Confirm before
any destructive or irreversible action.

[PROGRESS]
Before reporting progress, audit each claim against a tool result. Only report
verified work. State failures plainly.

[CHECKPOINT]
Pause only for destructive actions, real scope changes, or input only the user
can provide. Otherwise proceed. End your turn only when done or genuinely blocked.

[MEMORY]
Read agent_memory/ before starting. Write one lesson file after completing if
you learned something new.

[MESSAGES]
Call send_to_user for verbatim user-facing content mid-task. Not for narration.

[FINAL SUMMARY]
Open with the outcome. Complete sentences. No working shorthand. Spell out terms.
```
