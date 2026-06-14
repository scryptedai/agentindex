"""Derive trust metrics, sybil signals, and narrative copy from corpus data."""

from __future__ import annotations

import base64
import json
import re
import statistics
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from agentindex.frontend.visuals import (
    build_chart_marks,
    build_config_snapshot,
    build_cross_chain_flow,
)
from agentindex.frontend.narratives.engine import load_templates, render
from agentindex.frontend.narratives.metrics import (
    agent_metrics,
    corpus_metrics,
    identity_metrics,
    overview_metrics,
    reviewer_independence_metrics,
    reviewer_page_metrics,
    reviewer_profile_metrics,
)
from agentindex.frontend.narratives.reactions import (
    load_reactions,
    pick_all,
    react_bundle,
    react_pair,
    react_text,
    react_why,
)

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


def _react_page_description(
    section: str,
    ctx: dict[str, Any],
    description_tpl: str,
) -> str:
    group = load_reactions().get(section, {}).get("page_description")
    if group:
        text, _ = react_text(group, ctx)
        if text:
            return text
    return render(description_tpl, **ctx)


def dossier_empty_states(
    agent: dict[str, Any],
    *,
    network_label: str,
) -> dict[str, str]:
    ctx = agent_metrics(agent, network_label=network_label)
    rx = load_reactions()["dossier"]["empty"]
    return {key: react_text(rx[key], ctx)[0] for key in rx}


def _attach_empty_states(
    agents: list[dict[str, Any]],
    *,
    network_label: str,
) -> None:
    for agent in agents:
        agent["empty"] = dossier_empty_states(agent, network_label=network_label)


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

    flag_meta = load_templates()["dossier"]["flags"]
    flag_rx = load_reactions()["dossier"]["flags"]
    flags: list[dict[str, Any]] = []

    def add_flag(key: str, ctx: dict[str, Any]) -> None:
        spec = flag_meta[key]
        tip, tip_id = react_text(flag_rx[key], ctx)
        flags.append(
            {
                "k": key,
                "label": spec["label"],
                "sev": spec["sev"],
                "tip": tip,
                "reaction": tip_id,
            }
        )

    flag_ctx = {
        "burst_count": burst_count,
        "burst_window_min": burst_window_min,
        "owner_count": owner_count or 0,
        "ens_name": ens_name or "",
        "unique_clients": unique_clients,
        "n": n,
        "composite": composite or 0,
    }

    if is_burst:
        add_flag("burst", flag_ctx)
    if is_factory:
        add_flag("factory", flag_ctx)
    if is_collision:
        add_flag("collision", flag_ctx)
    if single_reviewer:
        add_flag("single", flag_ctx)
    if cliff:
        add_flag("cliff", flag_ctx)
    if punitive_touch:
        add_flag("punitive", flag_ctx)
    if sparse and not cliff:
        add_flag("sparse", flag_ctx)
    if n == 0:
        add_flag("ghost", flag_ctx)

    if n == 0:
        level = "none"
    elif (
        is_factory
        or single_reviewer
        or (is_burst and burst_window_min < 60 and unique_clients < n * 0.6)
        or n < 5
    ):
        level = "low"
    elif (
        is_burst
        or cliff
        or sparse
        or punitive_touch
        or (independence is not None and independence < 0.85)
    ):
        level = "med"
    else:
        level = "high"

    reason_ctx = {
        "n": n,
        "has_feedback": n > 0,
        "is_factory": is_factory,
        "owner_count": owner_count or 0,
        "single_reviewer": single_reviewer,
        "is_burst": is_burst,
        "burst_count": burst_count,
        "burst_window_min": burst_window_min,
        "compressed_burst": is_burst
        and burst_window_min < 60
        and unique_clients < n * 0.6,
        "cliff": cliff,
        "punitive_touch": punitive_touch,
        "independence_pct": (independence or 0) * 100,
        "confidence_level": level,
        "unique_clients": unique_clients,
    }
    reason_reactions = load_reactions()["dossier"]["confidence_reasons"]
    reasons = [
        render(r["text"], **reason_ctx) for r in pick_all(reason_reactions, reason_ctx)
    ]

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
        "punitiveTouch": punitive_touch,
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
    rx = load_reactions()["dossier"]
    ctx = agent_metrics(agent, network_label=network_label)
    out: list[dict[str, Any]] = []

    primary = react_bundle(
        rx["primary_callout"],
        ctx,
        fields=("title", "text"),
    )
    if primary:
        out.append(
            {
                "tone": primary["tone"],
                "icon": primary["icon"],
                "html": f"<b>{primary['title']}</b> {primary['text']}",
                "reaction": primary.get("id"),
            }
        )

    ens = react_bundle(
        rx["ens_callout"],
        ctx,
        fields=("title", "text"),
    )
    if ens and (agent["isCollision"] or ctx["verified_count"] >= 1):
        out.append(
            {
                "tone": ens["tone"],
                "icon": ens["icon"],
                "html": f"<b>{ens['title']}</b> {ens['text']}",
                "reaction": ens.get("id"),
            }
        )
    return out


