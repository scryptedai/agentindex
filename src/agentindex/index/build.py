"""Build SQLite corpus from ingested JSONL."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from agentindex.config.models import NetworkConfig
from agentindex.config.settings import IndexSettings
from agentindex.db.connection import open_db
from agentindex.erc8004 import Registry
from agentindex.ens.registrations import refresh_registration_jsonl
from agentindex.index.ens_sources import read_jsonl
from agentindex.index.reputation import normalize_score
from agentindex.index.sources import iter_registry_events
from agentindex.storage.ens_meta import EnsMeta
from agentindex.storage.paths import DataLayout

LinkKey = tuple[int, str]


@dataclass(frozen=True)
class BuildStats:
    agents: int
    feedback: int
    agents_with_feedback: int
    ens_links: int
    ens_verified_links: int
    ens_agents: int
    ens_names: int
    cross_registrations: int
    identity_events: int
    reputation_events: int


def _upsert_registry(
    conn: sqlite3.Connection,
    network_id: int,
    registry: Registry,
    last_block: int | None,
    last_log_index: int | None,
    last_at: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO registries (
          network_id, kind, address,
          last_indexed_block, last_indexed_log_index, last_indexed_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (network_id, address) DO UPDATE SET
          last_indexed_block = excluded.last_indexed_block,
          last_indexed_log_index = excluded.last_indexed_log_index,
          last_indexed_at = excluded.last_indexed_at
        """,
        (
            network_id,
            registry.name,
            registry.address.lower(),
            last_block,
            last_log_index,
            last_at,
        ),
    )


def _index_identity(
    conn: sqlite3.Connection,
    network_id: int,
    events: list[dict[str, Any]],
) -> int:
    for row in events:
        block_number = int(row["block_number"])
        log_index = int(row["log_index"])
        agent_id = int(row["agent_id"])
        owner = str(row["owner"]).lower()
        token_uri = str(row.get("agent_uri") or "")
        block_ts = row.get("block_timestamp")

        conn.execute(
            """
            INSERT INTO agents (
              network_id, agent_id, owner, token_uri,
              first_seen_block, first_seen_log_index, first_seen_at,
              last_updated_block, last_updated_log_index
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (network_id, agent_id) DO UPDATE SET
              owner = excluded.owner,
              token_uri = excluded.token_uri,
              last_updated_block = excluded.last_updated_block,
              last_updated_log_index = excluded.last_updated_log_index
            WHERE excluded.last_updated_block > agents.last_updated_block
               OR (
                 excluded.last_updated_block = agents.last_updated_block
                 AND excluded.last_updated_log_index > agents.last_updated_log_index
               )
            """,
            (
                network_id,
                agent_id,
                owner,
                token_uri,
                block_number,
                log_index,
                block_ts,
                block_number,
                log_index,
            ),
        )
    return len(events)


def _index_reputation(
    conn: sqlite3.Connection,
    network_id: int,
    events: list[dict[str, Any]],
) -> int:
    for row in events:
        raw_value = int(row["raw_value"])
        value_decimals = int(row.get("value_decimals") or 0)
        conn.execute(
            """
            INSERT INTO reputation_feedback (
              network_id, agent_id, client, score,
              raw_value, value_decimals,
              block_number, log_index,
              block_timestamp, transaction_hash, revoked
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT (network_id, block_number, log_index) DO UPDATE SET
              agent_id = excluded.agent_id,
              client = excluded.client,
              score = excluded.score,
              raw_value = excluded.raw_value,
              value_decimals = excluded.value_decimals,
              block_timestamp = excluded.block_timestamp,
              transaction_hash = excluded.transaction_hash
            """,
            (
                network_id,
                int(row["agent_id"]),
                str(row["client"]).lower(),
                normalize_score(raw_value, value_decimals),
                raw_value,
                value_decimals,
                int(row["block_number"]),
                int(row["log_index"]),
                row.get("block_timestamp"),
                row.get("transaction_hash"),
            ),
        )
    return len(events)


