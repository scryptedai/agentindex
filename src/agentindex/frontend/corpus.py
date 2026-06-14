"""Load analytics corpus from SQLite."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentindex.config.settings import IndexSettings


@dataclass(frozen=True)
class CorpusPaths:
    db_path: Path
    schema_version: int


def open_corpus(settings: IndexSettings | None = None) -> tuple[sqlite3.Connection, CorpusPaths]:
    settings = settings or IndexSettings.load()
    db_path = settings.db_path
    if not db_path.is_file():
        raise FileNotFoundError(
            f"SQLite corpus not found at {db_path}. Run `poetry run agentindex-build` first."
        )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
    schema_version = int(row[0]) if row else 0
    return conn, CorpusPaths(db_path=db_path, schema_version=schema_version)


def corpus_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    agents = conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
    agents_with_feedback = conn.execute("SELECT COUNT(*) FROM reputation_agg").fetchone()[0]
    feedback_events = conn.execute("SELECT COUNT(*) FROM reputation_feedback").fetchone()[0]
    unique_owners = conn.execute("SELECT COUNT(DISTINCT owner) FROM agents").fetchone()[0]
    unique_clients = conn.execute("SELECT COUNT(DISTINCT client) FROM reputation_feedback").fetchone()[0]
    ens_links = conn.execute("SELECT COUNT(*) FROM ens_links").fetchone()[0]
    ens_verified = conn.execute("SELECT COUNT(*) FROM ens_links WHERE verified=1").fetchone()[0]
    cross_registrations = conn.execute("SELECT COUNT(*) FROM agent_registrations").fetchone()[0]
    last_at = conn.execute(
        "SELECT MAX(last_indexed_at) FROM registries"
    ).fetchone()[0]
    generated_at = last_at or datetime.now(timezone.utc).date().isoformat()
    return {
        "generated_at": generated_at,
        "network": "ethereum",
        "chain_id": 1,
        "agents": agents,
        "agents_with_feedback": agents_with_feedback,
        "feedback_events": feedback_events,
        "unique_owners": unique_owners,
        "unique_clients": unique_clients,
        "ens_links": ens_links,
        "ens_verified": ens_verified,
        "cross_registrations": cross_registrations,
    }


def daily_registrations(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            """
            SELECT date(first_seen_at) AS day, COUNT(*) AS registrations
            FROM agents WHERE first_seen_at IS NOT NULL
            GROUP BY 1 ORDER BY 1
            """
        )
    ]


def daily_feedback(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            """
            SELECT date(block_timestamp) AS day, COUNT(*) AS feedback,
                   ROUND(AVG(score), 2) AS avg_score
            FROM reputation_feedback WHERE block_timestamp IS NOT NULL
            GROUP BY 1 ORDER BY 1
            """
        )
    ]


def score_distribution(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            """
            SELECT CASE WHEN score<20 THEN '0-19' WHEN score<40 THEN '20-39'
              WHEN score<60 THEN '40-59' WHEN score<80 THEN '60-79' ELSE '80-100' END AS bucket,
              COUNT(*) AS count
            FROM reputation_feedback GROUP BY 1 ORDER BY 1
            """
        )
    ]


def owner_concentration(conn: sqlite3.Connection, *, limit: int = 25) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            """
            SELECT owner, COUNT(*) AS agent_count,
              SUM(CASE WHEN r.agent_id IS NOT NULL THEN 1 ELSE 0 END) AS with_feedback
            FROM agents a LEFT JOIN reputation_agg r USING(network_id, agent_id)
            GROUP BY owner HAVING COUNT(*) >= 10 ORDER BY agent_count DESC LIMIT ?
            """,
            (limit,),
        )
    ]


def reviewer_profiles(conn: sqlite3.Connection, *, limit: int = 30) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            """
            SELECT client, COUNT(*) AS total_reviews,
              COUNT(DISTINCT agent_id) AS unique_agents_reviewed,
              ROUND(AVG(score), 2) AS avg_score_given,
              MIN(block_timestamp) AS first_review, MAX(block_timestamp) AS last_review
            FROM reputation_feedback GROUP BY client ORDER BY total_reviews DESC LIMIT ?
            """,
            (limit,),
        )
    ]


def ens_name_collisions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            """
            SELECT ens_name, GROUP_CONCAT(agent_id) AS agent_ids,
              SUM(verified) AS verified_count, SUM(claimed) AS claimed_count
            FROM ens_links GROUP BY ens_name HAVING COUNT(*) > 1
            """
        )
    ]


def review_graph_edges(conn: sqlite3.Connection, *, limit: int = 200) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            """
            SELECT client, agent_id, COUNT(*) AS reviews, ROUND(AVG(score), 1) AS avg_score
            FROM reputation_feedback GROUP BY client, agent_id
            HAVING reviews >= 2 OR avg_score >= 95
            ORDER BY reviews DESC LIMIT ?
            """,
            (limit,),
        )
    ]


def agent_feedback(conn: sqlite3.Connection, agent_id: int) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            """
            SELECT client, score, block_timestamp, transaction_hash
            FROM reputation_feedback WHERE agent_id=? ORDER BY block_timestamp
            """,
            (agent_id,),
        )
    ]


def agent_row(conn: sqlite3.Connection, agent_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
    return dict(row) if row else None


def agent_agg(conn: sqlite3.Connection, agent_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM reputation_agg WHERE agent_id=?", (agent_id,)
    ).fetchone()
    return dict(row) if row else None


def agent_ens(conn: sqlite3.Connection, agent_id: int) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute("SELECT * FROM ens_links WHERE agent_id=?", (agent_id,))
    ]


def agent_cross(conn: sqlite3.Connection, agent_id: int) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM agent_registrations WHERE home_agent_id=?", (agent_id,)
        )
    ]


def spotlight_agent_ids(conn: sqlite3.Connection) -> list[int]:
    """Curated + data-driven spotlight set."""
    curated = [22721, 22771, 25255, 29058, 26433, 22903, 29011, 34135, 31875]
    top = [
        int(r[0])
        for r in conn.execute(
            """
            SELECT agent_id FROM reputation_agg
            ORDER BY n_feedback DESC LIMIT 12
            """
        )
    ]
    ens = [
        int(r[0])
        for r in conn.execute(
            "SELECT DISTINCT agent_id FROM ens_links WHERE verified=1 LIMIT 8"
        )
    ]
    seen: set[int] = set()
    ordered: list[int] = []
    for aid in curated + top + ens:
        if aid not in seen:
            seen.add(aid)
            ordered.append(aid)
    return ordered[:20]


def explorer_agent_entries(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """All agents worth surfacing in Explorer (feedback, ENS, or collisions)."""
    ids: set[int] = set()
    for row in conn.execute("SELECT agent_id FROM reputation_agg"):
        ids.add(int(row[0]))
    for row in conn.execute("SELECT DISTINCT agent_id FROM ens_links"):
        ids.add(int(row[0]))
    for row in conn.execute(
        """
        SELECT DISTINCT home_agent_id FROM agent_registrations
        """
    ):
        ids.add(int(row[0]))
    for collision in ens_name_collisions(conn):
        for part in collision["agent_ids"].split(","):
            ids.add(int(part.strip()))

    entries: list[dict[str, Any]] = []
    for aid in sorted(ids):
        agent = agent_row(conn, aid)
        if agent is None:
            continue
        entries.append(
            {
                "agent": agent,
                "reputation_agg": agent_agg(conn, aid),
                "ens_links": agent_ens(conn, aid),
                "cross_registrations": agent_cross(conn, aid),
                "feedback_events": agent_feedback(conn, aid),
            }
        )
    return entries


def build_spotlight_agents(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for aid in spotlight_agent_ids(conn):
        agent = agent_row(conn, aid)
        if agent is None:
            continue
        rows.append(
            {
                "agent": agent,
                "reputation_agg": agent_agg(conn, aid),
                "ens_links": agent_ens(conn, aid),
                "cross_registrations": agent_cross(conn, aid),
                "feedback_events": agent_feedback(conn, aid),
            }
        )
    return rows


def integrity_outliers(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            """
            SELECT agent_id, score, block_number, log_index
            FROM reputation_feedback WHERE score < 0 OR score > 100
            LIMIT 10
            """
        )
    ]


def cross_chain_summary(conn: sqlite3.Connection, *, limit: int = 12) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            """
            SELECT home_agent_id AS agent_id,
                   GROUP_CONCAT(DISTINCT chain_id) AS chain_ids,
                   COUNT(*) AS refs
            FROM agent_registrations
            WHERE chain_id != 1
            GROUP BY home_agent_id
            ORDER BY refs DESC LIMIT ?
            """,
            (limit,),
        )
    ]


def load_raw_bundle(conn: sqlite3.Connection) -> dict[str, Any]:
    return {
        "corpus_stats": corpus_stats(conn),
        "daily_registrations": daily_registrations(conn),
        "daily_feedback": daily_feedback(conn),
        "score_distribution": score_distribution(conn),
        "owner_concentration": owner_concentration(conn),
        "reviewer_profiles": reviewer_profiles(conn),
        "ens_name_collisions": ens_name_collisions(conn),
        "review_graph_edges": review_graph_edges(conn),
        "spotlight_agents": build_spotlight_agents(conn),
        "explorer_agents": explorer_agent_entries(conn),
        "integrity_outliers": integrity_outliers(conn),
    }
