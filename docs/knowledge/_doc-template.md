---
# ─────────────────────────────────────────────────────────────────────────────
# IRE Knowledge Document Template
# Copy this file, rename it, and fill in the front matter before writing content.
# Valid values for each field are in docs/ire-taxonomy.yaml
# ─────────────────────────────────────────────────────────────────────────────
ire_doc:
  # What kind of document is this? (see ire-taxonomy.yaml → types)
  type: knowledge

  # Which IRE area does this belong to? (see ire-taxonomy.yaml → areas)
  area: cross-cutting

  # What lens should a reader apply? (see ire-taxonomy.yaml → perspectives)
  perspective: any

  # What does the author need from the reader? (see ire-taxonomy.yaml → intents)
  intent: knowledge-capture

  # Intel username of the primary author
  author: ""

  # ISO date this document was created
  created: "2026-07-29"

  # ISO date of last significant content change (update when content changes)
  updated: "2026-07-29"

  # Freeform status: draft | review | approved | superseded
  status: draft

  # ── Optional v1.1 fields ─────────────────────────────────────────────────
  # IRE sub-project this doc belongs to (optional — use in multi-project repos)
  # Examples: ire-observability | ire-sla | ire-predictiveanalytics | ire-datalake
  # project: ""

  # Filename of the document this replaces (optional — for decisions and runbooks)
  # supersedes: ""

  # ISO date after which this document should be reviewed or retired (optional)
  # Useful for status snapshots and runbooks that go stale.
  # expires: ""

  # Schema version — do not edit; used by validate_knowledge_docs.py
  schema_version: "1.1"

  # ── AI indexing block ────────────────────────────────────────────────────
  # Used by RAG pipelines and AI summarization tools.
  ai_index:
    # One sentence telling AI how to summarize this document.
    # Example: "Summarize this as a ServiceNow CMDB change justification"
    summary_prompt: ""

    # Tags for indexing. Use values from ire-taxonomy.yaml where possible.
    tags: []

    # Set to true if this document should NOT be summarized or indexed by AI
    do_not_summarize: false
---

# Title

<!-- Write your document content below this line.
     The front matter above is for AI tools — it does not appear in rendered output.

     Suggested structure based on document type:

     DECISION:      ## Context | ## Options Considered | ## Decision | ## Rejected Alternatives
     RUNBOOK:       ## Prerequisites | ## Steps | ## Verification | ## Rollback
     KNOWLEDGE:     ## Overview | ## Detail | ## Examples | ## Related
     EMAIL:         ## Summary | ## Key Points | ## Action Items | ## Background
     RETROSPECTIVE: ## What Went Well | ## What Didn't | ## Action Items
     STATUS:        ## Current State | ## Blockers | ## Next Steps
-->
