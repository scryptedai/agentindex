"""BigQuery SQL for ERC-8004 log ingestion."""

from __future__ import annotations

from datetime import date

from agentindex.erc8004 import LOGS_TABLE, Registry


def range_bounds(start: date, end: date) -> tuple[str, str]:
    return f"{start.isoformat()} 00:00:00", f"{end.isoformat()} 23:59:59"


def _time_filter(start: str, end: str) -> str:
    return (
        f"block_timestamp >= TIMESTAMP '{start}' "
        f"AND block_timestamp <= TIMESTAMP '{end}'"
    )


def _raw_log_columns() -> str:
    return """
  block_hash,
  block_number,
  block_timestamp,
  transaction_hash,
  transaction_index,
  log_index,
  address,
  data,
  topics,
  removed"""


def identity_events_query(registry: Registry, start: str, end: str) -> str:
    return f"""
SELECT
  '{registry.event_name}' AS event_name,
  '{registry.name}' AS registry,
{_raw_log_columns()},
  SAFE_CAST(topics[SAFE_OFFSET(1)] AS INT64) AS agent_id,
  CONCAT('0x', SUBSTR(topics[SAFE_OFFSET(2)], 27)) AS owner,
  SAFE_CONVERT_BYTES_TO_STRING(FROM_HEX(SUBSTR(
    data,
    131,
    2 * SAFE_CAST(CONCAT('0x', SUBSTR(data, 67, 64)) AS INT64)
  ))) AS agent_uri
FROM `{LOGS_TABLE}`
WHERE address = '{registry.address}'
  AND topics[SAFE_OFFSET(0)] = '{registry.topic0}'
  AND {_time_filter(start, end)}
ORDER BY block_number, log_index
"""


def reputation_events_query(registry: Registry, start: str, end: str) -> str:
    return f"""
SELECT
  '{registry.event_name}' AS event_name,
  '{registry.name}' AS registry,
{_raw_log_columns()},
  SAFE_CAST(topics[SAFE_OFFSET(1)] AS INT64) AS agent_id,
  CONCAT('0x', SUBSTR(topics[SAFE_OFFSET(2)], 27)) AS client,
  SAFE_CAST(CONCAT('0x', SUBSTR(data, 67, 64)) AS INT64) AS raw_value,
  SAFE_CAST(CONCAT('0x', SUBSTR(data, 131, 64)) AS INT64) AS value_decimals
FROM `{LOGS_TABLE}`
WHERE address = '{registry.address}'
  AND topics[SAFE_OFFSET(0)] = '{registry.topic0}'
  AND {_time_filter(start, end)}
  AND SUBSTR(data, 67, 1) != 'f'
ORDER BY block_number, log_index
"""


def events_query(registry: Registry, start: str, end: str) -> str:
    if registry.name == "identity":
        return identity_events_query(registry, start, end)
    if registry.name == "reputation":
        return reputation_events_query(registry, start, end)
    raise ValueError(f"Unknown registry: {registry.name}")
