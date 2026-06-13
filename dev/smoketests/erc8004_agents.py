#!/usr/bin/env python3
"""
Mission 2 — ERC-8004 agent registry smoke test.

Runs reference queries from the workshop gist (BUILD.md §0) against
goog_blockchain_ethereum_mainnet_us.logs. Values are reference-only until
pinned in docs/SOURCES.md.

The gist's open-ended launch filter (>= 2026-01-28) scans ~192 GB. This
smoketest uses a tight block_timestamp window (default: one hour on 2026-02-01)
so it fits BQ_MAX_BYTES_BILLED.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _util import fail, load_dotenv, ok, require_env  # noqa: E402

# Reference values from https://gist.github.com/godeva/040270ac2924501063d875b302cf2e91
LOGS_TABLE = "bigquery-public-data.goog_blockchain_ethereum_mainnet_us.logs"
IDENTITY_REGISTRY = "0x8004a169fb4a3325136eb29fa0ceb6d2e539a432"
REGISTERED_TOPIC0 = (
    "0xca52e62c367d81bb2e328eb795f7c7ba24afb478408a26c0e201d155c449bc4a"
)
DEFAULT_PROBE_START = "2026-02-01 05:00:00"
DEFAULT_PROBE_END = "2026-02-01 06:00:00"


def time_filter(start: str, end: str) -> str:
    return (
        f"block_timestamp >= TIMESTAMP '{start}' "
        f"AND block_timestamp < TIMESTAMP '{end}'"
    )


def adoption_curve_query(start: str, end: str) -> str:
    return f"""
SELECT
  DATE(block_timestamp) AS day,
  COUNT(*) AS new_agents
FROM `{LOGS_TABLE}`
WHERE address = '{IDENTITY_REGISTRY}'
  AND {time_filter(start, end)}
  AND topics[SAFE_OFFSET(0)] = '{REGISTERED_TOPIC0}'
GROUP BY day
ORDER BY day
"""


def registered_agents_query(start: str, end: str, limit: int = 10) -> str:
    return f"""
SELECT
  SAFE_CAST(topics[SAFE_OFFSET(1)] AS INT64) AS agent_id,
  CONCAT('0x', SUBSTR(topics[SAFE_OFFSET(2)], 27)) AS owner,
  SAFE_CONVERT_BYTES_TO_STRING(FROM_HEX(SUBSTR(
    data,
    131,
    2 * SAFE_CAST(CONCAT('0x', SUBSTR(data, 67, 64)) AS INT64)
  ))) AS agent_uri,
  block_timestamp
FROM `{LOGS_TABLE}`
WHERE address = '{IDENTITY_REGISTRY}'
  AND topics[SAFE_OFFSET(0)] = '{REGISTERED_TOPIC0}'
  AND {time_filter(start, end)}
ORDER BY block_timestamp DESC
LIMIT {limit}
"""


def setup_client():
    load_dotenv()

    creds_path = os.path.expanduser(require_env("GOOGLE_APPLICATION_CREDENTIALS"))
    if creds_path.startswith("AIza"):
        fail("GOOGLE_APPLICATION_CREDENTIALS must be a service account JSON file path")
    if not Path(creds_path).is_file():
        fail(f"GOOGLE_APPLICATION_CREDENTIALS file not found: {creds_path}")

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
    ok(f"credentials file exists: {creds_path}")

    max_bytes_raw = os.environ.get("BQ_MAX_BYTES_BILLED", "1073741824").strip()
    try:
        max_bytes = int(max_bytes_raw)
    except ValueError:
        fail(f"BQ_MAX_BYTES_BILLED must be an integer, got: {max_bytes_raw!r}")

    probe_start = os.environ.get("BQ_PROBE_START", DEFAULT_PROBE_START).strip()
    probe_end = os.environ.get("BQ_PROBE_END", DEFAULT_PROBE_END).strip()

    from google.cloud import bigquery

    return bigquery.Client(), max_bytes, probe_start, probe_end


def run_query(client, query: str, max_bytes: int, label: str):
    from google.cloud import bigquery

    ok(f"{label} (max_bytes_billed={max_bytes:,})")
    job_config = bigquery.QueryJobConfig(maximum_bytes_billed=max_bytes)
    try:
        job = client.query(query, job_config=job_config)
        rows = list(job.result())
    except Exception as exc:
        fail(f"{label} failed: {exc}")

    billed = client.get_job(job.job_id).total_bytes_billed or 0
    ok(f"{label}: {len(rows)} rows, bytes billed: {billed:,}")
    return rows, billed


def main() -> None:
    client, max_bytes, probe_start, probe_end = setup_client()
    ok(f"probe window: [{probe_start}, {probe_end})")

    print("\n--- Query 1: registrations in probe window ---")
    adoption_rows, _ = run_query(
        client, adoption_curve_query(probe_start, probe_end), max_bytes, "adoption curve"
    )
    if not adoption_rows:
        fail("adoption curve returned no rows — widen BQ_PROBE_START/END")
    for row in adoption_rows:
        print(f"  {row.day}: {row.new_agents} new agents")

    print("\n--- Query 2: registered agents (gist decode) ---")
    agent_rows, _ = run_query(
        client,
        registered_agents_query(probe_start, probe_end),
        max_bytes,
        "registered agents",
    )
    if not agent_rows:
        fail("registered agents query returned no rows")
    for row in agent_rows:
        uri = row.agent_uri or ""
        if len(uri) > 80:
            uri = uri[:77] + "..."
        print(
            f"  agent_id={row.agent_id} owner={row.owner} "
            f"at={row.block_timestamp} uri={uri}"
        )


if __name__ == "__main__":
    main()
