"""Ethereum ERC-8004 bulk backfill with resumable BigQuery jobs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from agentindex.bq.job_manager import BigQueryJobManager, explain_query
from agentindex.bq.queries import events_query, range_bounds
from agentindex.config import Settings
from agentindex.erc8004 import REGISTRIES, Registry
from agentindex.storage.backfill_job import BackfillJob
from agentindex.storage.meta import Meta
from agentindex.storage.paths import DataLayout


def _persist(meta: Meta, layout: DataLayout) -> None:
    meta.save(layout.meta_path)


def _run_registry_backfill(
    manager: BigQueryJobManager,
    meta: Meta,
    layout: DataLayout,
    registry: Registry,
    start: str,
    end: str,
    window_start: str,
    window_end: str,
) -> None:
    out_path = layout.events_path(registry.name)
    record = meta.backfill_job(registry.name)
    persist = lambda: _persist(meta, layout)

    if record.phase == "complete" and out_path.is_file() and out_path.stat().st_size > 0:
        print(f"Skip {registry.name}: backfill complete ({out_path})")
        return

    record.registry = registry.name
    record.output_path = str(out_path)
    record.window_start = window_start
    record.window_end = window_end

    job = manager.recover_or_raise(record, persist)

    if job is None:
        query = events_query(registry, start, end)
        dry = manager.dry_run_bytes(query)
        record.dry_run_bytes = dry
        explain_query(f"Backfill {registry.name}", window_start, window_end, dry)
        job = manager.submit(query, record, uncapped=True, persist=persist)

    if record.phase in ("submitted", "running"):
        job = manager.wait_until_done(record, persist)

    last_row = None
    if record.phase == "downloading":
        rows_written, last_row = manager.download_results(job, out_path, record, persist)
        billed = record.bytes_billed or 0
        print(
            f"  {registry.name}: {rows_written:,} events, {billed:,} bytes billed "
            f"-> {out_path}"
        )
        meta.mark_registry_fetch_from_last(registry.name, registry.address, rows_written, billed, last_row)


def backfill_ethereum(settings: Settings | None = None) -> None:
    settings = settings or Settings.load()
    layout = DataLayout(settings.data_dir)
    layout.ensure()

    meta = Meta.load(layout.meta_path, "ethereum", settings.launch_date)
    end_date = settings.sync_through_date()
    window_start, window_end = range_bounds(settings.launch_date, end_date)

    if meta.backfill_complete and all(
        meta.backfill_job(r.name).phase == "complete" for r in REGISTRIES
    ):
        print(f"Backfill already complete ({meta.backfill_completed_at})")
        return

    print(f"Backfill ethereum: {settings.launch_date} .. {end_date}")
    print(f"Data dir: {layout.network_dir}")
    print("Mode: two uncapped queries with job-id recovery")

    manager = BigQueryJobManager(max_bytes_billed=None)

    for registry in REGISTRIES:
        _run_registry_backfill(
            manager,
            meta,
            layout,
            registry,
            window_start,
            window_end,
            settings.launch_date.isoformat(),
            end_date.isoformat(),
        )
        meta.save(layout.meta_path)

    if all(meta.backfill_job(r.name).phase == "complete" for r in REGISTRIES):
        meta.mark_backfill_complete()
        meta.save(layout.meta_path)

    print()
    print("Backfill status:")
    for registry in REGISTRIES:
        job = meta.backfill_job(registry.name)
        state = meta.registries.get(registry.name)
        events = state.total_events if state else 0
        billed = state.total_bytes_billed if state else 0
        print(
            f"  {registry.name}: phase={job.phase} events={events:,} "
            f"billed={billed:,} job_id={job.job_id or '—'}"
        )
    print(f"Meta: {layout.meta_path}")
