# Dev

Manual integration checks and smoke tests for AgentIndex. These live outside the
`src/agentindex` package and hit real external services (BigQuery, Postgres, RPC).

Unit tests belong in `tests/` when we add them. This folder is for **"does it
actually connect?"** checks you run locally with credentials.

## Layout

```
dev/
  smoketests/     # one script per external dependency; run individually
```

## Milestones (from BUILD.md, Python port)

| Mission | Smoke test | Verifies |
|---------|------------|----------|
| 1 | `smoketests/bigquery_connect.py` | GCP auth, `crypto_ethereum.blocks`, bounded query |
| 2 | `smoketests/erc8004_agents.py` | ERC-8004 `Registered` events on `goog_blockchain_*`.logs |
| 3+ | TBD | Postgres migrate, incremental sync, … |

Open questions from BUILD §0 must be resolved **before** hardcoding values in
library code. Pin confirmed values in `docs/SOURCES.md` as they are verified.
