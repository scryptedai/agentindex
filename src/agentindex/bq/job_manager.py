"""BigQuery job submit, poll, and resumable result download."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

from google.api_core import exceptions as gexc
from google.cloud import bigquery

from agentindex.storage.backfill_job import BackfillJob
from agentindex.storage.jsonl import _json_default, count_lines

POLL_INTERVAL_SEC = 3
CHECKPOINT_EVERY = 500
MAX_RETRIES = 12
RETRY_SLEEP_SEC = 5


def _fmt_bytes(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1e9:.2f} GB"
    if n >= 1_000_000:
        return f"{n / 1e6:.1f} MB"
    return f"{n:,} B"


def _fmt_usd_scan_bytes(n: int) -> str:
    # On-demand ~$6.25/TB (US, approximate).
    return f"~${n / 1e12 * 6.25:.2f}"


def explain_query(label: str, window_start: str, window_end: str, dry_run_bytes: int) -> None:
    print()
    print(f"=== {label} ===")
    print(f"  Window:     {window_start} → {window_end}")
    print(f"  Dry-run:    {_fmt_bytes(dry_run_bytes)} scanned ({_fmt_usd_scan_bytes(dry_run_bytes)})")
    print(
        "  Recovery:   job_id is saved before scan starts; re-run backfill to "
        "resume without re-billing if the query already finished."
    )


class BigQueryJobManager:
    def __init__(
        self,
        client: bigquery.Client | None = None,
        max_bytes_billed: int | None = None,
    ) -> None:
        self._client = client or bigquery.Client()
        self._max_bytes_billed = max_bytes_billed

    def dry_run_bytes(self, query: str) -> int:
        cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        job = self._client.query(query, job_config=cfg)
        return int(job.total_bytes_processed or 0)

    def submit(
        self,
        query: str,
        record: BackfillJob,
        *,
        uncapped: bool = False,
        persist: Callable[[], None],
    ) -> bigquery.QueryJob:
        if uncapped:
            cfg = bigquery.QueryJobConfig()
        else:
            cfg = bigquery.QueryJobConfig(maximum_bytes_billed=self._max_bytes_billed)

        job = self._client.query(query, job_config=cfg)
        record.job_id = job.job_id
        record.job_location = job.location
        record.touch_submitted()
        persist()
        print(f"  Submitted job {job.job_id} (location={job.location})")
        return job

    def get_job(self, record: BackfillJob) -> bigquery.QueryJob:
        if not record.job_id:
            raise ValueError("No job_id on record")
        return self._client.get_job(record.job_id, location=record.job_location)

    def wait_until_done(
        self,
        record: BackfillJob,
        persist: Callable[[], None],
    ) -> bigquery.QueryJob:
        job = self.get_job(record)

        while True:
            try:
                job.reload()
            except gexc.GoogleAPIError as exc:
                print(f"  Network/API error polling job (will retry): {exc}", file=sys.stderr)
                time.sleep(RETRY_SLEEP_SEC)
                continue

            state = job.state
            if state != record.phase and state == "RUNNING":
                record.mark_running()
                persist()

            if state == "DONE":
                if job.error_result:
                    msg = str(job.error_result)
                    record.mark_failed(msg)
                    persist()
                    raise RuntimeError(f"BigQuery job failed: {msg}")
                billed = int(job.total_bytes_billed or 0)
                total_rows = int(job.num_dml_affected_rows or 0) or None
                if job.destination:
                    table = self._client.get_table(job.destination)
                    total_rows = int(table.num_rows or 0)
                record.mark_downloading(billed, total_rows)
                persist()
                print(
                    f"  Job DONE: billed {_fmt_bytes(billed)}"
                    + (f", {total_rows:,} rows ready" if total_rows is not None else "")
                )
                return job

            print(f"  BigQuery state: {state} …")
            time.sleep(POLL_INTERVAL_SEC)

    def download_results(
        self,
        job: bigquery.QueryJob,
        output_path: Path,
        record: BackfillJob,
        persist: Callable[[], None],
    ) -> tuple[int, dict[str, Any] | None]:
        """Stream query results to JSONL. Resumes via start_index without re-scanning."""
        if not job.destination:
            raise RuntimeError("Job has no destination table: cannot download results")

        start_index = record.rows_written
        if start_index == 0 and output_path.is_file():
            # Partial file without checkpoint: trust line count.
            start_index = count_lines(output_path)
            record.rows_written = start_index

        mode = "a" if start_index > 0 else "w"
        if start_index > 0:
            print(f"  Resuming download at row {start_index:,} (no re-scan)")

        rows = self._client.list_rows(job.destination, start_index=start_index)
        last_row: dict[str, Any] | None = None
        written = start_index

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open(mode, encoding="utf-8") as fh:
            for row in rows:
                item = dict(row.items())
                fh.write(json.dumps(item, default=_json_default, ensure_ascii=False))
                fh.write("\n")
                last_row = item
                written += 1
                if written % CHECKPOINT_EVERY == 0:
                    record.rows_written = written
                    persist()
                    _print_progress(written, record.rows_total)

        record.mark_complete(written)
        persist()
        _print_progress(written, record.rows_total, done=True)
        return written, last_row

    def recover_or_raise(
        self,
        record: BackfillJob,
        persist: Callable[[], None],
    ) -> bigquery.QueryJob | None:
        """Return an existing job if recoverable, else None."""
        if record.phase == "complete":
            return None
        if not record.job_id:
            return None

        try:
            job = self.get_job(record)
        except gexc.NotFound:
            record.mark_expired(f"job_id {record.job_id} not found (results may have expired)")
            persist()
            print(f"  Job {record.job_id} expired: will submit a new query")
            return None

        job.reload()
        if job.state == "DONE":
            if job.error_result:
                record.mark_failed(str(job.error_result))
                persist()
                raise RuntimeError(f"Previous job failed: {job.error_result}")
            if record.phase in ("submitted", "running"):
                billed = int(job.total_bytes_billed or 0)
                total_rows = None
                if job.destination:
                    table = self._client.get_table(job.destination)
                    total_rows = int(table.num_rows or 0)
                record.mark_downloading(billed, total_rows)
                persist()
            print(f"  Recovered completed job {record.job_id}: download only, no re-scan")
            return job

        if job.state in ("PENDING", "RUNNING"):
            print(f"  Recovered in-flight job {record.job_id} (state={job.state})")
            record.mark_running()
            persist()
            return job

        record.mark_expired(f"job in unexpected state {job.state}")
        persist()
        return None


def _print_progress(written: int, total: int | None, *, done: bool = False) -> None:
    if total:
        pct = min(100, written * 100 // total)
        bar = _bar(pct)
        suffix = "done" if done else "downloading"
        print(f"\r  [{bar}] {written:,}/{total:,} rows ({suffix})", end="", flush=True)
        if done:
            print()
    elif done:
        print(f"  Downloaded {written:,} rows")


def _bar(pct: int, width: int = 24) -> str:
    filled = int(width * pct / 100)
    return "█" * filled + "░" * (width - filled)
