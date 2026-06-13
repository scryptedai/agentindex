#!/usr/bin/env python3
"""
Mission 1 — BigQuery connectivity smoke test.

Verifies GCP credentials and fetches the latest indexed Ethereum block number
from the public BigQuery dataset.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _util import fail, load_dotenv, ok, require_env  # noqa: E402

DEFAULT_DATASET = "bigquery-public-data.crypto_ethereum"
BLOCKS_TABLE = "blocks"


def latest_block_query(dataset: str) -> str:
    table = f"`{dataset}.{BLOCKS_TABLE}`"
    # Partition-pruned: blocks.timestamp is the partition column on this dataset.
    return f"""
SELECT
  number AS block_number,
  timestamp AS block_timestamp,
  `hash` AS block_hash
FROM {table}
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
ORDER BY number DESC
LIMIT 1
"""


def main() -> None:
    load_dotenv()

    creds_path = os.path.expanduser(require_env("GOOGLE_APPLICATION_CREDENTIALS"))
    if creds_path.startswith("AIza"):
        fail(
            "GOOGLE_APPLICATION_CREDENTIALS must be the path to a service account "
            "JSON key file, not an API key. Download the JSON from GCP Console → "
            "IAM → Service Accounts → Keys."
        )
    if not Path(creds_path).is_file():
        fail(f"GOOGLE_APPLICATION_CREDENTIALS file not found: {creds_path}")

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path

    ok(f"credentials file exists: {creds_path}")

    dataset = os.environ.get("BQ_DATASET", "").strip() or DEFAULT_DATASET
    max_bytes_raw = os.environ.get("BQ_MAX_BYTES_BILLED", "1073741824").strip()
    try:
        max_bytes = int(max_bytes_raw)
    except ValueError:
        fail(f"BQ_MAX_BYTES_BILLED must be an integer, got: {max_bytes_raw!r}")

    from google.cloud import bigquery

    client = bigquery.Client()
    query = latest_block_query(dataset)
    job_config = bigquery.QueryJobConfig(maximum_bytes_billed=max_bytes)

    ok(f"running query against {dataset}.{BLOCKS_TABLE} (max_bytes_billed={max_bytes:,})")

    try:
        result = client.query(query, job_config=job_config).result()
        row = next(iter(result), None)
    except Exception as exc:
        fail(f"BigQuery query failed: {exc}")

    if row is None:
        fail("query returned no rows — try widening the timestamp window")

    bytes_billed = client.get_job(result.job_id).total_bytes_billed or 0
    ok(f"bytes billed: {bytes_billed:,}")
    print(f"latest_block_number: {row.block_number}")
    print(f"block_timestamp: {row.block_timestamp}")
    print(f"block_hash: {row.block_hash}")


if __name__ == "__main__":
    main()
