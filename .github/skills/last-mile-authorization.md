---
name: last-mile-authorization
description: >
  Authorization-at-point-of-use (last-mile authorization) for the Agentic IRE
  platform. Use whenever an agent reads data, writes data, executes an action,
  or calls an external API. Enforces Zero Trust: authorization is validated at
  the moment of access — not at session start — through a central Policy
  Decision Point. Cached authorization decisions are never treated as permanent.
---

# Last-Mile Authorization (Authorization at Point of Use)

Access permissions change at any time — a user may change roles, lose access,
change organizations, or leave the company, and data classification may change
mid-workflow. Therefore authorization **must be evaluated at the exact moment**
an agent attempts to read data, modify data, execute an action, call an API, or
access a sensitive record.

This follows Zero Trust: **access is continuously validated, never assumed.**

> **IRE Principle:** A permission granted at session start is not a permission
> that still holds at the moment of use. Re-check every time.

---

## The rule

Replace *authorize-once* with *authorize-at-use*:

```
❌ Authorize-once (forbidden)          ✅ Authorize-at-use (required)
─────────────────────────────         ──────────────────────────────
User starts session                    Agent requests data
        │                                      │
        ▼                                      ▼
Access approved                         Policy Decision Point (PDP)
        │                                      │
        ▼                                      ▼
Agent uses access forever              Authorization validation
                                               │
                                               ▼
                                       Access granted or denied
```

---

## Required controls

1. **Check at every access event.** Authorization is validated before *every*
   data read, *every* write, and *every* external API call — not once per session.
2. **Never treat cached decisions as permanent.** A prior "allow" may not hold
   now. Re-evaluate permissions at execution time. Cache only with a short TTL
   and re-validate on expiry.
3. **Central enforcement.** Route every decision through a single governance-layer
   Policy Decision Point (PDP). Do not scatter ad-hoc `if user.role == ...`
   checks across call sites.
4. **Deny-by-default.** If the PDP cannot positively confirm authorization, deny.
5. **Log every denial.** Access-denial events must be logged, attributable to the
   agent identity, and auditable.

---

## Required pattern — every data access / action / external call

Wrap the operation in a point-of-use check against the PDP:

```python
# Do NOT rely on a permission captured at session start.
# Re-validate at the exact moment of use.
decision = pdp.authorize(
    agent_id=agent.id,          # the agent's own identity (not the user's)
    action="read",              # read | write | execute | call_api
    resource=incident.sys_id,   # the specific resource being touched
    context=request_context,    # fresh role/classification at this instant
)
if not decision.allowed:
    audit_log.deny(agent_id=agent.id, action="read", resource=incident.sys_id,
                   reason=decision.reason)
    raise AuthorizationError(decision.reason)

# Only now perform the operation.
record = data_lake.read(incident.sys_id)
```

For external API calls and writes, the same gate applies **before** the call:

```python
if not pdp.authorize(agent.id, "call_api", endpoint, ctx).allowed:
    raise AuthorizationError("point-of-use check failed")
response = httpx.post(endpoint, ...)
```

---

## Anti-patterns to reject in review

- Capturing `allowed = check_permission(...)` at session start and reusing it later.
- A long-lived token or scope object passed around and trusted for the whole run.
- Authorization checks only at the API boundary but not before internal data reads.
- Treating a cached/allowlisted decision as permanent (no TTL, no re-check).
- Per-call-site inline role checks instead of a central PDP call.

---

## Relationship to other skills

- **`singapore-ai-governance`** — supplies the agent identity + bounded,
  least-privilege model this skill validates *at the moment of use*. Use both:
  identity/least-privilege define *what an agent may do*; last-mile authorization
  enforces *whether it may do it right now*.
- **`data-egress-guardrail`** — a destination check before writing outside the
  repo. Last-mile authorization is the broader per-access gate; run the egress
  guardrail as the final step for external writes.
- **`avoiding-agent-conflicts`** — pairs with kill switches / fail-safes.

---

## Escalation

If no Policy Decision Point exists in the project yet, **stop and flag it** — do
not silently fall back to session-time authorization. Point-of-use enforcement is
a Zero Trust requirement, not an optimization.
