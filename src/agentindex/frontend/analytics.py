"""Derive trust metrics, sybil signals, and narrative copy from corpus data."""

from __future__ import annotations

import base64
import json
import re
import statistics
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from agentindex.frontend.narratives.engine import load_templates, render

PUNITIVE_CLIENTS = {
    "0xab0b2d97b6ab1d0a16d8834a162098ce78da137b",
    "0x130e90223aa47b1a046cbb1f6f27ea98e139ee30",
}
CHAIN_LABELS = {
    1: "Ethereum",
    8453: "Base",
    56: "BNB Chain",
    137: "Polygon",
    10: "Optimism",
    42161: "Arbitrum",
}


def decode_name(token_uri: str | None) -> str | None:
    if not token_uri:
        return None
    if token_uri.startswith("data:application/json;base64,"):
        try:
            payload = token_uri.split(",", 1)[1]
            data = json.loads(base64.b64decode(payload))
            return data.get("name")
        except (json.JSONDecodeError, ValueError):
            pass
    try:
        host = urlparse(token_uri).hostname or ""
        return host.replace("www.", "") or None
    except ValueError:
        return None


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _span_days(first: str | None, last: str | None) -> int:
    a, b = _parse_ts(first), _parse_ts(last)
    if not a or not b:
        return 0
    return max(1, (b - a).days + 1)


def build_indexes(raw: dict[str, Any]) -> dict[str, Any]:
    owner_map = {o["owner"].lower(): o for o in raw["owner_concentration"]}
    reviewer_map = {r["client"].lower(): r for r in raw["reviewer_profiles"]}
    collision_agents: dict[int, str] = {}
    for c in raw["ens_name_collisions"]:
        for part in c["agent_ids"].split(","):
            collision_agents[int(part.strip())] = c["ens_name"]
    return {
        "owner_map": owner_map,
        "reviewer_map": reviewer_map,
        "collision_agents": collision_agents,
    }


