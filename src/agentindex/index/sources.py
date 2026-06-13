"""Read deduplicated registry events from JSONL on disk."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def iter_registry_events(registry_dir: Path) -> Iterator[dict[str, Any]]:
    """Yield events from all JSONL files, deduped by (block_number, log_index)."""
    if not registry_dir.is_dir():
        return

    seen: set[tuple[int, int]] = set()
    rows: list[dict[str, Any]] = []

    for path in sorted(registry_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                key = (int(row["block_number"]), int(row["log_index"]))
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)

    rows.sort(key=lambda r: (int(r["block_number"]), int(r["log_index"])))
    yield from rows
