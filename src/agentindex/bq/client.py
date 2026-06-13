"""BigQuery execution with optional byte caps."""

from __future__ import annotations

from typing import Any

from google.cloud import bigquery


class BigQueryRunner:
    def __init__(self, max_bytes_billed: int | None) -> None:
        self._client = bigquery.Client()
        self.max_bytes_billed = max_bytes_billed

    def dry_run_bytes(self, query: str) -> int:
        cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        job = self._client.query(query, job_config=cfg)
        return int(job.total_bytes_processed or 0)

    def query_rows(
        self,
        query: str,
        label: str,
        *,
        uncapped: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        estimated = self.dry_run_bytes(query)
        cap_label = "none" if uncapped else f"{self.max_bytes_billed:,}"
        print(f"{label}: dry-run estimate {estimated:,} bytes (cap={cap_label})")

        if not uncapped:
            if self.max_bytes_billed is None:
                raise RuntimeError(f"{label}: capped query but max_bytes_billed is unset")
            if estimated > self.max_bytes_billed:
                raise RuntimeError(
                    f"{label}: dry-run {estimated:,} bytes exceeds cap "
                    f"{self.max_bytes_billed:,}"
                )
            cfg = bigquery.QueryJobConfig(maximum_bytes_billed=self.max_bytes_billed)
        else:
            cfg = bigquery.QueryJobConfig()

        job = self._client.query(query, job_config=cfg)
        rows = [dict(row.items()) for row in job.result()]
        billed = self._client.get_job(job.job_id).total_bytes_billed or 0
        return rows, int(billed)
