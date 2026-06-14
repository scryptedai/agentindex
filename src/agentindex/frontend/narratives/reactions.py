"""Evaluate declarative narrative reactions against computed metric contexts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from agentindex.frontend.narratives.engine import render

_OPS: dict[str, Any] = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
}


@lru_cache(maxsize=1)
def load_reactions() -> dict[str, Any]:
    path = Path(__file__).with_name("reactions.json")
    return json.loads(path.read_text(encoding="utf-8"))


def eval_when(when: dict[str, Any], ctx: dict[str, Any]) -> bool:
    if when.get("default"):
        return True
    if "all" in when:
        return all(eval_when(part, ctx) for part in when["all"])
    if "any" in when:
        return any(eval_when(part, ctx) for part in when["any"])
    if "not" in when:
        return not eval_when(when["not"], ctx)

    field = when["field"]
    op = when["op"]
    expected = when["value"]
    actual = ctx.get(field)
    if actual is None:
        return False
    try:
        return bool(_OPS[op](actual, expected))
    except (KeyError, TypeError):
        return False


def pick_first(reactions: list[dict[str, Any]], ctx: dict[str, Any]) -> dict[str, Any] | None:
    """Return the highest-priority matching reaction."""
    ordered = sorted(reactions, key=lambda r: r.get("priority", 0), reverse=True)
    for reaction in ordered:
        when = reaction.get("when")
        if when is None and reaction.get("default"):
            return reaction
        if when and eval_when(when, ctx):
            return reaction
    for reaction in ordered:
        if reaction.get("default"):
            return reaction
    return None


def pick_all(reactions: list[dict[str, Any]], ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every matching reaction, highest priority first."""
    ordered = sorted(reactions, key=lambda r: r.get("priority", 0), reverse=True)
    matched = [r for r in ordered if r.get("when") and eval_when(r["when"], ctx)]
    if matched:
        return matched
    defaults = [r for r in ordered if r.get("default")]
    return defaults[:1]


def react_text(reactions: list[dict[str, Any]], ctx: dict[str, Any]) -> tuple[str, str | None]:
    """Pick first reaction and render its text. Returns (text, reaction_id)."""
    reaction = pick_first(reactions, ctx)
    if not reaction:
        return "", None
    return render(reaction["text"], **ctx), reaction.get("id")


def react_bundle(
    reactions: list[dict[str, Any]],
    ctx: dict[str, Any],
    *,
    fields: tuple[str, ...] = ("text",),
) -> dict[str, Any] | None:
    """Pick first reaction and render selected string fields."""
    reaction = pick_first(reactions, ctx)
    if not reaction:
        return None
    out: dict[str, Any] = {"id": reaction.get("id")}
    for field in fields:
        if field in reaction:
            out[field] = render(reaction[field], **ctx)
    for passthrough in ("tone", "icon", "title", "label", "archetype"):
        if passthrough in reaction:
            out[passthrough] = reaction[passthrough]
    return out


def react_pair(block: dict[str, list[dict[str, Any]]], ctx: dict[str, Any]) -> dict[str, Any]:
    """Render title + desc reaction groups."""
    title, title_id = react_text(block["title"], ctx)
    desc, desc_id = react_text(block["desc"], ctx)
    return {
        "title": title,
        "desc": desc,
        "title_reaction": title_id,
        "desc_reaction": desc_id,
    }


def react_why(detail: str, ctx: dict[str, Any]) -> tuple[str, str | None]:
    """Render why-it-matters copy for a sybil signal detail category."""
    group = load_reactions()["sybil"]["why_matters"].get(detail, [])
    if not group:
        return "", None
    return react_text(group, ctx)