def derive_agent(entry: dict[str, Any], indexes: dict[str, Any]) -> dict[str, Any]:
    agent = entry["agent"]
    agg = entry.get("reputation_agg")
    feedback = sorted(
        entry.get("feedback_events") or [],
        key=lambda e: e.get("block_timestamp") or "",
    )
    owner = agent["owner"].lower()
    owner_rec = indexes["owner_map"].get(owner)
    owner_count = owner_rec["agent_count"] if owner_rec else None
    n = int(agg["n_feedback"]) if agg else 0
    composite = float(agg["composite"]) if agg else None

    burst_count = 0
    burst_window_min = 0
    unique_clients = 0
    t0 = None
    if feedback:
        t0 = _parse_ts(feedback[0]["block_timestamp"])
        if t0:
            win_end = t0.timestamp() + 120 * 60
            in_win = [
                e
                for e in feedback
                if (_parse_ts(e["block_timestamp"]) or t0).timestamp() <= win_end
            ]
            burst_count = len(in_win)
            if in_win:
                t_last = _parse_ts(in_win[-1]["block_timestamp"]) or t0
                burst_window_min = max(0, round((t_last - t0).total_seconds() / 60))

    independence = None
    if feedback:
        clients = list({e["client"].lower() for e in feedback})
        reviewer_map = indexes["reviewer_map"]
        indep = sum(
            1
            for c in clients
            if c not in reviewer_map or reviewer_map[c]["unique_agents_reviewed"] <= 3
        )
        independence = indep / len(clients)
        unique_clients = len(clients)

    is_burst = burst_count >= 20 and burst_window_min <= 120
    is_factory = owner_count is not None and owner_count >= 50
    agent_id = int(agent["agent_id"])
    ens_name = indexes["collision_agents"].get(agent_id)
    is_collision = ens_name is not None
    low_indep = independence is not None and independence < 0.6
    single_reviewer = n > 0 and unique_clients / max(n, 1) < 0.5
    cliff = composite is not None and composite >= 99.5 and n <= 12
    sparse = 0 < n < 10
    punitive_touch = any(e["client"].lower() in PUNITIVE_CLIENTS for e in feedback)

    templates = load_templates()["dossier"]["flags"]
    flags: list[dict[str, Any]] = []

    def add_flag(key: str, ctx: dict[str, Any]) -> None:
        spec = templates[key]
        flags.append(
            {
                "k": key,
                "label": spec["label"],
                "sev": spec["sev"],
                "tip": render(spec["tip_template"], **ctx),
            }
        )

    if is_burst:
        add_flag(
            "burst",
            {"burst_count": burst_count, "burst_window_min": burst_window_min},
        )
    if is_factory:
        add_flag("factory", {"owner_count": owner_count})
    if is_collision:
        add_flag("collision", {"ens_name": ens_name})
    if single_reviewer:
        add_flag("single", {"unique_clients": unique_clients, "n": n})
    if cliff:
        add_flag("cliff", {"composite": composite, "n": n})
    if punitive_touch:
        add_flag("punitive", {})
    if sparse and not cliff:
        add_flag("sparse", {"n": n})
    if n == 0:
        add_flag("ghost", {})

    reasons: list[str] = []
    reason_tpl = load_templates()["dossier"]["confidence_reasons"]
    if n == 0:
        level = "none"
        reasons.append(reason_tpl["no_feedback"])
    elif (
        is_factory
        or single_reviewer
        or (is_burst and burst_window_min < 60 and unique_clients < n * 0.6)
        or n < 5
    ):
        level = "low"
        if is_factory:
            reasons.append(
                render(reason_tpl["factory_owner"], owner_count=owner_count)
            )
        if single_reviewer:
            reasons.append(reason_tpl["single_reviewer"])
        if n < 5:
            reasons.append(render(reason_tpl["small_sample"], n=n))
        if is_burst and burst_window_min < 60:
            reasons.append(reason_tpl["compressed_window"])
    elif (
        is_burst
        or cliff
        or sparse
        or punitive_touch
        or (independence is not None and independence < 0.85)
    ):
        level = "med"
        if is_burst:
            reasons.append(
                render(
                    reason_tpl["burst_timing"],
                    burst_count=burst_count,
                    burst_window_min=burst_window_min,
                )
            )
        if cliff:
            reasons.append(reason_tpl["perfect_thin"])
        if punitive_touch:
            reasons.append(reason_tpl["punitive_touch"])
        if not is_burst and not cliff:
            reasons.append(reason_tpl["moderate_independence"])
    else:
        level = "high"
        reasons.append(
            render(
                reason_tpl["strong_sample"],
                n=n,
                unique_clients=unique_clients,
            )
        )
    if independence is not None:
        reasons.append(
            render(
                reason_tpl["independence_pct"],
                independence_pct=independence * 100,
            )
        )

    span_days = 0
    if feedback:
        span_days = _span_days(
            feedback[0]["block_timestamp"], feedback[-1]["block_timestamp"]
        )

    return {
        "id": agent_id,
        "agent": agent,
        "agg": agg,
        "ens": entry.get("ens_links") or [],
        "xreg": entry.get("cross_registrations") or [],
        "feedback": feedback,
        "owner": owner,
        "ownerCount": owner_count,
        "n": n,
        "composite": composite,
        "name": decode_name(agent.get("token_uri")),
        "burstCount": burst_count,
        "burstWindowMin": burst_window_min,
        "uniqueClients": unique_clients,
        "independence": independence,
        "t0": feedback[0]["block_timestamp"] if feedback else None,
        "isBurst": is_burst,
        "isFactory": is_factory,
        "isCollision": is_collision,
        "collisionEns": ens_name,
        "cliff": cliff,
        "sparse": sparse,
        "flags": flags,
        "confidence": {"level": level, "reasons": reasons},
        "hasFeedback": n > 0,
        "spanDays": span_days,
    }


