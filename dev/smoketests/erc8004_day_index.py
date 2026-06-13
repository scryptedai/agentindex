#!/usr/bin/env python3
"""
Mission 3 — One-day index slice for Identity + Reputation registries.

Pulls a single calendar day of ERC-8004 events from mainnet logs (identity
Registered + reputation NewFeedback). Dry-runs each query before execution.

Expect ~2.3 GB scanned per registry per day. Set BQ_MAX_BYTES_BILLED >= 3 GB.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _erc8004 import (  # noqa: E402
    IDENTITY_REGISTRY,
    LOGS_TABLE,
    MIN_BYTES_ONE_REGISTRY_DAY,
    NEW_FEEDBACK_TOPIC0,
    REGISTERED_TOPIC0,
    REPUTATION_REGISTRY,
    run_query,
    setup_bq,
    time_filter,
)
from _util import fail, ok  # noqa: E402


def identity_agents_query(start: str, end: str) -> str:
    return f"""
SELECT
  SAFE_CAST(topics[SAFE_OFFSET(1)] AS INT64) AS agent_id,
  CONCAT('0x', SUBSTR(topics[SAFE_OFFSET(2)], 27)) AS owner,
  SAFE_CONVERT_BYTES_TO_STRING(FROM_HEX(SUBSTR(
    data,
    131,
    2 * SAFE_CAST(CONCAT('0x', SUBSTR(data, 67, 64)) AS INT64)
  ))) AS agent_uri,
  block_number,
  block_timestamp
FROM `{LOGS_TABLE}`
WHERE address = '{IDENTITY_REGISTRY}'
  AND topics[SAFE_OFFSET(0)] = '{REGISTERED_TOPIC0}'
  AND {time_filter(start, end)}
ORDER BY block_timestamp
"""


def reputation_feedback_query(start: str, end: str) -> str:
    return f"""
SELECT
  SAFE_CAST(topics[SAFE_OFFSET(1)] AS INT64) AS agent_id,
  CONCAT('0x', SUBSTR(topics[SAFE_OFFSET(2)], 27)) AS client,
  SAFE_CAST(CONCAT('0x', SUBSTR(data, 67, 64)) AS INT64) AS raw_value,
  SAFE_CAST(CONCAT('0x', SUBSTR(data, 131, 64)) AS INT64) AS value_decimals,
  block_number,
  block_timestamp
FROM `{LOGS_TABLE}`
WHERE address = '{REPUTATION_REGISTRY}'
  AND topics[SAFE_OFFSET(0)] = '{NEW_FEEDBACK_TOPIC0}'
  AND {time_filter(start, end)}
  AND SUBSTR(data, 67, 1) != 'f'
ORDER BY block_timestamp
"""


def truncate(text: str | None, n: int = 72) -> str:
    if not text:
        return ""
    return text if len(text) <= n else text[: n - 3] + "..."


def main() -> None:
    client, max_bytes, probe_day, start, end = setup_bq()
    ok(f"probe day: {probe_day} [{start}, {end}]")

    if max_bytes < MIN_BYTES_ONE_REGISTRY_DAY:
        fail(
            f"BQ_MAX_BYTES_BILLED ({max_bytes:,}) is below ~2.5 GB needed per "
            "registry-day query. Set BQ_MAX_BYTES_BILLED=3221225472 or higher."
        )

    print("\n--- Identity registry (Registered) ---")
    identity_rows, identity_billed = run_query(
        client, identity_agents_query(start, end), max_bytes, "identity"
    )
    print(f"  registrations: {len(identity_rows)}")
    for row in identity_rows[:5]:
        print(
            f"  agent_id={row.agent_id} owner={row.owner} "
            f"block={row.block_number} uri={truncate(row.agent_uri)}"
        )
    if len(identity_rows) > 5:
        print(f"  ... and {len(identity_rows) - 5} more")

    print("\n--- Reputation registry (NewFeedback) ---")
    rep_rows, rep_billed = run_query(
        client, reputation_feedback_query(start, end), max_bytes, "reputation"
    )
    print(f"  feedback events: {len(rep_rows)}")
    for row in rep_rows[:5]:
        score = row.raw_value / (10 ** row.value_decimals) if row.value_decimals else row.raw_value
        print(
            f"  agent_id={row.agent_id} client={row.client} "
            f"score={score} block={row.block_number}"
        )
    if len(rep_rows) > 5:
        print(f"  ... and {len(rep_rows) - 5} more")

    total_billed = identity_billed + rep_billed
    ok(f"total bytes billed: {total_billed:,} (~{total_billed / 1e9:.2f} GB)")


if __name__ == "__main__":
    main()