def _recompute_reputation_agg(conn: sqlite3.Connection, network_id: int) -> int:
    conn.execute(
        "DELETE FROM reputation_agg WHERE network_id = ?",
        (network_id,),
    )
    conn.execute(
        """
        INSERT INTO reputation_agg (
          network_id, agent_id, composite, n_feedback, last_computed_block
        )
        SELECT
          network_id,
          agent_id,
          AVG(score),
          COUNT(*),
          MAX(block_number)
        FROM reputation_feedback
        WHERE network_id = ? AND revoked = 0
        GROUP BY network_id, agent_id
        """,
        (network_id,),
    )
    row = conn.execute(
        "SELECT COUNT(*) FROM reputation_agg WHERE network_id = ?",
        (network_id,),
    ).fetchone()
    return int(row[0]) if row else 0


def _registry_watermark(
    events: list[dict[str, Any]],
) -> tuple[int | None, int | None, str | None]:
    if not events:
        return None, None, None
    last = events[-1]
    return (
        int(last["block_number"]),
        int(last["log_index"]),
        str(last.get("block_timestamp") or ""),
    )


def _link_key(agent_id: int, ens_name: str) -> LinkKey:
    return agent_id, ens_name.lower().strip()


def _index_ens(
    conn: sqlite3.Connection,
    network_id: int,
    layout: DataLayout,
) -> tuple[int, int, int, int]:
    meta = EnsMeta.load(layout.ens_meta_path)
    refresh_registration_jsonl(layout, meta)

    verified_rows = read_jsonl(layout.ens_verified_path)
    claimed_rows = read_jsonl(layout.ens_claimed_path)

    merged: dict[LinkKey, dict[str, Any]] = {}

    for row in verified_rows:
        agent_id = int(row["agent_id"])
        ens_name = str(row["ens_name"]).lower().strip()
        key = _link_key(agent_id, ens_name)
        merged[key] = {
            "verified": 1,
            "claimed": 0,
            "text_record_key": row.get("text_record_key"),
            "text_record_value": row.get("text_record_value"),
            "token_uri": None,
            "registration_path": None,
            "checked_at": row.get("fetched_at"),
        }

    for row in claimed_rows:
        agent_id = int(row["agent_id"])
        ens_name = str(row.get("claimed_ens") or "").lower().strip()
        if not ens_name:
            continue
        key = _link_key(agent_id, ens_name)
        reg_path = str(layout.ens_registration_path(agent_id))
        entry = merged.get(key)
        if entry is None:
            merged[key] = {
                "verified": 0,
                "claimed": 1,
                "text_record_key": None,
                "text_record_value": None,
                "token_uri": row.get("token_uri"),
                "registration_path": reg_path,
                "checked_at": row.get("fetched_at"),
            }
            continue
        entry["claimed"] = 1
        entry["token_uri"] = row.get("token_uri") or entry.get("token_uri")
        entry["registration_path"] = reg_path
        if entry.get("checked_at") is None:
            entry["checked_at"] = row.get("fetched_at")

    verified_links = 0
    agents: set[int] = set()
    names: set[str] = set()

    for (agent_id, ens_name), entry in merged.items():
        if entry.get("verified"):
            verified_links += 1
        agents.add(agent_id)
        names.add(ens_name)
        conn.execute(
            """
            INSERT INTO ens_links (
              network_id, agent_id, ens_name,
              verified, claimed,
              text_record_key, text_record_value,
              token_uri, registration_path, checked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                network_id,
                agent_id,
                ens_name,
                int(entry.get("verified") or 0),
                int(entry.get("claimed") or 0),
                entry.get("text_record_key"),
                entry.get("text_record_value"),
                entry.get("token_uri"),
                entry.get("registration_path"),
                entry.get("checked_at"),
            ),
        )

    return len(merged), verified_links, len(agents), len(names)


def _index_cross_registrations(
    conn: sqlite3.Connection,
    network_id: int,
    layout: DataLayout,
) -> int:
    rows = read_jsonl(layout.ens_cross_registrations_path)
    for row in rows:
        conn.execute(
            """
            INSERT INTO agent_registrations (
              home_network_id, home_agent_id,
              chain_id, registry_address, agent_id,
              source, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                network_id,
                int(row["home_agent_id"]),
                int(row["chain_id"]),
                str(row["registry_address"]).lower(),
                int(row["agent_id"]),
                str(row.get("source") or "registration"),
                row.get("fetched_at"),
            ),
        )
    return len(rows)


