"""Network metadata for the dashboard (from config/default.json)."""

from __future__ import annotations

from typing import Any

from agentindex.config.models import AppConfig, NetworkConfig

_NETWORK_LABELS: dict[str, str] = {
    "ethereum": "Ethereum Mainnet",
    "base": "Base",
    "polygon": "Polygon",
    "arbitrum": "Arbitrum",
    "optimism": "Optimism",
}


def network_label(network: NetworkConfig) -> str:
    return _NETWORK_LABELS.get(network.key, network.key.replace("_", " ").title())


def build_network_meta(config: AppConfig) -> dict[str, Any]:
    active = config.network()
    available: list[dict[str, Any]] = []
    for key, network in config.networks.items():
        available.append(
            {
                "key": key,
                "label": network_label(network),
                "chain_id": network.chain_id,
                "enabled": network.enabled,
                "coming_soon": not network.enabled,
            }
        )
    return {
        "active": {
            "key": active.key,
            "label": network_label(active),
            "chain_id": active.chain_id,
        },
        "available": available,
    }
