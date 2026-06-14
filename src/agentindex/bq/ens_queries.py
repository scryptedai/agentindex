"""BigQuery SQL for ENSIP-25 agent-registration text records."""

from __future__ import annotations

import os

from agentindex.ens.constants import DEFAULT_ENS_BQ_DATASET, ensip25_key_prefix


def ens_bq_dataset() -> str:
    return os.environ.get("ENS_BQ_DATASET", DEFAULT_ENS_BQ_DATASET).strip()


def verified_agents_query() -> str:
    """All on-chain ENSIP-25 verifications for the Identity registry."""
    dataset = ens_bq_dataset()
    prefix = ensip25_key_prefix()
    agent_id_re = r"\]\[(\d+)\]$"
    return f"""
SELECT
  res.name AS ens_name,
  tr.key AS text_record_key,
  tr.value AS text_record_value,
  SAFE_CAST(REGEXP_EXTRACT(tr.key, r'{agent_id_re}') AS INT64) AS agent_id
FROM `{dataset}.resolvers` AS r
CROSS JOIN UNNEST(r.text_records) AS tr
JOIN `{dataset}.resolutions` AS res USING (node)
WHERE tr.key LIKE '{prefix}%'
  AND tr.value IS NOT NULL
  AND TRIM(tr.value) != ''
  AND REGEXP_EXTRACT(tr.key, r'{agent_id_re}') IS NOT NULL
ORDER BY agent_id, ens_name
"""
