"""BigQuery ENSIP-25 discovery."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agentindex.bq.client import BigQueryRunner
from agentindex.bq.ens_queries import verified_agents_query
from agentindex.storage.ens_meta import EnsMeta
from agentindex.storage.jsonl import write_rows_replace
from agentindex.storage.paths import DataLayout


def _row_to_record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "agent_id": int(row["agent_id"]),
        "ens_name": str(row["ens_name"]).lower().strip(),
        "text_record_key": str(row["text_record_key"]),
        "text_record_value": str(row["text_record_value"]),
        "source": "bigquery",
        "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def discover_verified_agents(
    runner: BigQueryRunner,
    layout: DataLayout,
    meta: EnsMeta,
) -> tuple[int, int]:
    """Query ENS text records and write ``verified.jsonl``. Returns (rows, bytes_billed)."""
    query = verified_agents_query()
    rows, billed = runner.query_rows(query, "ens/verified", uncapped=False)
    records = [_row_to_record(row) for row in rows if row.get("agent_id") is not None]
    write_rows_replace(layout.ens_verified_path, records)

    meta.bq_last_run_at = EnsMeta.now_iso()
    meta.bq_bytes_billed = billed
    meta.verified_count = len(records)
    meta.save(layout.ens_meta_path)
    return len(records), billed
