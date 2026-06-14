"""Tests for chart marks and cross-chain flow payloads."""

from __future__ import annotations

from agentindex.frontend.visuals import (
    build_chart_marks,
    build_cross_chain_flow,
    build_config_snapshot,
    chart_day_label,
)


def test_chart_day_label():
    assert chart_day_label("2026-02-09") == "Feb 9"


def test_build_chart_marks_spike():
    raw = {
        "daily_registrations": [
            {"day": "2026-02-09", "registrations": 800},
            {"day": "2026-02-10", "registrations": 50},
        ],
        "daily_feedback": [],
    }
    marks = build_chart_marks(raw)
    assert marks["pulse"]
    assert marks["pulse"][0]["text"] == "800 mints"
    assert marks["pulse"][0]["label"] == "Feb 9"
    assert marks["cumulative"][0]["text"] == "+800"


def test_build_chart_marks_low_score_burst():
    raw = {
        "daily_registrations": [{"day": "2026-03-01", "registrations": 10}],
        "daily_feedback": [
            {"day": "2026-03-15", "feedback": 100, "avg_score": 3.5},
        ],
    }
    marks = build_chart_marks(raw)
    assert marks["score"][0]["text"] == "low-score burst"
    assert marks["score"][0]["label"] == "Mar 15"


def test_build_cross_chain_flow():
    raw = {
        "cross_chain_by_chain": [
            {"chain_id": 1, "refs": 288},
            {"chain_id": 8453, "refs": 10},
        ],
    }
    flow = build_cross_chain_flow(raw, home_chain_id=1)
    assert flow["total"] == 298
    assert len(flow["flows"]) == 2
    assert flow["flows"][0]["n"] == 288
    assert "self-ref" in flow["flows"][0]["chain"]


def test_build_config_snapshot_minimal():
    class _Ens:
        bq_dataset = "bigquery.public.ens"

    class _Registry:
        address = "0xabc"
        name = "Identity"

    class _Network:
        key = "ethereum"
        chain_id = 1
        lag_days = 2
        ens_enabled = True
        ens = _Ens()
        registries = [_Registry()]

    class _Config:
        def network(self):
            return _Network()

    snap = build_config_snapshot(_Config())
    assert "network  = ethereum" in snap
    assert "0xabc" in snap
    assert "ens_bq" in snap
