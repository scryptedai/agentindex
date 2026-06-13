"""Shared helpers for dev smoke tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_dotenv() -> None:
    """Load `.env` from repo root if python-dotenv is installed."""
    env_path = repo_root() / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv as _load
    except ImportError:
        return
    _load(env_path)


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"Missing required env var: {name}")
    return value


def fail(message: str, code: int = 1) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(code)


def ok(message: str) -> None:
    print(f"OK: {message}")
