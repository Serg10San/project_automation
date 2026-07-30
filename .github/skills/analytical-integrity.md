---
name: analytical-integrity
description: >
  Verifiable-claims standard for data analysis. Use whenever producing incident
  reports, KPI findings, trend analysis, or any data-derived insight. Enforces
  citation, VERIFIED/INFERRED/UNVERIFIED tagging, exportable evidence, and
  systemic pattern detection. Prevents hallucinated numbers and unsupported assertions.
---

# Analytical Integrity

Every insight, finding, or assertion **must** be backed by a verifiable source.
All analysis is **analytical** (derived from data) â€” never **speculative**
(generated from pattern-matching on training memory).

---

## The Seven Rules

### Rule 1 â€” Citation required for every claim

For every data-derived insight, always include:

- The query or code used to produce it (inline snippet or reference to a script)
- The raw count / value returned (e.g. `68 incidents matched filter`)
- The date range and filters applied (e.g. `months=3, priority=P1-Critical, service_offering=Managed Hosting`)

```python
# Good â€” cites the source
# [VERIFIED] 68 P1 incidents | source: fetch_raw_incidents_windowed(months=3) filtered on
# service_offering=077f713b..., priority=P1-Critical | run: 2026-06-30T16:40Z

# Bad â€” no source
# "There are about 70 P1 incidents in Managed Hosting"
```

---

### Rule 2 â€” No model hallucinations

- **Never generate a number, trend, or pattern from memory** â€” only from a live query or saved dataset.
- **Never extrapolate** ("probably", "likely around", "typically") without explicit data support.
- If the data hasn't been fetched yet, say so and fetch it before making any claim.
- **Never fabricate field names, API parameters, or column values.** If unsure whether a field
  exists, fetch a single raw record first (`limit=1`) and inspect the actual keys.

---

### Rule 3 â€” Flag every claim with its epistemic status

| Tag | Meaning | When to use |
|-----|---------|-------------|
| `[VERIFIED]` | Confirmed by a reproducible query against live data | Exact field match, counted from raw rows |
| `[INFERRED]` | Derived from indirect evidence | Free-text keyword analysis, correlation without causal proof |
| `[UNVERIFIED]` | Not yet confirmed against live data | Must be resolved before acting on it |

```markdown
[VERIFIED]  410 Managed Hosting incidents in the last 3 months.
[INFERRED]  293 of these are auto-resolved alerts (short_description ends "- Ok").
[UNVERIFIED] No Problem records appear to exist for repeat CIs â€” needs PRB table query to confirm.
```

---

### Rule 4 â€” Exportable evidence required for significant findings

Every significant finding **must** produce an artefact a human can independently inspect:

- **CSV export** â€” write results to `data/<report-name>.csv` (opens in Excel / Sheets)
- **Reproducible script** â€” save fetch + analysis as `data/gen_<report-name>.py`
- **Direct links** â€” for ServiceNow records, include full URL:
  `https://<instance>.service-now.com/nav_to.do?uri=incident.do?sys_id=<sys_id>`
- **Self-contained HTML** â€” dashboards must embed data, not require a live API call to render

```python
# Canonical output pattern
_write_csv("my_findings.csv", rows, fieldnames)   # human-inspectable
path.write_text(html, encoding="utf-8")            # self-contained report
print("Verify: python data/gen_my_findings.py")   # reproducibility path
```

---

### Rule 5 â€” Systemic pattern detection (required for incident analysis)

When analysing incidents, look beyond individual tickets:

| Pattern | How to detect | What to flag |
|---------|--------------|-------------|
| **Repeat offenders** | Count by `cmdb_ci`, assignment group, service offering | Any CI or group appearing in >10% of population |
| **Temporal clustering** | Bin `opened_at` by hour and weekday | Peaks within same hour / same day of week |
| **Blast-radius mapping** | For each top CI, list affected services and teams | CI name alone is insufficient |
| **MTTR stratification** | Mean time-to-resolve by group Ã— priority | Groups with MTTR > 2Ã— median |
| **Recurrence detection** | Same `cmdb_ci` closed and reopened within 30 days | Recurrence rate as % of total |
| **Correlation, not causation** | Label as `[CORRELATED]` unless a change record confirms cause | Never say "X caused Y" without a linked `change_request` |

All pattern outputs **must** be exported (CSV + optional HTML) per Rule 4.

---

### Rule 6 â€” Show the verification path

After stating any finding, include a one-liner to reproduce it:

```python
# Verify: run this to reproduce the finding
python data/gen_incident_profile.py
```

---

### Rule 7 â€” Self-check before responding

Before presenting any finding:

- Ask: *"Did I compute this, or am I recalling it from context?"*
- If recalling: re-run the query or mark it `[UNVERIFIED]`.
- If context says X but live data says Y, **trust the live data** and flag the discrepancy.

---

## Correct Pattern â€” Example

```markdown
**Finding:** 4 CIs account for 48% of Managed Hosting P1s. [INFERRED]
**Source:** short_description keyword frequency, 68 P1 incidents, 2026-04 to 2026-06,
  priority=P1-Critical, service_offering=Managed Hosting.
**Note:** CI names inferred from free-text, not resolved from cmdb_ci sys_id field.
**Verify:** python data/gen_mh_p1_report.py â†’ check repeat_cis section.
**Export:** data/mh_p1_report.csv (68 rows: number, cmdb_ci, opened_at, resolved_at, mttr_hours)
```

---

## Workflow Checklist

```
Before presenting any data-derived finding:
[ ] Source query identified (script or inline code snippet)
[ ] Raw count / value cited (not "around X" or "approximately")
[ ] Date range and filters stated
[ ] Each claim tagged [VERIFIED], [INFERRED], or [UNVERIFIED]
[ ] Significant findings exported to CSV
[ ] Reproducible script saved as data/gen_<name>.py
[ ] Self-check: "Did I compute this, or recall it?" â€” if recall, re-run
[ ] Correlations labelled [CORRELATED] â€” no causal claims without change record
```

---

## When to invoke this skill

| Trigger | What to do |
|---------|-----------|
| Any incident / KPI analysis | Tag every number; export to CSV |
| "How manyâ€¦" / "What % â€¦" | Fetch live data before answering |
| "Trending up/down" | Require temporal data with timestamps; never estimate |
| Building a dashboard or HTML report | Embed data; script must be rerunnable |
| About to say "probably" or "likely" | Stop â€” fetch the data first |


