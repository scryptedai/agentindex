"""Daily / on-demand incremental sync."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from agentindex.bq.client import BigQueryRunner
from agentindex.config import Settings
from agentindex.erc8004 import REGISTRIES
from agentindex.ingest.fetch import run_chunked_ingest
from agentindex.storage.meta import Meta
from agentindex.storage.paths import DataLayout


def _parse_ts(raw: str) -> datetime:
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    return datetime.fromisoformat(raw)


def _first_unsynced_day(meta: Meta, launch: date) -> date:
    if meta.backfill_complete:
        last_dates: list[date] = []
        for state in meta.registries.values():
            if state.last_block_timestamp:
                last_dates.append(_parse_ts(state.last_block_timestamp).date())
        if last_dates:
            return max(last_dates) + timedelta(days=1)

    completed: set[str] = set()
    for state in meta.registries.values():
        completed.update(state.chunks_completed)

    if not completed:
        return launch

    return max(date.fromisoformat(d) for d in completed) + timedelta(days=1)


def sync_ethereum(settings: Settings | None = None) -> None:
    settings = settings or Settings.load()
    layout = DataLayout(settings.data_dir)
    layout.ensure()

    meta = Meta.load(layout.meta_path, "ethereum", settings.launch_date)
    end = settings.sync_through_date()
    start = _first_unsynced_day(meta, settings.launch_date)

    if start > end:
        print(f"Already up to date through {end} (next would start {start})")
        return

    print(f"Sync ethereum: {start} .. {end}")
    print(f"Data dir: {layout.network_dir}")

    runner = BigQueryRunner(settings.max_bytes_billed)
    total_rows, total_bytes = run_chunked_ingest(
        runner,
        layout,
        meta,
        REGISTRIES,
        start,
        end,
        skip_existing=True,
    )

    meta.save(layout.meta_path)

    print(
        f"Sync complete: {total_rows:,} new events, "
        f"{total_bytes:,} bytes billed (~{total_bytes / 1e9:.2f} GB)"
    )