def classify_reviewer(profile: dict[str, Any]) -> dict[str, Any]:
    ctx = reviewer_profile_metrics(profile)
    bundle = react_bundle(
        load_reactions()["reviewer"]["archetype"],
        ctx,
        fields=("label", "text"),
    )
    if not bundle:
        return {"label": "Standard reviewer", "tone": "grey", "note": "", "archetype": "neutral"}
    return {
        "label": bundle["label"],
        "tone": bundle["tone"],
        "note": bundle["text"],
        "archetype": bundle.get("id", "neutral"),
    }


def build_reviewer_stories(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    stories: dict[str, dict[str, Any]] = {}
    for profile in raw["reviewer_profiles"][:15]:
        client = profile["client"].lower()
        story = classify_reviewer(profile)
        stories[client] = story
    return stories


def _signal_copy(signal_type: str, ctx: dict[str, Any], detail: str) -> dict[str, Any]:
    rx = load_reactions()["sybil"]["signals"][signal_type]
    copy = react_pair(rx, ctx)
    why, why_id = react_why(detail, ctx)
    copy["why"] = why
    copy["why_reaction"] = why_id
    return copy


def build_signals(raw: dict[str, Any], agents: list[dict[str, Any]], indexes: dict[str, Any]) -> list[dict[str, Any]]:
    tpl = load_templates()["sybil"]["signal_types"]
    cs = raw["corpus_stats"]
    signals: list[dict[str, Any]] = []

    for rank, owner in enumerate(raw["owner_concentration"][:3], start=1):
        if owner["agent_count"] < 50:
            continue
        share = 100 * owner["agent_count"] / cs["agents"]
        key = "factory_owner" if rank == 1 else "factory_owner_secondary"
        spec = tpl[key]
        ctx = {
            "owner_share": share,
            "agent_count": owner["agent_count"],
            "total_agents": cs["agents"],
            "with_feedback": owner["with_feedback"],
            "rank": rank,
            "feedback_ratio": owner["with_feedback"] / max(owner["agent_count"], 1),
            "feedback_ratio_pct": 100 * owner["with_feedback"] / max(owner["agent_count"], 1),
        }
        copy = _signal_copy(key, ctx, spec["detail"])
        signals.append(
            _signal(
                f"sig-factory-{rank}",
                spec,
                "high" if rank == 1 else "med",
                copy["title"],
                copy["desc"],
                {"kind": "owner", "id": owner["owner"]},
                [
                    {"k": "Agents minted", "v": f"{owner['agent_count']:,}"},
                    {"k": "With feedback", "v": str(owner["with_feedback"])},
                    {"k": "Share of registry", "v": f"{share:.1f}%"},
                ],
                why=copy["why"],
                why_reaction=copy.get("why_reaction"),
                title_reaction=copy.get("title_reaction"),
                desc_reaction=copy.get("desc_reaction"),
            )
        )

    for day_row in raw["daily_feedback"]:
        if day_row["feedback"] >= 100 and day_row["avg_score"] <= 5:
            spec = tpl["coordinated_downvote"]
            ctx = {
                "day": day_row["day"],
                "events": day_row["feedback"],
                "mean_score": day_row["avg_score"],
            }
            copy = _signal_copy("coordinated_downvote", ctx, spec["detail"])
            signals.append(
                _signal(
                    f"sig-downvote-{day_row['day']}",
                    spec,
                    "high",
                    copy["title"],
                    copy["desc"],
                    {"kind": "day", "id": day_row["day"]},
                    [
                        {"k": "Feedback events", "v": f"{day_row['feedback']:,}"},
                        {"k": "Mean score", "v": f"{day_row['avg_score']:.2f}"},
                    ],
                    why=copy["why"],
                    why_reaction=copy.get("why_reaction"),
                    title_reaction=copy.get("title_reaction"),
                    desc_reaction=copy.get("desc_reaction"),
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
            ctx = {
                "agents_hit": agents_hit,
                "reviews": reviews,
                "avg_score": avg,
                "span_label": span_label,
            }
            copy = _signal_copy("punitive_cluster", ctx, spec["detail"])
            signals.append(
                _signal(
                    f"sig-punitive-{client[:10]}",
                    spec,
                    "high",
                    copy["title"],
                    copy["desc"],
                    {"kind": "client", "id": profile["client"]},
                    [
                        {"k": "Reviews", "v": f"{reviews:,}"},
                        {"k": "Agents hit", "v": str(agents_hit)},
                        {"k": "Avg given", "v": f"{avg:.2f}"},
                    ],
                    ref_client=profile["client"],
                    why=copy["why"],
                    why_reaction=copy.get("why_reaction"),
                    title_reaction=copy.get("title_reaction"),
                    desc_reaction=copy.get("desc_reaction"),
                )
            )
        elif reviews >= 500:
            spec = tpl["reviewer_spray"]
            ctx = {
                "reviews": reviews,
                "agents": agents_hit,
                "span_days": span,
                "reviews_per_day": reviews / max(span, 1),
                "avg_score": avg,
            }
            copy = _signal_copy("reviewer_spray", ctx, spec["detail"])
            signals.append(
                _signal(
                    f"sig-spray-{client[:10]}",
                    spec,
                    "med",
                    copy["title"],
                    copy["desc"],
                    {"kind": "client", "id": profile["client"]},
                    [
                        {"k": "Reviews", "v": f"{reviews:,}"},
                        {"k": "Agents", "v": f"{agents_hit:,}"},
                        {"k": "Avg given", "v": f"{avg:.2f}"},
                    ],
                    ref_client=profile["client"],
                    why=copy["why"],
                    why_reaction=copy.get("why_reaction"),
                    title_reaction=copy.get("title_reaction"),
                    desc_reaction=copy.get("desc_reaction"),
                )
            )
        elif reviews >= 100 and avg <= 45:
            spec = tpl["harsh_critic"]
            ctx = {
                "agents": agents_hit,
                "reviews": reviews,
                "avg_score": avg,
                "span_label": span_label,
            }
            copy = _signal_copy("harsh_critic", ctx, spec["detail"])
            signals.append(
                _signal(
                    f"sig-harsh-{client[:10]}",
                    spec,
                    "med",
                    copy["title"],
                    copy["desc"],
                    {"kind": "client", "id": profile["client"]},
                    [
                        {"k": "Reviews", "v": f"{reviews:,}"},
                        {"k": "Agents", "v": str(agents_hit)},
                        {"k": "Avg given", "v": f"{avg:.2f}"},
                    ],
                    ref_client=profile["client"],
                    why=copy["why"],
                    why_reaction=copy.get("why_reaction"),
                    title_reaction=copy.get("title_reaction"),
                    desc_reaction=copy.get("desc_reaction"),
                )
            )

    burst_agents = [a for a in agents if a["isBurst"] and a["n"] >= 20]
    burst_agents.sort(key=lambda a: (-a["burstCount"], -a["n"]))
    for agent in burst_agents[:8]:
        spec = tpl["launch_burst"]
        ctx = {
            "agent_id": agent["id"],
            "burst_count": agent["burstCount"],
            "burst_window_min": agent["burstWindowMin"],
            "n": agent["n"],
            "composite": agent["composite"] or 0,
        }
        copy = _signal_copy("launch_burst", ctx, spec["detail"])
        signals.append(
            _signal(
                f"sig-burst-{agent['id']}",
                spec,
                "high",
                copy["title"],
                copy["desc"],
                {"kind": "agent", "id": agent["id"]},
                [
                    {"k": "Reviews", "v": f"{agent['n']:,}"},
                    {"k": "Window", "v": f"{agent['burstWindowMin']} min"},
                    {"k": "Composite", "v": f"{(agent['composite'] or 0):.1f}"},
                ],
                ref_agent=agent["id"],
                why=copy["why"],
                why_reaction=copy.get("why_reaction"),
                title_reaction=copy.get("title_reaction"),
                desc_reaction=copy.get("desc_reaction"),
            )
        )

    cliff_agents = [a for a in agents if a["cliff"]]
    cliff_agents.sort(key=lambda a: (-(a["composite"] or 0), -a["n"]))
    for agent in cliff_agents[:8]:
        spec = tpl["score_cliff"]
        ctx = {
            "agent_id": agent["id"],
            "composite": agent["composite"] or 0,
            "n": agent["n"],
        }
        copy = _signal_copy("score_cliff", ctx, spec["detail"])
        signals.append(
            _signal(
                f"sig-cliff-{agent['id']}",
                spec,
                "med",
                copy["title"],
                copy["desc"],
                {"kind": "agent", "id": agent["id"]},
                [
                    {"k": "Composite", "v": f"{(agent['composite'] or 0):.1f}"},
                    {"k": "Reviews", "v": str(agent["n"])},
                ],
                ref_agent=agent["id"],
                why=copy["why"],
                why_reaction=copy.get("why_reaction"),
                title_reaction=copy.get("title_reaction"),
                desc_reaction=copy.get("desc_reaction"),
            )
        )

    for collision in raw["ens_name_collisions"]:
        ids = [int(x) for x in collision["agent_ids"].split(",")]
        verified = int(collision["verified_count"])
        count = len(ids)
        if verified >= 2:
            spec = tpl["ens_collision_verified"]
            ctx = {
                "ens_name": collision["ens_name"],
                "agent_count": count,
                "agent_ids": ", ".join(str(i) for i in ids),
                "verified_count": verified,
            }
            copy = _signal_copy("ens_collision_verified", ctx, spec["detail"])
            signals.append(
                _signal(
                    f"sig-ens-verified-{collision['ens_name']}",
                    spec,
                    "med",
                    copy["title"],
                    copy["desc"],
                    {"kind": "ens", "id": collision["ens_name"]},
                    [
                        {"k": "Agents", "v": str(count)},
                        {"k": "Both verified", "v": "Yes"},
                    ],
                    ref_ens=collision["ens_name"],
                    why=copy["why"],
                    why_reaction=copy.get("why_reaction"),
                    title_reaction=copy.get("title_reaction"),
                    desc_reaction=copy.get("desc_reaction"),
                )
            )
        elif count >= 3:
            spec = tpl["ens_collision_spray"]
            verified_label = (
                f"{verified} verified" if verified else "none verified"
            )
            ctx = {
                "ens_name": collision["ens_name"],
                "agent_count": count,
                "verified_label": verified_label,
                "verified_count": verified,
            }
            copy = _signal_copy("ens_collision_spray", ctx, spec["detail"])
            signals.append(
                _signal(
                    f"sig-ens-{collision['ens_name']}",
                    spec,
                    "high" if count >= 5 else "med",
                    copy["title"],
                    copy["desc"],
                    {"kind": "ens", "id": collision["ens_name"]},
                    [
                        {"k": "Agents", "v": str(count)},
                        {"k": "Verified", "v": str(verified)},
                    ],
                    ref_ens=collision["ens_name"],
                    why=copy["why"],
                    why_reaction=copy.get("why_reaction"),
                    title_reaction=copy.get("title_reaction"),
                    desc_reaction=copy.get("desc_reaction"),
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
            ctx = {"registrations": reg, "day": day_row["day"], "share": share}
            copy = _signal_copy("mint_spike", ctx, spec["detail"])
            signals.append(
                _signal(
                    f"sig-mint-{day_row['day']}",
                    spec,
                    "med",
                    copy["title"],
                    copy["desc"],
                    {"kind": "day", "id": day_row["day"]},
                    [
                        {"k": "Registrations", "v": f"{reg:,}"},
                        {"k": "Share of registry", "v": f"{share:.1f}%"},
                    ],
                    why=copy["why"],
                    why_reaction=copy.get("why_reaction"),
                    title_reaction=copy.get("title_reaction"),
                    desc_reaction=copy.get("desc_reaction"),
                )
            )

    for owner in raw["owner_concentration"]:
        if owner["agent_count"] >= 100 and owner["with_feedback"] == 0:
            spec = tpl["ghost_fleet"]
            ctx = {"agent_count": owner["agent_count"]}
            copy = _signal_copy("ghost_fleet", ctx, spec["detail"])
            signals.append(
                _signal(
                    f"sig-ghost-{owner['owner'][:10]}",
                    spec,
                    "med",
                    copy["title"],
                    copy["desc"],
                    {"kind": "owner", "id": owner["owner"]},
                    [
                        {"k": "Agents minted", "v": f"{owner['agent_count']:,}"},
                        {"k": "With feedback", "v": "0"},
                    ],
                    why=copy["why"],
                    why_reaction=copy.get("why_reaction"),
                    title_reaction=copy.get("title_reaction"),
                    desc_reaction=copy.get("desc_reaction"),
                )
            )

    for row in raw.get("integrity_outliers") or []:
        spec = tpl["data_integrity"]
        ctx = {"agent_id": row["agent_id"], "score": row["score"]}
        copy = _signal_copy("data_integrity", ctx, spec["detail"])
        signals.append(
            _signal(
                f"sig-integrity-{row['agent_id']}",
                spec,
                "low",
                copy["title"],
                copy["desc"],
                {"kind": "agent", "id": row["agent_id"]},
                [
                    {"k": "Recorded score", "v": str(row["score"])},
                    {"k": "Scale ceiling", "v": "100"},
                ],
                ref_agent=row["agent_id"],
                why=copy["why"],
                why_reaction=copy.get("why_reaction"),
                title_reaction=copy.get("title_reaction"),
                desc_reaction=copy.get("desc_reaction"),
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
    why: str = "",
    why_reaction: str | None = None,
    title_reaction: str | None = None,
    desc_reaction: str | None = None,
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
        "why": why,
        "metrics": metrics,
        "rule": spec["rule"],
        "detail": spec["detail"],
    }
    if why_reaction:
        out["whyReaction"] = why_reaction
    if title_reaction:
        out["titleReaction"] = title_reaction
    if desc_reaction:
        out["descReaction"] = desc_reaction
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
    tpl = load_templates()["overview"]
    rx = load_reactions()["overview"]
    ctx = overview_metrics(raw, len(signals))
    ctx.update(net_ctx or {})

    hero: dict[str, dict[str, str]] = {}
    for mode in ("pulse", "score", "log", "cumulative"):
        block = tpl["hero"][mode]
        insight, insight_id = react_text(rx["hero"][mode], ctx)
        hero[mode] = {
            "title": block["title"],
            "subtitle": render(block.get("subtitle", ""), **ctx),
            "insight": insight,
            "reaction": insight_id,
        }

    shape_label, _ = react_text(rx["score_distribution"]["shape_label"], ctx)
    callout_bundle = react_bundle(rx["score_distribution"]["callout"], ctx, fields=("text",))
    teaser_title, teaser_title_id = react_text(rx["sybil_teaser"]["title"], ctx)
    teaser_sub, teaser_sub_id = react_text(rx["sybil_teaser"]["subtitle"], ctx)
    teaser_cta, _ = react_text(rx["sybil_teaser"]["cta"], ctx)
    cov_rx = rx["reputation_coverage"]
    cov_sub, _ = react_text(cov_rx["subtitle"], ctx)
    cov_insight, _ = react_text(cov_rx["insight"], ctx)

    kpi_rx = rx["kpi"]
    silent_note, _ = react_text(kpi_rx["silent_majority"], ctx)
    reviewer_note, _ = react_text(kpi_rx["reviewer_economy"], ctx)
    factory_note, _ = react_text(kpi_rx["factory_watch"], ctx)
    ens_note, _ = react_text(kpi_rx["ens_verified"], ctx)

    page_ctx = {**ctx, **(net_ctx or {})}
    return {
        "page": {
            "title": tpl["page"]["title"],
            "description": _react_page_description(
                "overview",
                page_ctx,
                tpl["page"]["description"],
            ),
        },
        "hero": hero,
        "kpi": {
            "silent_majority": {
                "label": tpl["kpi"]["silent_majority"]["label"],
                "value": f"{ctx['silent_pct']:.0f}",
                "unit": "%",
                "note": silent_note,
            },
            "reviewer_economy": {
                "label": tpl["kpi"]["reviewer_economy"]["label"],
                "value": f"{ctx['unique_clients']:,}",
                "note": reviewer_note,
            },
            "factory_watch": {
                "label": tpl["kpi"]["factory_watch"]["label"],
                "value": f"{ctx['top_owner_count']:,}" if ctx["factory_exists"] else "-",
                "note": factory_note,
            },
            "ens_verified": {
                "label": tpl["kpi"]["ens_verified"]["label"],
                "value": str(ctx["ens_verified"]),
                "unit": f"/ {ctx['ens_links']}",
                "note": ens_note,
            },
        },
        "reputation_coverage": {
            "subtitle": cov_sub,
            "insight": cov_insight,
        },
        "chart_marks": build_chart_marks(raw),
        "score_distribution": {
            "title": tpl["score_distribution"]["title"],
            "subtitle": render(
                tpl["score_distribution"]["subtitle_template"],
                feedback_events=ctx["feedback_events"],
                shape_label=shape_label,
            ),
            "callout": callout_bundle["text"] if callout_bundle else "",
            "callout_tone": callout_bundle.get("tone", "blue") if callout_bundle else "blue",
            "callout_icon": callout_bundle.get("icon", "info") if callout_bundle else "info",
            "reaction": callout_bundle.get("id") if callout_bundle else None,
        },
        "sybil_teaser": {
            "title": teaser_title,
            "subtitle": teaser_sub,
            "cta": teaser_cta,
            "reaction": teaser_title_id or teaser_sub_id,
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
    ctx = identity_metrics(raw)
    ctx.update(net_ctx or {})
    callouts: list[dict[str, Any]] = []

    collision = react_bundle(
        load_reactions()["identity"]["collision_callout"],
        ctx,
        fields=("text",),
    )
    if collision:
        callouts.append(
            {
                "tone": collision["tone"],
                "icon": collision["icon"],
                "html": f"<b>{collision['text']}</b>",
                "reaction": collision.get("id"),
            }
        )

    cross_chain, _ = react_text(load_reactions()["identity"]["cross_chain"], ctx)
    subtitle_bundle = react_bundle(
        load_reactions()["identity"]["cross_chain_subtitle"],
        ctx,
        fields=("text",),
    )

    proven = raw.get("ens_proven_links") or []
    unproven = raw.get("ens_unproven_claims") or []

    return {
        "page": {
            "title": tpl["page"]["title"],
            "description": _react_page_description(
                "identity",
                ctx,
                tpl["page"]["description"],
            ),
        },
        "callouts": callouts,
        "proven_links": proven,
        "unproven_claims": unproven,
        "proven_count": len(proven),
        "unproven_count": len(unproven),
        "cross_chain_callout": cross_chain,
        "cross_chain_subtitle": subtitle_bundle["text"] if subtitle_bundle else "",
        "cross_chain_flow": build_cross_chain_flow(
            raw,
            home_chain_id=ctx.get("home_chain_id", net_ctx.get("chain_id", 1) if net_ctx else 1),
        ),
    }


def _format_bytes_kpi(bytes_billed: int) -> tuple[str, str]:
    if bytes_billed <= 0:
        return "-", ""
    gb = bytes_billed / 1e9
    if gb >= 0.05:
        return f"{gb:.1f}", "GB"
    return f"{bytes_billed / 1e6:.0f}", "MB"


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
    _attach_empty_states(agents, network_label=net_ctx["network_label"])
    _attach_empty_states(explorer_derived, network_label=net_ctx["network_label"])
    agent_by_id = {a["id"]: a for a in explorer_derived}
    signals = build_signals(raw, explorer_derived, indexes)
    reviewer_stories = build_reviewer_stories(raw)
    dossier_callout_map = {
        a["id"]: dossier_callouts(a, network_label=net_ctx["network_label"])
        for a in agents
    }

    independence_examples: list[dict[str, Any]] = []
    indep_rx = load_reactions()["reviewer"]["independence_callout"]
    for aid in sorted(
        [a["id"] for a in agents if a.get("independence") is not None],
        key=lambda i: agent_by_id[i]["n"],
        reverse=True,
    )[:3]:
        a = agent_by_id[aid]
        ctx = reviewer_independence_metrics(a)
        bundle = react_bundle(indep_rx, ctx, fields=("text",))
        if not bundle:
            continue
        independence_examples.append(
            {
                "agent_id": aid,
                "independence_pct": round(ctx["independence_pct"]),
                "callout": {
                    "tone": bundle["tone"],
                    "icon": bundle["icon"],
                    "html": bundle["text"],
                    "reaction": bundle.get("id"),
                },
            }
        )

    sybil_tpl = load_templates()["sybil"]
    sybil_rx = load_reactions()["sybil"]
    sev_ctx = {"signal_count": len(signals)}
    severity_notes = {
        sev: react_text(sybil_rx["severity_notes"][sev], sev_ctx)[0]
        for sev in ("high", "med", "low")
    }
    reviewer_tpl = load_templates()["reviewer"]
    reviewer_rx = load_reactions()["reviewer"]
    rev_page_ctx = {**net_ctx, **reviewer_page_metrics(raw, independence_examples)}
    indep_sub, _ = react_text(reviewer_rx["independence_subtitle"], rev_page_ctx)

    explorer_tpl = load_templates()["explorer"]
    explorer_block = render_block_safe(explorer_tpl, **net_ctx)
    explorer_block["page"] = {
        "title": explorer_tpl["page"]["title"],
        "description": _react_page_description(
            "explorer",
            net_ctx,
            explorer_tpl["page"]["description"],
        ),
    }
    explorer_block["empty_results"] = react_text(
        load_reactions()["explorer"]["empty_results"], net_ctx
    )[0]
    corpus_tpl = load_templates()["corpus"]
    corpus_block = render_block_safe(corpus_tpl, **net_ctx)
    corpus_ctx = corpus_metrics(raw)
    corpus_ctx.update(net_ctx)
    corpus_rx = load_reactions()["corpus"]
    corpus_block["page"] = {
        "title": corpus_tpl["page"]["title"],
        "description": _react_page_description(
            "corpus",
            corpus_ctx,
            corpus_tpl["page"]["description"],
        ),
    }
    honesty_bundle = react_bundle(corpus_rx["honesty_callout"], corpus_ctx, fields=("text",))
    bytes_note, _ = react_text(corpus_rx["bytes_billed_note"], corpus_ctx)
    bytes_value, bytes_unit = _format_bytes_kpi(corpus_ctx["bytes_billed"])
    honesty_tpl = corpus_tpl["honesty_callout"]
    corpus_block["honesty_callout"] = {
        "tone": (honesty_bundle or {}).get("tone", honesty_tpl["tone"]),
        "icon": (honesty_bundle or {}).get("icon", honesty_tpl["icon"]),
        "body": honesty_bundle["text"] if honesty_bundle else "",
        "reaction": (honesty_bundle or {}).get("id"),
    }
    corpus_block["kpi"] = {
        "bytes_billed": {
            "value": bytes_value,
            "unit": bytes_unit,
            "note": bytes_note,
        },
    }
    if config is not None:
        corpus_block["config_snapshot"] = build_config_snapshot(config)
    corpus_block["db_download"] = "/api/download/db"
    dossier_tpl = load_templates()["dossier"]
    dossier_rx = load_reactions()["dossier"]
    not_found, _ = react_text(dossier_rx["not_found"], net_ctx)
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
                "page": {
                    "title": dossier_tpl["page"]["title"],
                    "description": _react_page_description(
                        "dossier",
                        net_ctx,
                        dossier_tpl["page"]["description"],
                    ),
                },
                "not_found": not_found,
            },
            "overview": build_overview_narratives(raw, signals, net_ctx=net_ctx),
            "identity": build_identity_narratives(raw, net_ctx=net_ctx),
            "reviewer": {
                "page": {
                    "title": reviewer_tpl["page"]["title"],
                    "description": _react_page_description(
                        "reviewer",
                        rev_page_ctx,
                        reviewer_tpl["page"]["description"],
                    ),
                },
                "independence_subtitle": indep_sub,
                "independenceExamples": independence_examples,
            },
            "sybil": {
                "page": {
                    "title": sybil_tpl["page"]["title"],
                    "description": _react_page_description(
                        "sybil",
                        {**net_ctx, **sev_ctx},
                        sybil_tpl["page"]["description"],
                    ),
                },
                "severityNotes": severity_notes,
            },
            "explorer": explorer_block,
            "corpus": corpus_block,
        },
    }
