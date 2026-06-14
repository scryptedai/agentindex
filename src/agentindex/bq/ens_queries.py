"""BigQuery SQL for ENSIP-25 agent-registration text records."""

from __future__ import annotations

from agentindex.config.models import EnsNetworkConfig


def verified_agents_query(ens: EnsNetworkConfig) -> str:
    """All on-chain ENSIP-25 verifications for a network's Identity registry."""
    dataset = ens.bq_dataset
    prefix = ens.ensip25_key_prefix()
    agent_id_re = r"\]\[(\d+)\]$"
    return f"""
SELECT
  res.name AS ens_name,
  tr.key AS text_record_key,
  tr.value AS text_record_value,
  SAFE_CAST(REGEXP_EXTRACT(tr.key, r'{agent_id_re}') AS INT64) AS agent_id
FROM `{dataset}.{ens.resolvers_table}` AS r
CROSS JOIN UNNEST(r.text_records) AS tr
JOIN `{dataset}.{ens.resolutions_table}` AS res USING (node)
WHERE tr.key LIKE '{prefix}%'
  AND tr.value IS NOT NULL
  AND TRIM(tr.value) != ''
  AND REGEXP_EXTRACT(tr.key, r'{agent_id_re}') IS NOT NULL
ORDER BY agent_id, ens_name
"""
