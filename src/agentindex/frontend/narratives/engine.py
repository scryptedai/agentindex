"""Load narrative templates and render with context."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def load_templates() -> dict[str, Any]:
    path = Path(__file__).with_name("templates.json")
    return json.loads(path.read_text(encoding="utf-8"))


def render(template: str, **ctx: Any) -> str:
    """Format a template string; missing keys become empty."""

    class SafeDict(dict):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    return template.format_map(SafeDict(**ctx))


def pick(path: str) -> Any:
    """Dot-path into templates, e.g. overview.kpi.silent_majority."""
    node: Any = load_templates()
    for part in path.split("."):
        node = node[part]
    return node


def render_block(path: str, **ctx: Any) -> dict[str, Any]:
    """Render all string values in a template block recursively."""
    block = pick(path)
    return _render_obj(block, ctx)


def _render_obj(obj: Any, ctx: dict[str, Any]) -> Any:
    if isinstance(obj, str):
        return render(obj, **ctx)
    if isinstance(obj, dict):
        return {k: _render_obj(v, ctx) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_render_obj(v, ctx) for v in obj]
    return obj
