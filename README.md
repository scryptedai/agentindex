# AgentIndex

Indexer that turns on-chain ERC-8004 agent data into a fast, local Postgres corpus.

## Setup

```bash
poetry install
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

**One-time backfill** — two uncapped since-launch queries (~380 GB total). Job IDs
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

**Daily / on-demand sync** — capped day-by-day for new data only:

```bash
poetry run agentindex-sync
```

| Command | Queries | Byte cap |
|---------|---------|----------|
| `agentindex-backfill` | 2 (identity + reputation, full history) | none |
| `agentindex-sync` | 1 per registry per missing day | `BQ_MAX_BYTES_BILLED` (default 3 GB) |

Configure via `.env`:

| Variable | Purpose |
|----------|---------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Service account JSON path |
| `BQ_MAX_BYTES_BILLED` | Cap for **sync only** (default 3 GB) |
| `ERC8004_LAUNCH_DATE` | Backfill start (default `2026-02-01`) |
| `BQ_LAG_DAYS` | Stop before today N days (default `1`) |
| `DATA_DIR` | Output root (default `data`) |

If you ran an older day-chunked backfill, remove `data/ethereum/` before re-running.
Backfill writes `identity/events.jsonl` and `reputation/events.jsonl`.

Smoketests live under `dev/smoketests/` for manual connectivity checks.