def dossier_callouts(
    agent: dict[str, Any],
    *,
    network_label: str = "Ethereum Mainnet",
) -> list[dict[str, Any]]:
    tpl = load_templates()["dossier"]["callouts"]
    out: list[dict[str, Any]] = []
    ctx = {
        "n": agent["n"],
        "composite": agent["composite"] or 0,
        "burst_window_min": agent["burstWindowMin"],
        "unique_clients": agent["uniqueClients"],
        "owner_count": agent["ownerCount"] or 0,
        "verified_count": sum(1 for e in agent["ens"] if e.get("verified")),
        "ens_name": agent.get("collisionEns") or "",
    }

    if agent["isBurst"] and agent["n"] >= 20:
        block = tpl["launch_burst"]
        out.append(
            {
                "tone": block["tone"],
                "icon": block["icon"],
                "html": f"<b>{block['title']}</b> "
                + render(block["body_template"], **ctx),
            }
        )
    elif agent["cliff"]:
        block = tpl["score_cliff"]
        out.append(
            {
                "tone": block["tone"],
                "icon": block["icon"],
                "html": f"<b>{block['title']}</b> "
                + render(block["body_template"], **ctx),
            }
        )
    elif agent["isFactory"]:
        block = tpl["factory_owner"]
        out.append(
            {
                "tone": block["tone"],
                "icon": block["icon"],
                "html": f"<b>{block['title']}</b> "
                + render(block["body_template"], **ctx),
            }
        )
    elif not agent["hasFeedback"]:
        block = tpl["no_feedback"]
        out.append(
            {
                "tone": block["tone"],
                "icon": block["icon"],
                "html": f"<b>{block['title']}</b> "
                + render(block["body_template"], network_label=network_label),
            }
        )
    elif agent["confidence"]["level"] == "high":
        block = tpl["high_confidence"]
        out.append(
            {
                "tone": block["tone"],
                "icon": block["icon"],
                "html": f"<b>{block['title']}</b> "
                + render(block["body_template"], **ctx, span_days=agent["spanDays"]),
            }
        )

    verified = [e for e in agent["ens"] if e.get("verified")]
    if agent["isCollision"] and verified:
        block = tpl["ens_collision_verified"]
        out.append(
            {
                "tone": block["tone"],
                "icon": block["icon"],
                "html": f"<b>{block['title']}</b> "
                + render(block["body_template"], **ctx),
            }
        )
    elif verified:
        block = tpl["ens_verified"]
        out.append(
            {
                "tone": block["tone"],
                "icon": block["icon"],
                "html": f"<b>{block['title']}</b> "
                + render(block["body_template"], **ctx),
            }
        )
    return out


