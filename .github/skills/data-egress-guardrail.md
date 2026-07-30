---
name: data-egress-guardrail
description: Pre-flight check — run before any skill that writes data outside the local repository (to-issues, to-prd, triage). Prevents Intel-internal data from being published to external or broadly-accessible systems.
disable-model-invocation: true
---

# Data Egress Guardrail

**Invoke this skill before any action that writes content outside the local filesystem** (publishing issues, PRDs, comments, webhooks, external APIs, or any network destination).

This guardrail exists because IRE projects process Intel-confidential data: incident records, SLA metrics, resiliency KPIs, observability telemetry, CMDB topology, and infrastructure health signals. That data must not appear in issue bodies, comments, PRD text, or any other externally-accessible location.

---

## Step 1 — Classify the destination

Determine where content will be written:

| Destination | Allowed? | Notes |
|-------------|----------|-------|
| `intel-innersource` GitHub (github.com/intel-innersource) | ✅ Yes | Intel-internal; still apply content rules below |
| Public `github.com` repos | ❌ No | Stop immediately |
| External SaaS (Jira, Linear, Slack, PagerDuty, etc.) | ❌ No | Stop immediately |
| Any URL outside `*.intel.com` or `*.corp.intel.com` | ❌ No | Stop immediately |

If the destination is not `intel-innersource` or another confirmed-internal Intel system, **stop and tell the user why you cannot proceed.**

---

## Step 2 — Scan the content for classified data

Before publishing, scan ALL content (titles, bodies, comments) for the following patterns:

### ❌ Never include in external-facing content

| Data type | Examples |
|-----------|---------|
| Raw incident records | INC numbers with description text, SLA breach details |
| ServiceNow field values | `short_description`, `work_notes`, caller names, assigned-to names |
| KPI / metric values | "MTTR was 4.2 hours", "P1 breach rate 12%", specific percentages or counts from live data |
| Infrastructure identifiers | server hostnames, IP addresses, CMDB CIs, service names from `data_lake.db` or `monitor.db` |
| API keys or credentials | Any `.env` values, tokens, keys |
| Personally identifiable info | Intel employee names, IDSID, email addresses pulled from data sources |

### ✅ Safe to include

- Feature descriptions, user stories, and acceptance criteria written in **general terms**
- Domain vocabulary from `CONTEXT.md` or ADRs (e.g., "incident SLA breach", "assignment group", "priority tier")
- Code snippets from the repository (source code, not data)
- Architecture decisions and design rationale
- Issue links and PR references

---

## Step 3 — Confirm before publishing

Present a pre-publish summary to the user:

```
📋 Pre-publish check
Destination: <org/repo or system name>
Items to publish: <count and type, e.g. "3 issues">

Content review:
  ✅ No raw incident data detected
  ✅ No metric values from live data sources
  ✅ No employee names / IDs
  ✅ No credentials or API keys
  ✅ No hostnames / IP addresses
  ✅ Destination is Intel-internal

Proceed? (yes / no)
```

If **any** item is ❌, do not publish. Revise the content to remove the classified data, then re-check.

---

## Step 4 — Log the action

After publishing, note in the conversation:

- What was published (type, count, destination URL or repo)
- Timestamp
- Confirmation that Step 2 checks passed

---

## Escalation

If you are unsure whether specific content is safe to publish, **stop and ask the user** before proceeding. Do not make assumptions about what is public vs. confidential.
