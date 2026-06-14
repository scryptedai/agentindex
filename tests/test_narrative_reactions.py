"""Tests for declarative narrative reactions."""

from __future__ import annotations

from agentindex.frontend.narratives.reactions import (
    eval_when,
    pick_all,
    pick_first,
    react_text,
)


def test_eval_when_all():
    ctx = {"spike_registrations": 600, "spike_share": 6.0}
    when = {
        "all": [
            {"field": "spike_registrations", "op": "gte", "value": 500},
            {"field": "spike_share", "op": "gte", "value": 5},
        ]
    }
    assert eval_when(when, ctx) is True


def test_pick_first_major_spike():
    reactions = [
        {
            "id": "major",
            "priority": 90,
            "when": {
                "all": [
                    {"field": "spike_registrations", "op": "gte", "value": 500},
                    {"field": "spike_share", "op": "gte", "value": 5},
                ]
            },
            "text": "Spike {spike_registrations}",
        },
        {"id": "default", "priority": 0, "default": True, "text": "Quiet"},
    ]
    picked = pick_first(reactions, {"spike_registrations": 800, "spike_share": 10})
    assert picked["id"] == "major"
    text, rid = react_text(reactions, {"spike_registrations": 800, "spike_share": 10})
    assert text == "Spike 800"
    assert rid == "major"


def test_pick_first_falls_back_to_default():
    reactions = [
        {
            "id": "major",
            "priority": 90,
            "when": {"field": "spike_registrations", "op": "gte", "value": 500},
            "text": "Spike",
        },
        {"id": "default", "priority": 0, "default": True, "text": "Quiet"},
    ]
    picked = pick_first(reactions, {"spike_registrations": 10})
    assert picked["id"] == "default"


def test_pick_all_confidence_reasons():
    reactions = [
        {
            "id": "factory",
            "priority": 90,
            "when": {"field": "is_factory", "op": "eq", "value": True},
            "text": "Factory {owner_count}",
        },
        {
            "id": "small",
            "priority": 80,
            "when": {"field": "n", "op": "lt", "value": 5},
            "text": "Small {n}",
        },
    ]
    matched = pick_all(
        reactions,
        {"is_factory": True, "owner_count": 120, "n": 3, "has_feedback": True},
    )
    assert {m["id"] for m in matched} == {"factory", "small"}


def test_signal_copy_factory_dominant():
    from agentindex.frontend.analytics import _signal_copy

    copy = _signal_copy(
        "factory_owner",
        {
            "owner_share": 25.0,
            "agent_count": 3000,
            "total_agents": 12000,
            "with_feedback": 50,
            "feedback_ratio": 50 / 3000,
            "feedback_ratio_pct": 100 * 50 / 3000,
        },
        "factory",
    )
    assert copy["title_reaction"] == "fo_title_dominant"
    assert "25" in copy["title"]
    assert copy["why_reaction"] == "why_factory_dominant"


def test_overview_metrics_and_reactions_integration():
    from agentindex.frontend.narratives.metrics import overview_metrics
    from agentindex.frontend.narratives.reactions import load_reactions

    raw = {
        "corpus_stats": {
            "agents": 1000,
            "agents_with_feedback": 100,
            "feedback_events": 500,
            "unique_clients": 20,
            "ens_links": 50,
            "ens_verified": 5,
            "generated_at": "2026-06-01",
        },
        "daily_registrations": [
            {"day": "2026-02-01", "registrations": 10},
            {"day": "2026-02-02", "registrations": 800},
            {"day": "2026-02-03", "registrations": 5},
        ],
        "daily_feedback": [
            {"day": "2026-02-02", "feedback": 200, "avg_score": 3.5},
        ],
        "score_distribution": [
            {"bucket": "80-100", "count": 300},
            {"bucket": "0-19", "count": 50},
        ],
        "owner_concentration": [{"agent_count": 600, "with_feedback": 10, "owner": "0x1"}],
    }
    ctx = overview_metrics(raw, signal_count=3)
    assert ctx["spike_registrations"] == 800
    assert ctx["coordinated_downvote"] is True

    pulse_text, pulse_id = react_text(load_reactions()["overview"]["hero"]["pulse"], ctx)
    assert pulse_id == "major_registration_spike"
    assert "800" in pulse_text

    silent_text, _ = react_text(load_reactions()["overview"]["kpi"]["silent_majority"], ctx)
    assert "900" in silent_text.replace(",", "")


