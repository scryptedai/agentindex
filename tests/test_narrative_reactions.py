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
