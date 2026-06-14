"""Persisted BigQuery backfill job state for crash/network recovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class BackfillJob:
    """Tracks one registry backfill query end-to-end.

    Phases:
      submitted: job_id saved, query queued on BigQuery
      running: BigQuery still scanning (billable work in flight)
      downloading: query DONE, streaming rows to local JSONL
      complete: rows on disk, safe to skip on re-run
      failed: terminal error; inspect `error` and re-run
      expired: job_id no longer recoverable; will submit fresh query
    """

    registry: str
    phase: str = "submitted"
    job_id: str | None = None
    job_location: str | None = None
    dry_run_bytes: int = 0
    bytes_billed: int | None = None
    rows_total: int | None = None
    rows_written: int = 0
    output_path: str = ""
    window_start: str = ""
    window_end: str = ""
    submitted_at: str | None = None
    finished_at: str | None = None
    error: str | None = None

    def touch_submitted(self) -> None:
        self.phase = "submitted"
        self.submitted_at = _now_iso()
        self.error = None

    def mark_running(self) -> None:
        self.phase = "running"

    def mark_downloading(self, bytes_billed: int, rows_total: int | None) -> None:
        self.phase = "downloading"
        self.bytes_billed = bytes_billed
        self.rows_total = rows_total

    def mark_complete(self, rows_written: int) -> None:
        self.phase = "complete"
        self.rows_written = rows_written
        self.finished_at = _now_iso()
        self.error = None

    def mark_failed(self, message: str) -> None:
        self.phase = "failed"
        self.error = message
        self.finished_at = _now_iso()

    def mark_expired(self, message: str) -> None:
        self.phase = "expired"
        self.error = message


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