def test_corpus_metrics_staleness_and_bytes():
    from agentindex.frontend.narratives.metrics import corpus_metrics
    from agentindex.frontend.narratives.reactions import load_reactions, react_bundle, react_text

    raw = {
        "corpus_stats": {"generated_at": "2020-01-01", "cross_registrations": 100, "chain_id": 1},
        "cross_chain_stats": {
            "total": 100,
            "on_home_chain": 95,
            "foreign_chain": 5,
            "foreign_chain_count": 2,
            "home_chain_id": 1,
        },
        "ingest_meta": {"bytes_billed": 8_400_000_000},
    }
    ctx = corpus_metrics(raw)
    assert ctx["bytes_billed_gb"] == 8.4
    assert ctx["days_since_indexed"] >= 2000

    rx = load_reactions()["corpus"]
    stale = react_bundle(rx["honesty_callout"], ctx, fields=("text",))
    assert stale["id"] == "corpus_stale"
    note, note_id = react_text(rx["bytes_billed_note"], ctx)
    assert note_id == "bytes_recorded"


def test_identity_cross_chain_subtitle():
    from agentindex.frontend.narratives.metrics import identity_metrics
    from agentindex.frontend.narratives.reactions import load_reactions, react_bundle

    raw = {
        "corpus_stats": {"cross_registrations": 500, "chain_id": 1},
        "cross_chain_stats": {
            "total": 500,
            "on_home_chain": 480,
            "foreign_chain": 20,
            "foreign_chain_count": 2,
            "home_chain_id": 1,
        },
        "ens_name_collisions": [],
    }
    ctx = identity_metrics(raw)
    ctx["network_label"] = "Ethereum Mainnet"
    subtitle = react_bundle(
        load_reactions()["identity"]["cross_chain_subtitle"],
        ctx,
        fields=("text",),
    )
    assert subtitle["id"] == "cross_subtitle_multi_chain"
    assert "2 foreign chains" in subtitle["text"]


def test_reputation_coverage_and_page_descriptions():
    from agentindex.frontend.narratives.metrics import overview_metrics
    from agentindex.frontend.narratives.reactions import load_reactions, react_text
    from agentindex.frontend.analytics import _react_page_description

    raw = {
        "corpus_stats": {
            "agents": 1000,
            "agents_with_feedback": 50,
            "feedback_events": 500,
            "unique_clients": 20,
            "ens_links": 50,
            "ens_verified": 5,
            "generated_at": "2026-06-01",
        },
        "daily_registrations": [{"day": "2026-02-01", "registrations": 10}],
        "daily_feedback": [],
        "score_distribution": [],
        "owner_concentration": [],
    }
    ctx = overview_metrics(raw, signal_count=0)
    ctx.update({"network_label": "Ethereum Mainnet", "chain_id": 1, "agent_count": 1000})
    insight, insight_id = react_text(
        load_reactions()["overview"]["reputation_coverage"]["insight"], ctx
    )
    assert insight_id == "cov_silent_majority"
    assert "950" in insight.replace(",", "")

    page = _react_page_description(
        "overview",
        ctx,
        "fallback {network_label}",
    )
    assert "Ethereum Mainnet" in page
    assert "95" in page or "silent" in page.lower()


def test_dossier_empty_states():
    from agentindex.frontend.analytics import dossier_empty_states

    agent = {
        "id": 1,
        "n": 0,
        "composite": None,
        "burstCount": 0,
        "burstWindowMin": 0,
        "uniqueClients": 0,
        "ownerCount": 1,
        "ens": [],
        "independence": None,
        "isBurst": False,
        "isFactory": False,
        "isCollision": False,
        "cliff": False,
        "sparse": False,
        "hasFeedback": False,
        "confidence": {"level": "none", "reasons": []},
        "spanDays": 0,
    }
    empty = dossier_empty_states(agent, network_label="Ethereum Mainnet")
    assert "no reputation events" in empty["events"].lower()
    assert "timeline needs" in empty["timeline"].lower()
