"""BigQuery fetch and persist for one registry/day chunk."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from agentindex.bq.client import BigQueryRunner
from agentindex.bq.queries import events_query
from agentindex.erc8004 import Registry
from agentindex.storage.jsonl import write_rows
from agentindex.storage.meta import Meta
from agentindex.storage.paths import DataLayout


def day_bounds(day: date) -> tuple[str, str]:
    start = f"{day.isoformat()} 00:00:00"
    end = f"{day.isoformat()} 23:59:59"
    return start, end


def hour_bounds(day: date, hour: int) -> tuple[str, str]:
    start = datetime(day.year, day.month, day.day, hour, 0, 0)
    end = start + timedelta(hours=1) - timedelta(seconds=1)
    return start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")


def iter_days(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _fetch_window(
    runner: BigQueryRunner,
    registry: Registry,
    logs_table: str,
    window_start: str,
    window_end: str,
    label: str,
) -> tuple[list[dict[str, Any]], int]:
    query = events_query(registry, logs_table, window_start, window_end)
    return runner.query_rows(query, label)


def _fetch_day_hourly(
    runner: BigQueryRunner,
    registry: Registry,
    logs_table: str,
    day: date,
) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    total_billed = 0
    for hour in range(24):
        start, end = hour_bounds(day, hour)
        label = f"{registry.name}/{day.isoformat()}T{hour:02d}"
        chunk_rows, billed = _fetch_window(
            runner, registry, logs_table, start, end, label
        )
        rows.extend(chunk_rows)
        total_billed += billed
    rows.sort(key=lambda r: (r["block_number"], r["log_index"]))
    return rows, total_billed


def fetch_day(
    runner: BigQueryRunner,
    layout: DataLayout,
    meta: Meta,
    registry: Registry,
    logs_table: str,
    day: date,
    *,
    skip_existing: bool = True,
) -> tuple[int, int]:
    """Fetch one calendar day for a registry. Returns (rows_written, bytes_billed)."""
    if skip_existing and meta.chunk_done(registry.name, day):
        return 0, 0

    chunk_path = layout.chunk_path(registry.name, day)
    if skip_existing and chunk_path.is_file() and chunk_path.stat().st_size > 0:
        state = meta.registry(registry.name, registry.address)
        day_str = day.isoformat()
        if day_str not in state.chunks_completed:
            state.chunks_completed.append(day_str)
            state.chunks_completed.sort()
        return 0, 0

    start, end = day_bounds(day)
    label = f"{registry.name}/{day.isoformat()}"
    query = events_query(registry, logs_table, start, end)
    estimated = runner.dry_run_bytes(query)

    if runner.max_bytes_billed is not None and estimated <= runner.max_bytes_billed:
        rows, billed = runner.query_rows(query, label)
    else:
        print(
            f"  {label}: daily dry-run {estimated:,} bytes > cap; "
            f"splitting into hourly chunks"
        )
        rows, billed = _fetch_day_hourly(runner, registry, logs_table, day)

    write_rows(chunk_path, rows)
    meta.mark_chunk(registry.name, registry.address, day, rows, billed)
    return len(rows), billed


def run_chunked_ingest(
    runner: BigQueryRunner,
    layout: DataLayout,
    meta: Meta,
    registries: tuple,
    logs_table: str,
    start: date,
    end: date,
    *,
    skip_existing: bool = True,
) -> tuple[int, int]:
    """Ingest all registries day-by-day. Returns (total_rows, total_bytes)."""
    layout.ensure()
    total_rows = 0
    total_bytes = 0

    for day in iter_days(start, end):
        for registry in registries:
            rows, billed = fetch_day(
                runner,
                layout,
                meta,
                registry,
                logs_table,
                day,
                skip_existing=skip_existing,
            )
            total_rows += rows
            total_bytes += billed
            if rows or billed:
                print(
                    f"  {registry.name} {day}: {rows} events, {billed:,} bytes billed "
                    f"-> {layout.chunk_path(registry.name, day)}"
                )
        meta.save(layout.meta_path)

    return total_rows, total_bytes
