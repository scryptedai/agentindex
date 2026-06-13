# Smoke tests

Opt-in scripts that require real credentials. They are **not** run in CI by default.

## Prerequisites

1. `poetry install` (from repo root)
2. Copy `.env.example` → `.env` and fill in values
3. `google-cloud-bigquery` and `python-dotenv` are project dependencies

## Running

From the repo root:

```bash
poetry run python dev/smoketests/bigquery_connect.py
poetry run python dev/smoketests/erc8004_agents.py
poetry run python dev/smoketests/erc8004_day_index.py
```

Each script exits `0` on success, non-zero on failure. Missing credentials should
fail fast with a clear message (not hang or scan unbounded data).

Always set `BQ_MAX_BYTES_BILLED` — every query uses `maximum_bytes_billed`.

---

## Mission 1 — BigQuery connect

`bigquery_connect.py` verifies:

- `GOOGLE_APPLICATION_CREDENTIALS` points to a readable service-account JSON file
- A partition-pruned probe against `crypto_ethereum.blocks` succeeds
- Bytes billed are logged

Uses `BQ_DATASET` (default: `bigquery-public-data.crypto_ethereum`).

---

## Mission 2 — ERC-8004 agent registry

`erc8004_agents.py` runs adapted versions of the [workshop gist](https://gist.github.com/godeva/040270ac2924501063d875b302cf2e91)
queries (BUILD.md §0) against **`bigquery-public-data.goog_blockchain_ethereum_mainnet_us.logs`**.

**Query 1:** count `Registered` events in the probe window (adoption curve slice).

**Query 2:** decode `agent_id`, `owner`, and `agent_uri` from raw log topics/data.

### Reference constants (not pinned in `docs/SOURCES.md` yet)

| Constant | Value |
|----------|-------|
| Identity registry | `0x8004a169fb4a3325136eb29fa0ceb6d2e539a432` |
| `Registered` topic0 | `0xca52e62c367d81bb2e328eb795f7c7ba24afb478408a26c0e201d155c449bc4a` |
| Launch date (gist) | `2026-01-28` |

First registrations observed **2026-02-01** (Jan 28 window returned 0 events).

### Cost discipline — tight probe window required

The gist's open-ended filter (`block_timestamp >= '2026-01-28'`) dry-runs at **~192 GB**
and exceeds a 1 GB `BQ_MAX_BYTES_BILLED` cap.

Observed scan sizes on `goog_blockchain_ethereum_mainnet_us.logs` with address + topic0 filters:

| Window | Bytes (approx) |
|--------|----------------|
| 1 hour | ~210 MB |
| 1 day | ~1.4 GB |
| since launch | ~192 GB |

The smoketest defaults to a **1-hour window** on a day with known activity:

```env
BQ_PROBE_START=2026-02-01 05:00:00
BQ_PROBE_END=2026-02-01 06:00:00
```

Verified result (2026-02-01 05:00–06:00 UTC): **5 agents**, ~122 MB + ~191 MB billed
across the two queries.

### Example decoded agents (2026-02-01 05:00–06:00 UTC)

```
agent_id=22710  uri=https://ufc-mma-agent-production.up.railway.app/.well-known/erc8004.json
agent_id=22709  uri=ipfs://QmZyYPdcMaaMNCRXyiHXvPYK1DP8pfnCPBC4N9hPHnyhD8
```

Do not hardcode registry addresses or topic0 hashes in library code until confirmed
from the contracts repo ABI and recorded in `docs/SOURCES.md`.

---

## Mission 3 — One-day Identity + Reputation index slice

`erc8004_day_index.py` pulls **one calendar day** of mainnet logs for:

- **Identity registry** — decode all `Registered` events that day
- **Reputation registry** — decode all `NewFeedback` events that day

### Config

```env
BQ_PROBE_DAY=2026-02-01
BQ_MAX_BYTES_BILLED=3221225472
```

**Requires ~3 GB cap per query** (~2.3 GB scanned per registry per day, observed dry-run).
The script **dry-runs before each query** and aborts if the estimate exceeds the cap.

### Cost

Two queries per run (identity + reputation): expect **~4.3 GB total** billed for one day.

Verified default day `2026-02-01` has identity activity (70 registrations observed in prior probes).