def _build_network(
    conn: sqlite3.Connection,
    layout: DataLayout,
    network: NetworkConfig,
) -> tuple[int, int, int, int, int, int, int, int, int]:
    network_id = network.chain_id
    identity_events = list(iter_registry_events(layout.registry_dir("identity")))
    reputation_events = list(iter_registry_events(layout.registry_dir("reputation")))

    conn.execute("DELETE FROM agents WHERE network_id = ?", (network_id,))
    conn.execute(
        "DELETE FROM reputation_feedback WHERE network_id = ?",
        (network_id,),
    )
    conn.execute(
        "DELETE FROM reputation_agg WHERE network_id = ?",
        (network_id,),
    )
    conn.execute("DELETE FROM ens_links WHERE network_id = ?", (network_id,))
    conn.execute(
        "DELETE FROM agent_registrations WHERE home_network_id = ?",
        (network_id,),
    )

    _index_identity(conn, network_id, identity_events)
    _index_reputation(conn, network_id, reputation_events)
    agents_with_feedback = _recompute_reputation_agg(conn, network_id)

    ens_links = ens_verified_links = ens_agents = ens_names = 0
    cross_registrations = 0
    if layout.ens_dir.is_dir():
        ens_links, ens_verified_links, ens_agents, ens_names = _index_ens(
            conn, network_id, layout
        )
        cross_registrations = _index_cross_registrations(conn, network_id, layout)

    indexed_at = datetime.now(timezone.utc).isoformat()
    for registry in network.registries:
        events = (
            identity_events
            if registry.name == "identity"
            else reputation_events
        )
        block, log_index, ts = _registry_watermark(events)
        _upsert_registry(
            conn,
            network_id,
            registry,
            block,
            log_index,
            ts or indexed_at,
        )

    return (
        len(identity_events),
        len(reputation_events),
        agents_with_feedback,
        ens_links,
        ens_verified_links,
        ens_agents,
        ens_names,
        cross_registrations,
        network_id,
    )


def build_index(
    db_path,
    settings: IndexSettings | None = None,
) -> BuildStats:
    """Rebuild the SQLite corpus from JSONL for all enabled networks."""
    settings = settings or IndexSettings.load()
    config = settings.config

    conn = open_db(db_path)
    agent_count = 0
    feedback_count = 0
    agents_with_feedback = 0
    ens_links = 0
    ens_verified_links = 0
    ens_agents = 0
    ens_names = 0
    cross_registrations = 0
    identity_events = 0
    reputation_events = 0

    try:
        conn.execute("BEGIN")
        for network in config.enabled_networks():
            layout = DataLayout(config.data_dir, network=network.key)
            (
                id_events,
                rep_events,
                with_feedback,
                links,
                verified_links,
                link_agents,
                link_names,
                cross,
                network_id,
            ) = _build_network(conn, layout, network)

            identity_events += id_events
            reputation_events += rep_events
            agents_with_feedback += with_feedback
            ens_links += links
            ens_verified_links += verified_links
            ens_agents += link_agents
            ens_names += link_names
            cross_registrations += cross

            agent_count += conn.execute(
                "SELECT COUNT(*) FROM agents WHERE network_id = ?",
                (network_id,),
            ).fetchone()[0]
            feedback_count += conn.execute(
                "SELECT COUNT(*) FROM reputation_feedback WHERE network_id = ?",
                (network_id,),
            ).fetchone()[0]

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return BuildStats(
        agents=int(agent_count),
        feedback=int(feedback_count),
        agents_with_feedback=agents_with_feedback,
        ens_links=ens_links,
        ens_verified_links=ens_verified_links,
        ens_agents=ens_agents,
        ens_names=ens_names,
        cross_registrations=cross_registrations,
        identity_events=identity_events,
        reputation_events=reputation_events,
    )
