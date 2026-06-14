"""Compute metric contexts that drive narrative reactions."""

from __future__ import annotations

import statistics
from datetime import date, datetime
from typing import Any


def _parse_ts(iso: str | None) -> datetime | None:
    if not iso:
        return None
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _span_days(start: str | None, end: str | None) -> int:
    t0 = _parse_ts(start)
    t1 = _parse_ts(end)
    if not t0 or not t1:
        return 0
    return max(0, (t1 - t0).days)


def overview_metrics(raw: dict[str, Any], signal_count: int) -> dict[str, Any]:
    cs = raw["corpus_stats"]
    agents = cs["agents"] or 1
    silent = cs["agents"] - cs["agents_with_feedback"]
    silent_pct = 100 * silent / agents

    days = raw["daily_registrations"]
    date_range = f"{days[0]['day']} – {days[-1]['day']}" if days else "-"
    reg_values = [int(d["registrations"]) for d in days]
    median_reg = statistics.median(reg_values) if reg_values else 0
    spike = max(days, key=lambda d: d["registrations"]) if days else None
    spike_registrations = int(spike["registrations"]) if spike else 0
    spike_share = 100 * spike_registrations / agents if spike else 0
    spike_vs_median = spike_registrations / median_reg if median_reg else 0

    sorted_days = sorted(days, key=lambda d: d["registrations"], reverse=True)
    top3_registrations = sum(int(d["registrations"]) for d in sorted_days[:3])
    top3_share = 100 * top3_registrations / agents

    feedback_days = raw["daily_feedback"]
    worst = (
        min(feedback_days, key=lambda d: d.get("avg_score") or 100)
        if feedback_days
        else None
    )
    worst_events = int(worst["feedback"]) if worst else 0
    worst_mean_score = float(worst["avg_score"]) if worst and worst.get("avg_score") is not None else 100.0
    worst_day = worst["day"] if worst else ""

    high_volume_low_score = (
        worst is not None
        and worst_events >= 50
        and worst_mean_score <= 30
    )
    coordinated_downvote = (
        worst is not None
        and worst_events >= 100
        and worst_mean_score <= 5
    )

    dist = {d["bucket"]: d["count"] for d in raw["score_distribution"]}
    total_fb = cs["feedback_events"] or 1
    high_bucket_pct = 100 * dist.get("80-100", 0) / total_fb
    low_bucket_count = dist.get("0-19", 0) + dist.get("20-39", 0)

    top_owner = raw["owner_concentration"][0] if raw["owner_concentration"] else None
    top_owner_count = int(top_owner["agent_count"]) if top_owner else 0
    top_owner_share = 100 * top_owner_count / agents if top_owner else 0
    factory_exists = top_owner_count >= 50

    ens_links = cs["ens_links"] or 0
    ens_verified = cs["ens_verified"] or 0
    ens_verified_rate = 100 * ens_verified / ens_links if ens_links else 0

    feedback_rate = 100 * cs["agents_with_feedback"] / agents
    events_per_client = cs["feedback_events"] / max(cs["unique_clients"], 1)

    return {
        "date_range": date_range,
        "agent_count": agents,
        "silent_count": silent,
        "silent_pct": silent_pct,
        "feedback_rate": feedback_rate,
        "feedback_events": cs["feedback_events"],
        "unique_clients": cs["unique_clients"],
        "events_per_client": events_per_client,
        "spike_day": spike["day"] if spike else "",
        "spike_registrations": spike_registrations,
        "spike_share": spike_share,
        "spike_vs_median": spike_vs_median,
        "registration_days": len(days),
        "top3_share": top3_share,
        "worst_day": worst_day,
        "worst_events": worst_events,
        "worst_mean_score": worst_mean_score,
        "high_volume_low_score": high_volume_low_score,
        "coordinated_downvote": coordinated_downvote,
        "high_bucket_pct": high_bucket_pct,
        "low_bucket_count": low_bucket_count,
        "top_owner_count": top_owner_count,
        "top_owner_share": top_owner_share,
        "factory_exists": factory_exists,
        "ens_links": ens_links,
        "ens_verified": ens_verified,
        "ens_verified_rate": ens_verified_rate,
        "signal_count": signal_count,
        "indexed_through": cs["generated_at"],
        "agents_with_feedback": cs["agents_with_feedback"],
    }


