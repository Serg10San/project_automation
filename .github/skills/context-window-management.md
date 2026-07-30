---
name: context-window-management
description: >
  Context window token counting, compression triggering, and history summarisation.
  Use when the conversation is long-running, when working with large documents,
  when the user mentions "token limit", "context full", or "losing history",
  or when designing an AI pipeline that must run indefinitely without hitting
  the model's context ceiling.
---

# Context Window Management

Every LLM has a hard token limit — the **context window**. When a session
fills it, older messages are silently dropped or the API errors out. This skill
prevents both failure modes by counting tokens precisely before each call and
compressing history when the window approaches capacity.

---

## When to apply this skill

- Building a chat loop, agent, or pipeline that runs across many turns
- The user says "the model is forgetting things" or "context window is full"
- Ingesting large documents into a prompt
- Any async or background AI task that accumulates history over time

---

## Step 1 — Count tokens before every API call

Use `tiktoken` (not character counts — they are unreliable).

```python
import tiktoken

def count_tokens(messages: list[dict], model: str = "gpt-4o") -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")  # safe fallback
    total = 0
    for msg in messages:
        total += 4                          # per-message overhead
        total += len(enc.encode(msg.get("content") or ""))
    total += 2                              # reply-priming tokens
    return total
```

**Token rules of thumb:**
| Content | Approx tokens |
|---------|---------------|
| 1 English word | ~1.3 tokens |
| 1 line of code | ~5–10 tokens |
| 1 page of text | ~500 tokens |
| This skill file | ~800 tokens |

---

## Step 2 — Set a compression threshold, not a hard limit

Never wait until 100 %. You need headroom for:
- The compressed summary itself
- The model's response
- A few new messages before the next check

```python
MODEL_LIMITS = {
    "gpt-4o":            128_000,
    "gpt-4o-mini":       128_000,
    "claude-3-5-sonnet": 200_000,
    "claude-sonnet-4":   200_000,
}

THRESHOLD = 0.75  # compress at 75 % — safe for all models above

def should_compress(messages, model="gpt-4o") -> bool:
    limit = MODEL_LIMITS.get(model, 128_000)
    return count_tokens(messages, model) >= int(limit * THRESHOLD)
```

---

## Step 3 — Compress, not truncate

Truncation loses information. Summarisation preserves it.

```python
def compress(messages: list[dict], client, model: str = "gpt-4o") -> list[dict]:
    system  = [m for m in messages if m["role"] == "system"]    # always keep
    history = [m for m in messages if m["role"] != "system"]

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content":
                "Summarise this conversation concisely. Preserve all key facts, "
                "decisions, code, variable values, and open questions. "
                "Be thorough — this replaces the full history."},
            {"role": "user", "content": str(history)},
        ],
    )
    summary = resp.choices[0].message.content
    return system + [{"role": "assistant", "content": f"[SUMMARY]\n{summary}"}]
```

**Rules:**
- ✅ Always preserve the system prompt verbatim
- ✅ Prefer recent messages over old ones if you must choose
- ✅ Re-count tokens after compression to confirm you're back under threshold
- ❌ Never silently drop messages — always summarise

---

## Step 4 — Wire it into the chat loop

```python
def chat(messages, user_input, client, model="gpt-4o"):
    messages.append({"role": "user", "content": user_input})

    if should_compress(messages, model):
        used = count_tokens(messages, model)
        limit = MODEL_LIMITS.get(model, 128_000)
        print(f"⚠️  Context at {used / limit * 100:.0f}% — compressing...")
        messages = compress(messages, client, model)

    response = client.chat.completions.create(model=model, messages=messages)
    reply = response.choices[0].message.content
    messages.append({"role": "assistant", "content": reply})
    return reply, messages
```

---

## Step 5 — Use `ContextWindowManager` for production

The `context_window.py` module (included in every IRE project via `templates/`)
wraps all of the above plus a **background monitor thread**:

```python
from context_window import ContextWindowManager

# Basic usage
mgr = ContextWindowManager(model="gpt-4o")
messages = [{"role": "system", "content": "You are helpful."}]
messages = mgr.add_user("Hello")
messages = mgr.auto_compress(messages, client)   # compresses only if needed

# With background monitoring (logs token usage every 60 s)
with ContextWindowManager(model="gpt-4o", monitor=True, monitor_interval=60) as mgr:
    while True:
        messages = mgr.auto_compress(messages, client)
        # ... your chat loop here

# Inspect current state
report = mgr.report(messages)
print(report)
# → [gpt-4o] [████████░░░░░░░░░░░░░░░░░░░░░░] 12,430 / 128,000 tokens (9.7%) — 8 messages
print(report.to_dict())   # JSON-serialisable
```

---

## Checklist before shipping a long-running AI pipeline

- [ ] `tiktoken` installed and used (not `len(text)` or character counts)
- [ ] Compression threshold set at ≤80 % of the model limit
- [ ] System prompt excluded from compression
- [ ] Token count verified **after** compression (not just before)
- [ ] Background monitor thread running in production (optional but recommended)
- [ ] Compression events logged with before/after token counts
- [ ] Model limit table kept up to date as new models are added

---

## Key numbers

| Model | Context limit | Compress at (75%) |
|-------|-------------|-------------------|
| gpt-4o / gpt-4o-mini | 128,000 | 96,000 |
| gpt-4-turbo | 128,000 | 96,000 |
| gpt-3.5-turbo | 16,385 | 12,289 |
| Claude Sonnet / Opus | 200,000 | 150,000 |
| Claude Fable 5 / Mythos 5 | 200,000 | 150,000 |

---

## Claude Fable 5 / Mythos 5 — Context Budget Behavior

Fable 5 behaves differently from prior models when it detects remaining context
is limited. It can spontaneously suggest a new session, offer to summarize and
hand off, or trim its own output.

**Rule: do not surface explicit token counts to the model.** The progress bar in
`context_window.py` is for your observability — do not pass it to the model as
part of the prompt or system message.

If your harness must display token counts and the model sees them, add this
reassurance to the system prompt:

```
You have ample context remaining. Do not stop, summarize, or suggest a new
session on account of context limits. Continue the work.
```

**`MODEL_LIMITS` table — add Fable 5 entries:**

```python
MODEL_LIMITS = {
    "gpt-4o":                128_000,
    "gpt-4o-mini":           128_000,
    "gpt-4-turbo":           128_000,
    "gpt-3.5-turbo":         16_385,
    "claude-3-5-sonnet":     200_000,
    "claude-sonnet-4":       200_000,
    "claude-fable-5":        200_000,   # Fable 5
    "claude-mythos-5":       200_000,   # Mythos 5
}
```
