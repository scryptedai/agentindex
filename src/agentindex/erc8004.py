"""ERC-8004 reference constants (workshop gist — pin in docs/SOURCES.md before prod)."""

from __future__ import annotations

from dataclasses import dataclass

# https://gist.github.com/godeva/040270ac2924501063d875b302cf2e91
LOGS_TABLE = "bigquery-public-data.goog_blockchain_ethereum_mainnet_us.logs"
LAUNCH_DATE = "2026-02-01"  # first observed registrations; Jan 28 scans ~3.5 GB/day empty


@dataclass(frozen=True)
class Registry:
    name: str
    address: str
    topic0: str
    event_name: str


IDENTITY = Registry(
    name="identity",
    address="0x8004a169fb4a3325136eb29fa0ceb6d2e539a432",
    topic0="0xca52e62c367d81bb2e328eb795f7c7ba24afb478408a26c0e201d155c449bc4a",
    event_name="Registered",
)

REPUTATION = Registry(
    name="reputation",
    address="0x8004baa17c55a88189ae136b182e5fda19de9b63",
    topic0="0x6a4a61743519c9d648a14e6493f47dbe3ff1aa29e7785c96c8326a205e58febc",
    event_name="NewFeedback",
)

REGISTRIES = (IDENTITY, REPUTATION)
