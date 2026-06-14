"""Chart annotations and graph payloads derived from corpus data."""

from __future__ import annotations

from datetime import date
from typing import Any

CHAIN_LABELS: dict[int, str] = {
    1: "Ethereum",
    8453: "Base",
    56: "BNB Chain",
    137: "Polygon",
    10: "Optimism",
    42161: "Arbitrum",
}

CHAIN_COLORS: dict[int, str] = {
    1: "#5F6368",
    8453: "#1A73E8",
    56: "#F9AB00",
    137: "#8247E5",
    10: "#137333",
    42161: "#6E5BD0",
}

COLOR_RED = "#C5221F"
COLOR_AMBER = "#B06000"


def chart_day_label(day: str) -> str:
    """Match frontend charts.jsx dlabel (en-US short month + day)."""
    d = date.fromisoformat(str(day)[:10])
    return f"{d.strftime('%b')} {d.day}"


def build_chart_marks(raw: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Reactive chart annotation sets keyed by overview hero mode."""
    marks: dict[str, list[dict[str, Any]]] = {
        "pulse": [],
        "log": [],
        "score": [],
        "cumulative": [],
    }
    reg_days = raw.get("daily_registrations") or []
    fb_days = raw.get("daily_feedback") or []

    spikes = sorted(reg_days, key=lambda d: int(d["registrations"]), reverse=True)
    spikes = [d for d in spikes if int(d["registrations"]) >= 100][:3]
    if spikes:
        peak = int(spikes[0]["registrations"])
        for spike in spikes:
            n = int(spike["registrations"])
            label = chart_day_label(spike["day"])
            color = COLOR_RED if n == peak else COLOR_AMBER
            text = f"{n:,} mints"
            entry = {"label": label, "text": text, "color": color, "day": spike["day"]}
            marks["pulse"].append(entry)
            marks["log"].append(dict(entry))
        marks["cumulative"].append(
            {
                "label": chart_day_label(spikes[0]["day"]),
                "text": f"+{peak:,}",
                "color": COLOR_RED,
                "day": spikes[0]["day"],
            }
        )

    low_score_days = [
        row
        for row in fb_days
        if int(row.get("feedback") or 0) >= 50
        and row.get("avg_score") is not None
        and float(row["avg_score"]) <= 30
    ]
    if low_score_days:
        worst = min(low_score_days, key=lambda r: float(r["avg_score"]))
        avg = float(worst["avg_score"])
        label = chart_day_label(worst["day"])
        text = "low-score burst" if avg <= 5 else f"mean {avg:.2f}"
        burst = {"label": label, "text": text, "color": COLOR_RED, "day": worst["day"]}
        if not any(m["label"] == label for m in marks["pulse"]):
            marks["pulse"].insert(0, burst)
        marks["score"] = [burst]

    score_candidates = [
        row
        for row in fb_days
        if int(row.get("feedback") or 0) >= 20 and row.get("avg_score") is not None
    ]
    if score_candidates and not marks["score"]:
        worst = min(score_candidates, key=lambda r: float(r["avg_score"]))
        avg = float(worst["avg_score"])
        marks["score"] = [
            {
                "label": chart_day_label(worst["day"]),
                "text": f"mean {avg:.2f}",
                "color": COLOR_RED,
                "day": worst["day"],
            }
        ]

    return marks


def build_cross_chain_flow(
    raw: dict[str, Any],
    *,
    home_chain_id: int = 1,
) -> dict[str, Any]:
    rows = raw.get("cross_chain_by_chain") or []
    total = sum(int(r["refs"]) for r in rows)
    home_name = CHAIN_LABELS.get(home_chain_id, f"Chain {home_chain_id}")
    flows: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: int(r["refs"]), reverse=True):
        chain_id = int(row["chain_id"])
        refs = int(row["refs"])
        if chain_id == home_chain_id:
            label = f"{home_name} {chain_id} (self-ref)"
        else:
            label = f"{CHAIN_LABELS.get(chain_id, 'Chain')} {chain_id}"
        flows.append(
            {
                "chain": label,
                "n": refs,
                "color": CHAIN_COLORS.get(chain_id, "#80868B"),
            }
        )
    return {"total": total, "flows": flows, "home_chain_id": home_chain_id}


def build_config_snapshot(config: Any) -> str:
    network = config.network()
    lines = [
        f"network  = {network.key}",
        f"chain_id = {network.chain_id}",
    ]
    for registry in network.registries:
        lines.append(f"registry = {registry.address} ({registry.name})")
    if network.ens_enabled and network.ens:
        lines.append(f"ens_bq   = {network.ens.bq_dataset}")
    lines.append(f"lag_days = {network.lag_days}")
    return "\n".join(lines)
