"""Reputation score helpers."""

from __future__ import annotations


def normalize_score(raw_value: int, value_decimals: int) -> float:
    if value_decimals <= 0:
        return float(raw_value)
    return raw_value / (10**value_decimals)
