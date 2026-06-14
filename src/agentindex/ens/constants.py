"""ENSIP-25 constants for ERC-8004 Identity Registry on Ethereum mainnet."""

from __future__ import annotations

from agentindex.erc8004 import IDENTITY

# ERC-7930 interoperable address (EIP-155 chain ID 1, 20-byte address).
# Source: https://docs.ens.domains/ensip/25/
IDENTITY_REGISTRY_ERC7930 = (
    "0x000100000101148004a169fb4a3325136eb29fa0ceb6d2e539a432"
)

DEFAULT_ENS_BQ_DATASET = "web3-publicgoods.ens"


def ensip25_key(agent_id: int) -> str:
    return f"agent-registration[{IDENTITY_REGISTRY_ERC7930}][{agent_id}]"


def ensip25_key_prefix() -> str:
    return f"agent-registration[{IDENTITY_REGISTRY_ERC7930}]["