def classify_reviewer(profile: dict[str, Any]) -> dict[str, Any]:
    tpl = load_templates()["reviewer"]["archetypes"]
    reviews = int(profile["total_reviews"])
    agents = int(profile["unique_agents_reviewed"])
    avg = float(profile["avg_score_given"])
    span = _span_days(profile.get("first_review"), profile.get("last_review"))

    if reviews >= 500 and agents >= 500 and avg >= 75:
        key = "generous_sprayer"
    elif reviews >= 200 and avg <= 15:
        key = "punitive_cluster"
    elif reviews >= 100 and avg <= 45:
        key = "harsh_critic"
    elif reviews >= 50 and agents >= reviews * 0.95 and avg >= 80:
        key = "one_each_broad"
    elif reviews >= 30 and agents <= max(10, reviews // 4):
        key = "sequential_burst"
    elif reviews >= 100:
        key = "prolific_mixed"
    else:
        key = "neutral"

    spec = tpl[key]
    note = render(
        spec["note_template"],
        total_reviews=reviews,
        unique_agents=agents,
        avg_score=avg,
        span_days=span,
    )
    return {"label": spec["label"], "tone": spec["tone"], "note": note, "archetype": key}


def build_reviewer_stories(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    stories: dict[str, dict[str, Any]] = {}
    for profile in raw["reviewer_profiles"][:15]:
        client = profile["client"].lower()
        story = classify_reviewer(profile)
        stories[client] = story
    return stories


def build_signals(raw: dict[str, Any], agents: list[dict[str, Any]], indexes: dict[str, Any]) -> list[dict[str, Any]]:
    tpl = load_templates()["sybil"]["signal_types"]
    cs = raw["corpus_stats"]
    signals: list[dict[str, Any]] = []
    agent_by_id = {a["id"]: a for a in agents}

    for rank, owner in enumerate(raw["owner_concentration"][:3], start=1):
        if owner["agent_count"] < 50:
            continue
        share = 100 * owner["agent_count"] / cs["agents"]
        key = "factory_owner" if rank == 1 else "factory_owner_secondary"
        spec = tpl[key]
        title = render(
            spec["title_template"],
            owner_share=share,
            agent_count=owner["agent_count"],
        )
        desc = render(
            spec["desc_template"],
            agent_count=owner["agent_count"],
            total_agents=cs["agents"],
            with_feedback=owner["with_feedback"],
            rank=rank,
        )
        signals.append(
            _signal(
                f"sig-factory-{rank}",
                spec,
                "high" if rank == 1 else "med",
                title,
                desc,
                {"kind": "owner", "id": owner["owner"]},
                [
                    {"k": "Agents minted", "v": f"{owner['agent_count']:,}"},
                    {"k": "With feedback", "v": str(owner["with_feedback"])},
                    {"k": "Share of registry", "v": f"{share:.1f}%"},
                ],
            )
        )

    for day_row in raw["daily_feedback"]:
        if day_row["feedback"] >= 100 and day_row["avg_score"] <= 5:
            spec = tpl["coordinated_downvote"]
            signals.append(
                _signal(
                    f"sig-downvote-{day_row['day']}",
                    spec,
                    "high",
                    render(spec["title_template"], day=day_row["day"]),
                    render(
                        spec["desc_template"],
                        events=day_row["feedback"],
                        mean_score=day_row["avg_score"],
                    ),
                    {"kind": "day", "id": day_row["day"]},
                    [
                        {"k": "Feedback events", "v": f"{day_row['feedback']:,}"},
                        {"k": "Mean score", "v": f"{day_row['avg_score']:.2f}"},
                    ],
                )
            )

    for profile in raw["reviewer_profiles"]:
        client = profile["client"].lower()
        reviews = int(profile["total_reviews"])
        agents_hit = int(profile["unique_agents_reviewed"])
        avg = float(profile["avg_score_given"])
        span = _span_days(profile.get("first_review"), profile.get("last_review"))
        span_label = f"{span} days"

        if reviews >= 200 and avg <= 15 and agents_hit >= 50:
            spec = tpl["punitive_cluster"]
            signals.append(
                _signal(
                    f"sig-punitive-{client[:10]}",
                    spec,
                    "high",
                    render(spec["title_template"], agents_hit=agents_hit),
                    render(
                        spec["desc_template"],
                        reviews=reviews,
                        avg_score=avg,
                        span_label=span_label,
                    ),
                    {"kind": "client", "id": profile["client"]},
                    [
                        {"k": "Reviews", "v": f"{reviews:,}"},
                        {"k": "Agents hit", "v": str(agents_hit)},
                        {"k": "Avg given", "v": f"{avg:.2f}"},
                    ],
                    ref_client=profile["client"],
                )
            )
        elif reviews >= 500:
            spec = tpl["reviewer_spray"]
            signals.append(
                _signal(
                    f"sig-spray-{client[:10]}",
                    spec,
                    "med",
                    render(
                        spec["title_template"],
                        reviews=reviews,
                        agents=agents_hit,
                        span_days=span,
                    ),
                    render(
                        spec["desc_template"],
                        reviews_per_day=reviews / max(span, 1),
                        agents=agents_hit,
                        avg_score=avg,
                    ),
                    {"kind": "client", "id": profile["client"]},
                    [
                        {"k": "Reviews", "v": f"{reviews:,}"},
                        {"k": "Agents", "v": f"{agents_hit:,}"},
                        {"k": "Avg given", "v": f"{avg:.2f}"},
                    ],
                    ref_client=profile["client"],
                )
            )
        elif reviews >= 100 and avg <= 45:
            spec = tpl["harsh_critic"]
            signals.append(
                _signal(
                    f"sig-harsh-{client[:10]}",
                    spec,
                    "med",
                    render(spec["title_template"], agents=agents_hit),
                    render(
                        spec["desc_template"],
                        reviews=reviews,
                        avg_score=avg,
                        span_label=span_label,
                    ),
                    {"kind": "client", "id": profile["client"]},
                    [
                        {"k": "Reviews", "v": f"{reviews:,}"},
                        {"k": "Agents", "v": str(agents_hit)},
                        {"k": "Avg given", "v": f"{avg:.2f}"},
                    ],
                    ref_client=profile["client"],
                )
            )

    burst_agents = [a for a in agents if a["isBurst"] and a["n"] >= 20]
    burst_agents.sort(key=lambda a: (-a["burstCount"], -a["n"]))
    for agent in burst_agents[:8]:
        spec = tpl["launch_burst"]
        signals.append(
            _signal(
                f"sig-burst-{agent['id']}",
                spec,
                "high",
                render(
                    spec["title_template"],
                    agent_id=agent["id"],
                    burst_count=agent["burstCount"],
                    burst_window_min=agent["burstWindowMin"],
                ),
                render(
                    spec["desc_template"],
                    composite=agent["composite"] or 0,
                    n=agent["n"],
                ),
                {"kind": "agent", "id": agent["id"]},
                [
                    {"k": "Reviews", "v": f"{agent['n']:,}"},
                    {"k": "Window", "v": f"{agent['burstWindowMin']} min"},
                    {"k": "Composite", "v": f"{(agent['composite'] or 0):.1f}"},
                ],
                ref_agent=agent["id"],
            )
        )

    cliff_agents = [a for a in agents if a["cliff"]]
    cliff_agents.sort(key=lambda a: (-(a["composite"] or 0), -a["n"]))
    for agent in cliff_agents[:8]:
        spec = tpl["score_cliff"]
        signals.append(
            _signal(
                f"sig-cliff-{agent['id']}",
                spec,
                "med",
                render(
                    spec["title_template"],
                    agent_id=agent["id"],
                    composite=agent["composite"] or 0,
                    n=agent["n"],
                ),
                render(
                    spec["desc_template"],
                    composite=agent["composite"] or 0,
                    n=agent["n"],
                ),
                {"kind": "agent", "id": agent["id"]},
                [
                    {"k": "Composite", "v": f"{(agent['composite'] or 0):.1f}"},
                    {"k": "Reviews", "v": str(agent["n"])},
                ],
                ref_agent=agent["id"],
            )
        )

    for collision in raw["ens_name_collisions"]:
        ids = [int(x) for x in collision["agent_ids"].split(",")]
        verified = int(collision["verified_count"])
        count = len(ids)
        if verified >= 2:
            spec = tpl["ens_collision_verified"]
            signals.append(
                _signal(
                    f"sig-ens-verified-{collision['ens_name']}",
                    spec,
                    "med",
                    render(
                        spec["title_template"],
                        ens_name=collision["ens_name"],
                        agent_count=count,
                    ),
                    render(
                        spec["desc_template"],
                        ens_name=collision["ens_name"],
                        agent_ids=", ".join(str(i) for i in ids),
                    ),
                    {"kind": "ens", "id": collision["ens_name"]},
                    [
                        {"k": "Agents", "v": str(count)},
                        {"k": "Both verified", "v": "Yes"},
                    ],
                    ref_ens=collision["ens_name"],
                )
            )
        elif count >= 3:
            spec = tpl["ens_collision_spray"]
            verified_label = (
                f"{verified} verified" if verified else "none verified"
            )
            signals.append(
                _signal(
                    f"sig-ens-{collision['ens_name']}",
                    spec,
                    "high" if count >= 5 else "med",
                    render(
                        spec["title_template"],
                        ens_name=collision["ens_name"],
                        agent_count=count,
                    ),
                    render(
                        spec["desc_template"],
                        ens_name=collision["ens_name"],
                        agent_count=count,
                        verified_label=verified_label,
                    ),
                    {"kind": "ens", "id": collision["ens_name"]},
                    [
                        {"k": "Agents", "v": str(count)},
                        {"k": "Verified", "v": str(verified)},
                    ],
                    ref_ens=collision["ens_name"],
                )
            )

    medians = [
        d["registrations"]
        for d in raw["daily_registrations"]
        if d["registrations"] > 0
    ]
    median_reg = statistics.median(medians) if medians else 1
    for day_row in raw["daily_registrations"]:
        reg = int(day_row["registrations"])
        if reg >= max(500, median_reg * 10):
            spec = tpl["mint_spike"]
            share = 100 * reg / cs["agents"]
            signals.append(
                _signal(
                    f"sig-mint-{day_row['day']}",
                    spec,
                    "med",
                    render(
                        spec["title_template"],
                        registrations=reg,
                        day=day_row["day"],
                    ),
                    render(
                        spec["desc_template"],
                        share=share,
                    ),
                    {"kind": "day", "id": day_row["day"]},
                    [
                        {"k": "Registrations", "v": f"{reg:,}"},
                        {"k": "Share of registry", "v": f"{share:.1f}%"},
                    ],
                )
            )

    for owner in raw["owner_concentration"]:
        if owner["agent_count"] >= 100 and owner["with_feedback"] == 0:
            spec = tpl["ghost_fleet"]
            signals.append(
                _signal(
                    f"sig-ghost-{owner['owner'][:10]}",
                    spec,
                    "med",
                    render(
                        spec["title_template"],
                        agent_count=owner["agent_count"],
                    ),
                    render(
                        spec["desc_template"],
                        agent_count=owner["agent_count"],
                    ),
                    {"kind": "owner", "id": owner["owner"]},
                    [
                        {"k": "Agents minted", "v": f"{owner['agent_count']:,}"},
                        {"k": "With feedback", "v": "0"},
                    ],
                )
            )

    for row in raw.get("integrity_outliers") or []:
        spec = tpl["data_integrity"]
        signals.append(
            _signal(
                f"sig-integrity-{row['agent_id']}",
                spec,
                "low",
                render(spec["title_template"], agent_id=row["agent_id"]),
                render(spec["desc_template"], score=row["score"]),
                {"kind": "agent", "id": row["agent_id"]},
                [
                    {"k": "Recorded score", "v": str(row["score"])},
                    {"k": "Scale ceiling", "v": "100"},
                ],
                ref_agent=row["agent_id"],
            )
        )

    sev_order = {"high": 0, "med": 1, "low": 2}
    signals.sort(key=lambda s: (sev_order[s["sev"]], s["title"]))
    return signals


def _signal(
    sig_id: str,
    spec: dict[str, Any],
    sev: str,
    title: str,
    desc: str,
    entity: dict[str, Any],
    metrics: list[dict[str, str]],
    *,
    ref_agent: int | None = None,
    ref_client: str | None = None,
    ref_ens: str | None = None,
) -> dict[str, Any]:
    out = {
        "id": sig_id,
        "cls": spec["cls"],
        "sev": sev,
        "icon": spec["icon"],
        "title": title,
        "entity": entity,
        "desc": desc,
        "metrics": metrics,
        "rule": spec["rule"],
        "detail": spec["detail"],
    }
    if ref_agent is not None:
        out["refAgent"] = ref_agent
    if ref_client is not None:
        out["refClient"] = ref_client
    if ref_ens is not None:
        out["refEns"] = ref_ens
    return out


def build_overview_narratives(
    raw: dict[str, Any],
    signals: list[dict[str, Any]],
    *,
    net_ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cs = raw["corpus_stats"]
    tpl = load_templates()["overview"]
    silent = cs["agents"] - cs["agents_with_feedback"]
    silent_pct = 100 * silent / cs["agents"] if cs["agents"] else 0
    top_owner = raw["owner_concentration"][0] if raw["owner_concentration"] else None
    days = raw["daily_registrations"]
    date_range = f"{days[0]['day']} – {days[-1]['day']}" if days else "-"
    spike = max(days, key=lambda d: d["registrations"]) if days else None

    dist = {d["bucket"]: d["count"] for d in raw["score_distribution"]}
    total_fb = cs["feedback_events"] or 1
    high_pct = 100 * dist.get("80-100", 0) / total_fb
    low_count = dist.get("0-19", 0) + dist.get("20-39", 0)

    hero_ctx = {
        "date_range": date_range,
        "spike_day": spike["day"] if spike else "",
        "spike_registrations": spike["registrations"] if spike else 0,
        "spike_share": 100 * spike["registrations"] / cs["agents"] if spike else 0,
        "feedback_rate": 100 * cs["agents_with_feedback"] / cs["agents"],
    }

    hero: dict[str, dict[str, str]] = {}
    for mode in ("pulse", "score", "log", "cumulative"):
        block = tpl["hero"][mode]
        insight = block["insight_default"]
        if mode == "pulse" and spike and spike["registrations"] >= 500:
            insight = render(block["insight_spike_day"], **hero_ctx)
        elif mode == "score":
            worst = min(
                raw["daily_feedback"],
                key=lambda d: d.get("avg_score") or 100,
                default=None,
            )
            if worst and worst["feedback"] >= 50:
                insight = render(
                    block["insight_downvote_day"],
                    day=worst["day"],
                    events=worst["feedback"],
                    mean_score=worst["avg_score"],
                )
        hero[mode] = {
            "title": block["title"],
            "subtitle": render(block.get("subtitle", ""), date_range=date_range),
            "insight": insight,
        }

    score_callout = (
        render(
            tpl["score_distribution"]["callout_high_bucket"]["body_template"],
            high_bucket_pct=high_pct,
            low_bucket_count=low_count,
        )
        if high_pct >= 50
        else tpl["score_distribution"]["callout_balanced"]["body_template"]
    )

    return {
        "page": render_block_safe(
            tpl["page"],
            indexed_through=cs["generated_at"],
            **(net_ctx or {}),
        ),
        "hero": hero,
        "kpi": {
            "silent_majority": {
                "label": tpl["kpi"]["silent_majority"]["label"],
                "value": f"{silent_pct:.0f}",
                "unit": "%",
                "note": render(
                    tpl["kpi"]["silent_majority"]["note_template"],
                    silent_count=silent,
                    network_label=(net_ctx or {}).get("network_label", "Ethereum Mainnet"),
                ),
            },
            "reviewer_economy": {
                "label": tpl["kpi"]["reviewer_economy"]["label"],
                "value": f"{cs['unique_clients']:,}",
                "note": render(
                    tpl["kpi"]["reviewer_economy"]["note_template"],
                    feedback_events=cs["feedback_events"],
                    unique_clients=cs["unique_clients"],
                    network_label=(net_ctx or {}).get("network_label", "Ethereum Mainnet"),
                ),
            },
            "factory_watch": {
                "label": tpl["kpi"]["factory_watch"]["label"],
                "value": f"{top_owner['agent_count']:,}" if top_owner else "-",
                "note": (
                    render(
                        tpl["kpi"]["factory_watch"]["note_template"],
                        top_owner_share=100 * top_owner["agent_count"] / cs["agents"],
                    )
                    if top_owner and top_owner["agent_count"] >= 50
                    else tpl["kpi"]["factory_watch"]["note_none"]
                ),
            },
            "ens_verified": {
                "label": tpl["kpi"]["ens_verified"]["label"],
                "value": str(cs["ens_verified"]),
                "unit": f"/ {cs['ens_links']}",
                "note": render(
                    tpl["kpi"]["ens_verified"]["note_template"],
                    ens_verified=cs["ens_verified"],
                    ens_links=cs["ens_links"],
                ),
            },
        },
        "score_distribution": {
            "title": tpl["score_distribution"]["title"],
            "subtitle": render(
                tpl["score_distribution"]["subtitle_template"],
                feedback_events=cs["feedback_events"],
                shape_label="skewed toward high scores"
                if high_pct >= 50
                else "mixed",
            ),
            "callout": score_callout,
        },
        "sybil_teaser": {
            "title": render(
                tpl["sybil_teaser"]["title_template"],
                signal_count=len(signals),
            ),
            "subtitle": tpl["sybil_teaser"]["subtitle"],
        },
    }


def _needs_runtime_render(template: str, ctx: dict[str, Any]) -> bool:
    """Leave templates unrendered when they reference keys not in ctx."""
    import string

    for _, field_name, _, _ in string.Formatter().parse(template):
        if not field_name:
            continue
        key = field_name.split(":")[0]
        if key not in ctx:
            return True
    return False


def render_block_safe(block: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in block.items():
        if isinstance(value, dict):
            result[key] = render_block_safe(value, **ctx)
        elif isinstance(value, str):
            if _needs_runtime_render(value, ctx):
                result[key] = value
            else:
                result[key] = render(value, **ctx)
        else:
            result[key] = value
    return result


def build_explorer_index(agents: list[dict[str, Any]], raw: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "id": a["id"],
            "name": a["name"],
            "owner": a["agent"]["owner"],
            "composite": a["composite"],
            "n": a["n"],
            "conf": a["confidence"]["level"],
            "flags": len(a["flags"]),
            "seen": a["agent"].get("first_seen_at"),
            "ens": [e["ens_name"] for e in a["ens"]],
            "isFactory": a["isFactory"],
            "collisionOnly": False,
        }
        for a in agents
    ]
    seen = {r["id"] for r in rows}
    for collision in raw["ens_name_collisions"]:
        for part in collision["agent_ids"].split(","):
            aid = int(part.strip())
            if aid not in seen:
                seen.add(aid)
                rows.append(
                    {
                        "id": aid,
                        "name": None,
                        "owner": None,
                        "composite": None,
                        "n": 0,
                        "conf": "none",
                        "flags": 1,
                        "seen": None,
                        "ens": [collision["ens_name"]],
                        "isFactory": False,
                        "collisionOnly": True,
                    }
                )
    return rows


def build_identity_narratives(
    raw: dict[str, Any],
    *,
    net_ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tpl = load_templates()["identity"]
    callouts: list[dict[str, Any]] = []
    worst = max(
        raw["ens_name_collisions"],
        key=lambda c: len(c["agent_ids"].split(",")),
        default=None,
    )
    if worst:
        count = len(worst["agent_ids"].split(","))
        verified = int(worst["verified_count"])
        if verified >= 2:
            block = tpl["collision_callout"]["verified_collision"]
            callouts.append(
                {
                    "tone": block["tone"],
                    "icon": block["icon"],
                    "html": f"<b>{render(block['body_template'], ens_name=worst['ens_name'], agent_count=count)}</b>",
                }
            )
        elif count >= 3:
            block = tpl["collision_callout"]["namespace_spray"]
            callouts.append(
                {
                    "tone": block["tone"],
                    "icon": block["icon"],
                    "html": render(
                        block["body_template"],
                        ens_name=worst["ens_name"],
                        agent_count=count,
                        verified_count=verified,
                    ),
                }
            )
    cc = tpl["cross_chain_callout"]
    return {
        "page": render_block_safe(tpl["page"], **(net_ctx or {})),
        "callouts": callouts,
        "cross_chain_callout": cc["body_template"],
    }


def build_payload(
    raw: dict[str, Any],
    *,
    schema_version: int,
    db_path: str,
    config: Any | None = None,
) -> dict[str, Any]:
    from agentindex.frontend.networks import build_network_meta, network_label

    network_meta = build_network_meta(config) if config else None
    active = (network_meta or {}).get("active") or {
        "label": "Ethereum Mainnet",
        "chain_id": raw["corpus_stats"].get("chain_id", 1),
    }
    net_ctx = {
        "network_label": active["label"],
        "chain_id": active["chain_id"],
        "agent_count": raw["corpus_stats"]["agents"],
    }
    indexes = build_indexes(raw)
    spotlight_entries = raw["spotlight_agents"]
    explorer_entries = raw.get("explorer_agents") or spotlight_entries
    agents = [derive_agent(entry, indexes) for entry in spotlight_entries]
    explorer_derived = [derive_agent(entry, indexes) for entry in explorer_entries]
    agent_by_id = {a["id"]: a for a in explorer_derived}
    signals = build_signals(raw, explorer_derived, indexes)
    reviewer_stories = build_reviewer_stories(raw)
    dossier_callout_map = {
        a["id"]: dossier_callouts(a, network_label=net_ctx["network_label"])
        for a in agents
    }

    independence_examples: list[dict[str, Any]] = []
    for aid in sorted(
        [a["id"] for a in agents if a.get("independence") is not None],
        key=lambda i: agent_by_id[i]["n"],
        reverse=True,
    )[:3]:
        a = agent_by_id[aid]
        tpl = load_templates()["reviewer"]["independence_callout"]
        if a["isBurst"] and (a["independence"] or 0) >= 0.8:
            block = tpl["high_timing_low"]
        elif (a["independence"] or 0) < 0.6:
            block = tpl["low_independence"]
        else:
            continue
        independence_examples.append(
            {
                "agent_id": aid,
                "independence_pct": round((a["independence"] or 0) * 100),
                "callout": {
                    "tone": block["tone"],
                    "icon": block["icon"],
                    "html": render(
                        block["body_template"],
                        agent_id=aid,
                        independence_pct=(a["independence"] or 0) * 100,
                    ),
                },
            }
        )

    sybil_tpl = load_templates()["sybil"]
    return {
        "raw": raw,
        "meta": {
            "schema_version": schema_version,
            "db_path": db_path,
            "generated_at": raw["corpus_stats"]["generated_at"],
        },
        "derived": {
            "agents": agents,
            "agentById": agent_by_id,
            "signals": signals,
            "reviewerStories": reviewer_stories,
            "explorerIndex": build_explorer_index(explorer_derived, raw),
            "dossierCallouts": dossier_callout_map,
            "dossier": {
                "page": render_block_safe(
                    load_templates()["dossier"]["page"],
                    **net_ctx,
                ),
            },
            "overview": build_overview_narratives(raw, signals, net_ctx=net_ctx),
            "identity": build_identity_narratives(raw, net_ctx=net_ctx),
            "reviewer": {
                "page": render_block_safe(
                    load_templates()["reviewer"]["page"],
                    **net_ctx,
                ),
                "independenceExamples": independence_examples,
            },
            "sybil": {
                "page": render_block_safe(sybil_tpl["page"], **net_ctx),
                "whyMatters": sybil_tpl["why_matters"],
                "severityNotes": sybil_tpl["severity_notes"],
            },
            "explorer": render_block_safe(load_templates()["explorer"], **net_ctx),
            "corpus": render_block_safe(load_templates()["corpus"], **net_ctx),
        },
    }
