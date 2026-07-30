---
name: paginating-api-fetches
description: >
  Pagination pattern for large API and dataset fetches. Use whenever calling any
  endpoint that returns a subset of results with a total/count field, or when
  fetching more than one page of data. Prevents silent data truncation from
  assuming the first page is the full dataset.
---

# Paginating API Fetches

**Never assume the first page is the full dataset.** Any API that returns `total`,
`count`, or a similar field is telling you there is more data. Always paginate.

---

## The Rules

1. **Always paginate** â€” loop until `offset >= total` or the page returns zero rows.
2. **Check `total`** â€” compare `total` against `offset + len(page_rows)` after every page.
3. **Use `page_size=1000`** (or the API's documented maximum) to minimise round-trips.
4. **Log progress** for datasets larger than 10,000 rows: `fetched N/total`.
5. **Expose `page_size` and `offset`** as parameters on every paginated helper function.

---

## Reference Implementation

`get_all_incidents()` in `src/ire_client.py` is the canonical pattern for this project.
Use it as the model for all new paginated helpers.

```python
def get_all_records(
    endpoint: str,
    *,
    params: dict | None = None,
    page_size: int = 1000,
) -> list[dict]:
    """Fetch ALL records from a paginated endpoint.

    Loops until offset >= total or the page returns no rows.
    Handles both list-of-lists (columnar) and list-of-dicts response shapes.
    """
    rows: list[dict] = []
    offset = 0
    columns: list[str] = []
    params = dict(params or {})

    with _client() as c:
        while True:
            params["limit"] = page_size
            params["offset"] = offset

            resp = c.get(endpoint, params=params).raise_for_status().json()

            if not columns:
                columns = resp.get("columns", [])
            page_rows = resp.get("rows", [])

            # Handle columnar (list-of-lists) or dict responses
            if page_rows and isinstance(page_rows[0], list):
                rows.extend(dict(zip(columns, row)) for row in page_rows)
            else:
                rows.extend(page_rows)

            total = resp.get("total", 0)
            offset += len(page_rows)

            if len(rows) % 10_000 < page_size:            # log every ~10K rows
                print(f"  fetched {len(rows):,} / {total:,}")

            if not page_rows or offset >= total:
                break

    return rows
```

---

## Anti-Patterns

```python
# BAD â€” assumes first page is complete
resp = client.get("/incidents/raw", params={"limit": 500}).json()
rows = resp["rows"]   # silently drops everything after row 500

# BAD â€” uses a hard-coded limit that may be less than total
rows = get_incidents_raw(limit=200_000)  # API may cap at 100K; you'd never know

# GOOD â€” paginate properly
rows = get_all_records("/incidents/raw", params={"months": 3}, page_size=1000)
print(f"Fetched {len(rows):,} total rows")
```

---

## Response Shape Variations

Different endpoints return data differently â€” handle both:

```python
# Shape 1: columnar (list-of-lists + separate columns array)
{
  "columns": ["number", "opened_at", "priority"],
  "rows": [["INC001", "2026-06-01", "P1"], ["INC002", "2026-06-02", "P3"]],
  "total": 12345
}

# Shape 2: list-of-dicts
{
  "rows": [{"number": "INC001", "opened_at": "2026-06-01"}, ...],
  "total": 12345
}

# Normalise with:
if page_rows and isinstance(page_rows[0], list):
    rows.extend(dict(zip(columns, row)) for row in page_rows)
else:
    rows.extend(page_rows)
```

---

## Checklist

```
Before writing any API fetch:
[ ] Does the endpoint return a "total" / "count" field?
[ ] Is my fetch wrapped in a pagination loop?
[ ] Does the loop terminate on: empty page OR offset >= total?
[ ] Is page_size set to 1000 (or API max)?
[ ] Does the function expose page_size and offset as parameters?
[ ] Is progress logged for datasets > 10K rows?
[ ] Is the full count verified after fetch (len(rows) vs total)?
```

---

## When to invoke this skill

| Trigger | What to do |
|---------|-----------|
| Any new API fetch helper | Check for `total` field; add pagination loop |
| Fetching incidents, changes, or any ITSM data | Use `fetch_raw_incidents_windowed()` pattern |
| "Only got N rows but expected more" | Add pagination â€” you're missing pages |
| Helper function with a `limit=` param | Verify the loop goes past the first page |