def agent_metrics(agent: dict[str, Any], *, network_label: str) -> dict[str, Any]:
    verified_count = sum(1 for e in agent["ens"] if e.get("verified"))
    independence_pct = (agent["independence"] or 0) * 100
    n = agent["n"]
    unique_clients = agent["uniqueClients"]
    return {
        "network_label": network_label,
        "n": n,
        "composite": agent["composite"] or 0,
        "burst_count": agent["burstCount"],
        "burst_window_min": agent["burstWindowMin"],
        "unique_clients": unique_clients,
        "owner_count": agent["ownerCount"] or 0,
        "verified_count": verified_count,
        "ens_name": agent.get("collisionEns") or "",
        "span_days": agent["spanDays"],
        "independence_pct": independence_pct,
        "is_burst": agent["isBurst"],
        "is_factory": agent["isFactory"],
        "is_collision": agent["isCollision"],
        "cliff": agent["cliff"],
        "has_feedback": agent["hasFeedback"],
        "confidence_level": agent["confidence"]["level"],
        "sparse": agent["sparse"],
        "punitive_touch": agent.get("punitiveTouch", False),
        "single_reviewer": n > 0 and unique_clients / max(n, 1) < 0.5,
        "compressed_burst": agent["isBurst"]
        and agent["burstWindowMin"] < 60
        and unique_clients < n * 0.6,
    }


def _parse_date(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return date.fromisoformat(str(iso)[:10])
    except ValueError:
        return None


def _cross_share_fields(cross: dict[str, Any], cs: dict[str, Any]) -> dict[str, Any]:
    total = int(cross.get("total") or cs.get("cross_registrations") or 0)
    on_home = int(cross.get("on_home_chain") or 0)
    foreign = int(cross.get("foreign_chain") or 0)
    return {
        "cross_registrations": total,
        "cross_on_home_chain": on_home,
        "cross_foreign_chain": foreign,
        "foreign_chain_count": int(cross.get("foreign_chain_count") or 0),
        "home_chain_id": cross.get("home_chain_id", cs.get("chain_id", 1)),
        "home_share_pct": 100 * on_home / total if total else 0,
        "foreign_share_pct": 100 * foreign / total if total else 0,
    }


def corpus_metrics(raw: dict[str, Any], ingest_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    cs = raw["corpus_stats"]
    indexed = _parse_date(cs.get("generated_at"))
    days_since_indexed = (date.today() - indexed).days if indexed else 0
    ingest = ingest_meta or raw.get("ingest_meta") or {}
    bytes_billed = int(ingest.get("bytes_billed") or 0)
    cross = raw.get("cross_chain_stats") or {}
    return {
        "indexed_through": cs["generated_at"],
        "days_since_indexed": days_since_indexed,
        "bytes_billed": bytes_billed,
        "bytes_billed_gb": bytes_billed / 1e9 if bytes_billed else 0,
        **_cross_share_fields(cross, cs),
    }


def identity_metrics(raw: dict[str, Any]) -> dict[str, Any]:
    cs = raw["corpus_stats"]
    cross = raw.get("cross_chain_stats") or {}
    collisions = raw["ens_name_collisions"]
    worst = max(collisions, key=lambda c: len(c["agent_ids"].split(",")), default=None)
    base = {
        **_cross_share_fields(cross, cs),
        "collision_cluster_count": len(collisions),
        "collision_count": 0,
        "verified_count": 0,
        "worst_ens_name": "",
    }
    if not worst:
        return base
    count = len(worst["agent_ids"].split(","))
    verified = int(worst["verified_count"])
    return {
        **base,
        "collision_count": count,
        "verified_count": verified,
        "worst_ens_name": worst["ens_name"],
        "ens_name": worst["ens_name"],
        "agent_count": count,
    }


def reviewer_profile_metrics(profile: dict[str, Any]) -> dict[str, Any]:
    reviews = int(profile["total_reviews"])
    agents = int(profile["unique_agents_reviewed"])
    avg = float(profile["avg_score_given"])
    span = _span_days(profile.get("first_review"), profile.get("last_review"))
    return {
        "total_reviews": reviews,
        "unique_agents": agents,
        "avg_score": avg,
        "span_days": span,
        "agents_per_review": agents / max(reviews, 1),
        "sequential_burst": reviews >= 30 and agents <= max(10, reviews // 4),
    }


def reviewer_page_metrics(
    raw: dict[str, Any],
    independence_examples: list[dict[str, Any]],
) -> dict[str, Any]:
    profiles = raw.get("reviewer_profiles") or []
    top = profiles[0] if profiles else None
    example = independence_examples[0] if independence_examples else None
    return {
        "reviewer_count": len(profiles),
        "top_reviews": int(top["total_reviews"]) if top else 0,
        "example_count": len(independence_examples),
        "top_independence_pct": int(example["independence_pct"]) if example else 0,
        "top_example_agent": int(example["agent_id"]) if example else 0,
    }


def reviewer_independence_metrics(agent: dict[str, Any]) -> dict[str, Any]:
    independence_pct = (agent["independence"] or 0) * 100
    return {
        "agent_id": agent["id"],
        "independence_pct": independence_pct,
        "is_burst": agent["isBurst"],
        "low_independence": independence_pct < 60,
        "high_independence": independence_pct >= 80,
    }
