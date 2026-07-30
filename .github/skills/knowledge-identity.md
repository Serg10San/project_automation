---
name: knowledge-identity
description: >
  IRE Knowledge Identity Layer. Use when writing, reviewing, or ingesting any
  documentation in a project that has docs/ire-knowledge-schema.yaml present.
  Covers: reading documents with ire_doc front matter, drafting in an author's
  voice using their profile, categorizing content using the IRE taxonomy, and
  indexing documents for AI retrieval. Invoke when the words "document",
  "email", "knowledge", "summarize", "draft for me", or "write this up" appear.
---

# Knowledge Identity Skill

This skill applies when `docs/ire-knowledge-schema.yaml` exists in the project
with `enabled: true`.  It governs how AI tools **read**, **write**, and
**categorize** all documentation in the project.

---

## Step 1 — Check if the Layer is Active

```bash
# Feature is enabled if this file exists and has enabled: true
cat docs/ire-knowledge-schema.yaml
```

If the file is missing or `enabled: false`, skip this skill entirely.

---

## Step 2 — Reading a Document

When asked to summarize, extract, or analyze a document, **read the front matter
first**:

```yaml
---
ire_doc:
  type: decision          # what kind of doc is this?
  area: observability   # what IRE area does it belong to?
  perspective: sre        # read it through this lens
  intent: decision-request  # what does the author need from the reader?
  author: jmonroe
---
```

Apply these rules based on the front matter fields:

| Field | What to do |
|-------|-----------|
| `perspective: sre` | Interpret technical content through SRE/operational lens |
| `perspective: executive` | Surface outcomes and risks; suppress implementation detail |
| `perspective: product-owner` | Focus on requirements, acceptance criteria, stakeholder impact |
| `intent: decision-request` | Lead your response with a clear decision recommendation |
| `intent: action-required` | Extract action items as a numbered list with owners |
| `intent: fyi` | Summarize concisely; no action items expected |
| `intent: knowledge-capture` | Preserve detail; this is reference material |
| `type: email` | Keep summaries to 3 sentences unless asked for more |
| `type: decision` | Structure output as: Context → Options → Recommendation |

---

## Step 3 — Drafting in an Author's Voice

When asked to draft, write, or continue a document **on behalf of an author**:

1. Read `docs/authors/{username}.md` to load their writing profile
2. Match the `tone`, `structure`, and `vocabulary` fields exactly
3. Apply the `attribution_tag` at the end of any AI-drafted section
4. If no author profile exists, ask: *"Should I create a writing profile for you
   in docs/authors/?"*

**Key rule:** Do not invent a tone. If no profile exists, write neutrally and
flag that a profile would improve future drafts.

---

## Step 4 — Writing a New Document

When creating a new `.md` document in the project, **always add the front matter
block** from `docs/knowledge/_doc-template.md`.  Populate every field — do not
leave fields blank.

Consult `docs/ire-taxonomy.yaml` for valid values on:
- `type` — document classification
- `area` — IRE area
- `perspective` — intended reading lens
- `intent` — what the document asks of its reader

If a value you need is not in the taxonomy, propose adding it rather than
inventing an undeclared value.

---

## Step 5 — Indexing and Search

When asked *"find all documents about X"* or *"what do we have on Y"*, query
front matter fields rather than full-text searching:

```bash
# Find all decision documents in the observability area
grep -rl "area: observability" docs/knowledge/ | xargs grep -l "type: decision"

# Find all documents authored by jmonroe
grep -rl "author: jmonroe" docs/
```

For AI-assisted RAG pipelines, the `ai_index` block in the front matter provides
the `summary_prompt` (how to chunk/summarize this document) and `tags` (index
keys).  Always pass `summary_prompt` as the system instruction when embedding the
document.

---

## What This Skill Does NOT Cover

- It does not modify code files — only `.md` documentation
- It does not enforce schema on documents outside the `docs/` directory
  (though authors may apply it anywhere)
- It does not auto-generate author profiles — the author fills those in
