"""Build SQLite corpus from ingested JSONL."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from agentindex.db.connection import open_db
from agentindex.erc8004 import IDENTITY, REPUTATION, Registry
from agentindex.index.reputation import normalize_score
from agentindex.index.sources import iter_registry_events
from agentindex.storage.paths import DataLayout


ETHEREUM_MAINNET = 1


@dataclass(frozen=True)
class BuildStats:
    agents: int
    feedback: int
    agents_with_feedback: int
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


def build_index(
    db_path,
    layout: DataLayout,
    *,
    network_id: int = ETHEREUM_MAINNET,
) -> BuildStats:
    """Rebuild the SQLite corpus from JSONL under ``layout``."""
    identity_events = list(iter_registry_events(layout.registry_dir("identity")))
    reputation_events = list(iter_registry_events(layout.registry_dir("reputation")))

    conn = open_db(db_path)
    try:
        conn.execute("BEGIN")
        conn.execute("DELETE FROM agents WHERE network_id = ?", (network_id,))
        conn.execute(
            "DELETE FROM reputation_feedback WHERE network_id = ?",
            (network_id,),
        )
        conn.execute(
            "DELETE FROM reputation_agg WHERE network_id = ?",
            (network_id,),
        )

        _index_identity(conn, network_id, identity_events)
        _index_reputation(conn, network_id, reputation_events)
        agents_with_feedback = _recompute_reputation_agg(conn, network_id)

        indexed_at = datetime.now(timezone.utc).isoformat()
        id_block, id_log, id_at = _registry_watermark(identity_events)
        rep_block, rep_log, rep_at = _registry_watermark(reputation_events)
        _upsert_registry(
            conn, network_id, IDENTITY, id_block, id_log, id_at or indexed_at
        )
        _upsert_registry(
            conn, network_id, REPUTATION, rep_block, rep_log, rep_at or indexed_at
        )

        agent_count = conn.execute(
            "SELECT COUNT(*) FROM agents WHERE network_id = ?",
            (network_id,),
        ).fetchone()[0]
        feedback_count = conn.execute(
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
        identity_events=len(identity_events),
        reputation_events=len(reputation_events),
    )
