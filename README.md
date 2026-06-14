# AgentIndex

Indexer that turns on-chain ERC-8004 agent data into a fast, local SQLite corpus.

## Configuration

Network targets, registry addresses, BigQuery tables, and ENS settings live in
[`config/default.json`](config/default.json). Copy and edit for your deployment, or
point at another file with `AGENTINDEX_CONFIG`.

Each network entry can be enabled independently. Ethereum is enabled by default; Base
is included as a disabled template (no public BigQuery logs dataset yet). Agents that
register on multiple chains appear in `cross_registrations.jsonl` and the SQLite
`agent_registrations` table (parsed from registration JSON `registrations[]`).

Credentials and runtime overrides stay in `.env`:

| Variable | Purpose |
|----------|---------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Service account JSON path (required for ingest) |
| `BQ_MAX_BYTES_BILLED` | Cap for **sync** and ENS discovery (default 3 GB) |
| `AGENTINDEX_CONFIG` | Optional path to config JSON (default `config/default.json`) |

```bash
cp .env.example .env   # set GOOGLE_APPLICATION_CREDENTIALS
```

Poetry is configured to create the virtualenv at `.venv/` in the project root (`poetry.toml`).

## Ingest to disk (BigQuery → `data/`)

Lossless JSONL: raw log fields plus decoded ERC-8004 fields.

```
data/ethereum/
  meta.json
  identity/events.jsonl      # bulk backfill (one query)
  reputation/events.jsonl
  identity/2026-06-12.jsonl  # daily sync chunks (after backfill)
  reputation/2026-06-12.jsonl
```

**One-time backfill**: two uncapped since-launch queries (~380 GB total). Job IDs
and download progress are saved to `meta.json`; re-run after a network interrupt to
resume **without re-scanning** (if the BigQuery job already finished).

```bash
poetry run agentindex-backfill   # safe to re-run; resumes from job_id / row offset
```

**Recovery phases** (stored per registry in `meta.json` → `backfill_jobs`):

| Phase | Meaning | Re-run cost |
|-------|---------|-------------|
| `running` | Query still scanning on BigQuery | wait, no new query |
| `downloading` | Scan done, rows streaming to disk | download only, no re-scan |
| `complete` | JSONL on disk | skip |
| `expired` | job_id gone (~24h+); must submit fresh query | new scan |

BigQuery bills on **scan**, not on re-downloading results from a completed job.

**Daily / on-demand sync**: capped day-by-day for new data only:

```bash
poetry run agentindex-sync
```

| Command | Queries | Byte cap |
|---------|---------|----------|
| `agentindex-backfill` | 2 per enabled network (identity + reputation) | none |
| `agentindex-sync` | 1 per registry per missing day per network | `BQ_MAX_BYTES_BILLED` (default 3 GB) |

Backfill/sync iterate all **enabled** networks in config. Per-network settings
(`launch_date`, `lag_days`, `bigquery.logs_table`, registries, ENS) are in
`config/default.json`.

If you ran an older day-chunked backfill, remove `data/ethereum/` before re-running.
Backfill writes `identity/events.jsonl` and `reputation/events.jsonl`.

Smoketests live under `dev/smoketests/` for manual connectivity checks.

## Build SQLite index (`data/` → `agentindex.db`)

After ingest, rebuild the queryable corpus from JSONL. No BigQuery credentials needed.

```bash
poetry run agentindex-build
```

Writes `data/agentindex.db` (path set in config). Tables:

| Table | Contents |
|-------|----------|
| `agents` | Identity registry mints (`agent_id`, `owner`, `token_uri`, first seen) |
| `reputation_feedback` | One row per `NewFeedback` event |
| `reputation_agg` | Mean score per agent (non-revoked feedback) |
| `registries` | Per-registry watermark `(block_number, log_index)` |
| `ens_links` | Many-to-many agent ↔ ENS edges (`verified`, `claimed` flags per pair) |
| `agent_registrations` | Cross-network registry refs from registration JSON |

Example queries:

```sql
-- Newest agents
SELECT agent_id, owner, token_uri, first_seen_at
FROM agents ORDER BY first_seen_block DESC LIMIT 20;

-- Top-rated agents (min 3 reviews)
SELECT a.agent_id, a.token_uri, r.composite, r.n_feedback
FROM reputation_agg r
JOIN agents a USING (network_id, agent_id)
WHERE r.n_feedback >= 3
ORDER BY r.composite DESC LIMIT 20;

-- Agents registered since block
SELECT agent_id, owner, first_seen_block
FROM agents WHERE first_seen_block > 24500000;
```

Re-run `agentindex-build` after `agentindex-sync` to pick up new JSONL chunks.

## Web dashboard (`poetry run frontend`)

Dashboard over the local SQLite corpus. Copy and sybil signals are computed server-side from [`src/agentindex/frontend/narratives/`](src/agentindex/frontend/narratives/).

```bash
poetry run agentindex-build   # if needed
poetry run frontend           # http://127.0.0.1:8787
```

| Route | Purpose |
|-------|---------|
| `/` | Overview, Sybil Signals, Agent dossier, Reviewer lens, Identity graph, Explorer |
| `/api/bootstrap` | Full corpus + derived metrics + narrative copy (JSON) |
| `/api/agents/{id}` | Single-agent dossier on demand |
| `POST /api/reload` | Refresh cache after rebuild |
| `/api/download/db` | Download the SQLite index file |

Static UI lives in [`frontend/`](frontend/). Narrative rules in `reactions.json` fill titles, KPI notes, callouts, and sybil signal descriptions from corpus statistics.

Optional env: `FRONTEND_HOST`, `FRONTEND_PORT` (default `8787`), `FRONTEND_RELOAD=1` for dev.

## ENS enrichment (`data/ethereum/ens/`)

Two-phase pipeline: BigQuery for on-chain ENSIP-25 verifications, then HTTP fetch
for registration JSON to extract claimed `.eth` names.

```
data/ethereum/ens/
  meta.json
  verified.jsonl              # BigQuery: agent-registration[registry][agentId] text records
  claimed.jsonl               # one row per (agent_id, claimed_ens) edge
  cross_registrations.jsonl   # registrations[] from registration JSON (other chains)
  registrations/{agent_id}.json
```

**One-time ENS backfill:**

```bash
poetry run agentindex-ens-backfill   # BQ discovery + fetch all registration JSON
poetry run agentindex-build          # merge into ens_links table in SQLite
```

**Daily ENS sync:**

```bash
poetry run agentindex-ens-sync       # refresh BQ + fetch new/changed token_uri only
poetry run agentindex-build
```

| Command | What it does |
|---------|----------------|
| `agentindex-ens-backfill` | Full BQ scan + re-fetch all registration JSON |
| `agentindex-ens-sync` | Refresh BQ + fetch only new/changed URIs |
| `agentindex-build` | Loads `verified.jsonl` + `claimed.jsonl` → `ens_links` |

Example queries:

```sql
-- All ENS names for one agent
SELECT ens_name, verified, claimed
FROM ens_links WHERE agent_id = 26433;

-- All agents sharing one ENS name (two-sided lookup)
SELECT agent_id, verified, claimed
FROM ens_links WHERE ens_name = 'atv.eth';

-- Verified on-chain links only
SELECT agent_id, ens_name FROM ens_links WHERE verified = 1 ORDER BY ens_name;
```
