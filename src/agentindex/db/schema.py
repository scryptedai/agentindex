"""SQLite schema for the local agent corpus."""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1

_DDL = """
CREATE TABLE IF NOT EXISTS schema_meta (
  version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS registries (
  network_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  address TEXT NOT NULL,
  last_indexed_block INTEGER,
  last_indexed_log_index INTEGER,
  last_indexed_at TEXT,
  PRIMARY KEY (network_id, address)
);

CREATE TABLE IF NOT EXISTS agents (
  network_id INTEGER NOT NULL,
  agent_id INTEGER NOT NULL,
  owner TEXT NOT NULL,
  token_uri TEXT NOT NULL DEFAULT '',
  first_seen_block INTEGER NOT NULL,
  first_seen_log_index INTEGER NOT NULL,
  first_seen_at TEXT,
  last_updated_block INTEGER NOT NULL,
  last_updated_log_index INTEGER NOT NULL,
  PRIMARY KEY (network_id, agent_id)
);

CREATE TABLE IF NOT EXISTS reputation_feedback (
  network_id INTEGER NOT NULL,
  agent_id INTEGER NOT NULL,
  client TEXT NOT NULL,
  score REAL NOT NULL,
  raw_value INTEGER NOT NULL,
  value_decimals INTEGER NOT NULL,
  block_number INTEGER NOT NULL,
  log_index INTEGER NOT NULL,
  block_timestamp TEXT,
  transaction_hash TEXT,
  revoked INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (network_id, block_number, log_index)
);

CREATE TABLE IF NOT EXISTS reputation_agg (
  network_id INTEGER NOT NULL,
  agent_id INTEGER NOT NULL,
  composite REAL NOT NULL,
  n_feedback INTEGER NOT NULL,
  last_computed_block INTEGER NOT NULL,
  PRIMARY KEY (network_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_agents_first_seen
  ON agents (network_id, first_seen_block, agent_id);

CREATE INDEX IF NOT EXISTS idx_feedback_agent
  ON reputation_feedback (network_id, agent_id);

CREATE INDEX IF NOT EXISTS idx_feedback_block
  ON reputation_feedback (network_id, block_number, log_index);
"""


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    row = conn.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO schema_meta (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
    conn.commit()
