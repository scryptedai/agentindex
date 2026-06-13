"""Shared ERC-8004 reference constants and BigQuery helpers for smoketests."""

from __future__ import annotations

import os
from pathlib import Path

from _util import fail, load_dotenv, ok, require_env

# Reference: https://gist.github.com/godeva/040270ac2924501063d875b302cf2e91
LOGS_TABLE = "bigquery-public-data.goog_blockchain_ethereum_mainnet_us.logs"
IDENTITY_REGISTRY = "0x8004a169fb4a3325136eb29fa0ceb6d2e539a432"
REPUTATION_REGISTRY = "0x8004baa17c55a88189ae136b182e5fda19de9b63"
REGISTERED_TOPIC0 = (
    "0xca52e62c367d81bb2e328eb795f7c7ba24afb478408a26c0e201d155c449bc4a"
)
NEW_FEEDBACK_TOPIC0 = (
    "0x6a4a61743519c9d648a14e6493f47dbe3ff1aa29e7785c96c8326a205e58febc"
)
DEFAULT_PROBE_DAY = "2026-02-01"
# One day of filtered logs scans ~2.3 GB per registry (observed dry-run, Feb 2026).
MIN_BYTES_ONE_REGISTRY_DAY = 2_500_000_000


def day_bounds(day: str) -> tuple[str, str]:
    return f"{day} 00:00:00", f"{day} 23:59:59"


def time_filter(start: str, end: str) -> str:
    return (
        f"block_timestamp >= TIMESTAMP '{start}' "
        f"AND block_timestamp <= TIMESTAMP '{end}'"
    )


def setup_bq():
    load_dotenv()

    creds_path = os.path.expanduser(require_env("GOOGLE_APPLICATION_CREDENTIALS"))
    if creds_path.startswith("AIza"):
        fail("GOOGLE_APPLICATION_CREDENTIALS must be a service account JSON file path")
    if not Path(creds_path).is_file():
        fail(f"GOOGLE_APPLICATION_CREDENTIALS file not found: {creds_path}")

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
    ok(f"credentials file exists: {creds_path}")

    max_bytes_raw = os.environ.get("BQ_MAX_BYTES_BILLED", "2147483648").strip()
    try:
        max_bytes = int(max_bytes_raw)
    except ValueError:
        fail(f"BQ_MAX_BYTES_BILLED must be an integer, got: {max_bytes_raw!r}")

    probe_day = os.environ.get("BQ_PROBE_DAY", DEFAULT_PROBE_DAY).strip()
    start, end = day_bounds(probe_day)

    from google.cloud import bigquery

    return bigquery.Client(), max_bytes, probe_day, start, end


def dry_run_bytes(client, query: str) -> int:
    from google.cloud import bigquery

    cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    job = client.query(query, job_config=cfg)
    return int(job.total_bytes_processed or 0)


def run_query(client, query: str, max_bytes: int, label: str):
    from google.cloud import bigquery

    estimated = dry_run_bytes(client, query)
    ok(f"{label}: dry-run estimate {estimated:,} bytes")

    if estimated > max_bytes:
        fail(
            f"{label} dry-run ({estimated:,} bytes) exceeds BQ_MAX_BYTES_BILLED "
            f"({max_bytes:,}). Raise the cap or narrow BQ_PROBE_DAY."
        )

    job_config = bigquery.QueryJobConfig(maximum_bytes_billed=max_bytes)
    try:
        job = client.query(query, job_config=job_config)
        rows = list(job.result())
    except Exception as exc:
        fail(f"{label} failed: {exc}")

    billed = client.get_job(job.job_id).total_bytes_billed or 0
    ok(f"{label}: {len(rows)} rows, bytes billed: {billed:,}")
    return rows, billed
