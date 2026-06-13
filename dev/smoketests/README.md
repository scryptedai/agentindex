# Smoke tests

Opt-in scripts that require real credentials. They are **not** run in CI by default.

## Prerequisites

1. `poetry install` (from repo root)
2. Copy `.env.example` → `.env` and fill in values
3. Install mission-specific deps when needed, e.g. `poetry add google-cloud-bigquery`

## Running

From the repo root:

```bash
poetry run python dev/smoketests/bigquery_connect.py
```

Each script exits `0` on success, non-zero on failure. Missing credentials should
fail fast with a clear message (not hang or scan unbounded data).

## Mission 1 — BigQuery connect

`bigquery_connect.py` will verify:

- `GOOGLE_APPLICATION_CREDENTIALS` points to a readable service-account JSON
- The configured dataset/table path exists (path confirmed in `docs/SOURCES.md`, not assumed)
- A **partition-pruned**, **byte-capped** probe query succeeds and logs bytes billed

Do not hardcode registry addresses, topic0 hashes, or dataset paths until they are
fetched from the authoritative sources listed in BUILD.md §0.
