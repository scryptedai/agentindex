"""Fetch and parse ERC-8004 registration files from token_uri."""

from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote_to_bytes

from agentindex.index.sources import iter_registry_events
from agentindex.storage.ens_meta import EnsMeta, RegistrationFetchState
from agentindex.storage.jsonl import write_rows_replace
from agentindex.storage.paths import DataLayout

ENS_NAME_RE = re.compile(
    r"(?i)\b([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.eth)\b"
)
DEFAULT_TIMEOUT = 30
DEFAULT_WORKERS = 8


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _decode_data_uri(uri: str) -> dict[str, Any]:
    if not uri.startswith("data:"):
        raise ValueError("not a data: URI")
    header, _, payload = uri.partition(",")
    if not payload:
        raise ValueError("empty data URI payload")
    if ";base64" in header:
        raw = base64.b64decode(payload)
    else:
        raw = unquote_to_bytes(payload)
    return json.loads(raw.decode("utf-8"))


def load_registration_from_uri(uri: str, *, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    uri = uri.strip()
    if not uri:
        raise ValueError("empty token_uri")
    if uri.startswith("{"):
        return json.loads(uri)
    if uri.startswith("data:"):
        return _decode_data_uri(uri)
    if uri.startswith("http://") or uri.startswith("https://"):
        req = urllib.request.Request(
            uri,
            headers={"User-Agent": "agentindex/0.1 (+https://github.com/agentindex)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
        return json.loads(body.decode("utf-8"))
    raise ValueError(f"unsupported token_uri scheme: {uri[:48]!r}")


def extract_ens_names(value: Any) -> list[str]:
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, str):
            for match in ENS_NAME_RE.finditer(node):
                found.add(match.group(1).lower())
        elif isinstance(node, dict):
            for item in node.values():
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(value)
    return sorted(found)


def extract_claimed_ens_names(registration: dict[str, Any]) -> list[str]:
    """Ordered, deduped ENS names explicitly declared in registration JSON."""
    ordered: list[str] = []
    seen: set[str] = set()

    def add(name: str | None) -> None:
        if not name:
            return
        normalized = name.lower()
        if normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)

    for endpoint in registration.get("endpoints") or []:
        if not isinstance(endpoint, dict):
            continue
        if str(endpoint.get("name", "")).lower() != "ens":
            continue
        match = ENS_NAME_RE.search(str(endpoint.get("endpoint", "")))
        add(match.group(1) if match else None)

    for service in registration.get("services") or []:
        if not isinstance(service, dict):
            continue
        if str(service.get("name", "")).lower() == "ens":
            match = ENS_NAME_RE.search(str(service.get("endpoint", "")))
            add(match.group(1) if match else None)
            continue
        if "ens" in str(service.get("type", "")).lower():
            for key in ("name", "endpoint", "url"):
                match = ENS_NAME_RE.search(str(service.get(key, "")))
                if match:
                    add(match.group(1))

    operator = registration.get("operator")
    if isinstance(operator, dict):
        add(str(operator.get("ens") or "").strip().lower() or None)

    for name in extract_ens_names(registration):
        add(name)

    return ordered


def pick_claimed_ens(registration: dict[str, Any]) -> str | None:
    names = extract_claimed_ens_names(registration)
    return names[0] if names else None


def parse_registry_ref(agent_registry: str) -> tuple[int, str] | None:
    """Parse ERC-8004 ``agentRegistry`` refs such as ``eip155:1:0x...``."""
    value = agent_registry.strip()
    if not value.startswith("eip155:"):
        return None
    parts = value.split(":")
    if len(parts) < 3:
        return None
    try:
        chain_id = int(parts[1])
    except ValueError:
        return None
    address = parts[-1].lower()
    if not address.startswith("0x"):
        return None
    return chain_id, address


def extract_cross_network_registrations(
    registration: dict[str, Any],
) -> list[dict[str, int | str]]:
    """Other chain/registry memberships declared in registration JSON."""
    rows: list[dict[str, int | str]] = []
    for item in registration.get("registrations") or []:
        if not isinstance(item, dict):
            continue
        ref = item.get("agentRegistry") or item.get("agent_registry")
        agent_id_raw = item.get("agentId")
        if agent_id_raw is None:
            agent_id_raw = item.get("agent_id")
        if ref is None or agent_id_raw is None:
            continue
        parsed = parse_registry_ref(str(ref))
        if parsed is None:
            continue
        try:
            agent_id = int(agent_id_raw)
        except (TypeError, ValueError):
            continue
        chain_id, registry_address = parsed
        rows.append(
            {
                "chain_id": chain_id,
                "registry_address": registry_address,
                "agent_id": agent_id,
            }
        )
    return rows


def latest_agents_with_uri(layout: DataLayout) -> dict[int, str]:
    """Most recent token_uri per agent_id from identity JSONL."""
    agents: dict[int, tuple[int, int, str]] = {}
    for row in iter_registry_events(layout.registry_dir("identity")):
        agent_id = int(row["agent_id"])
        uri = str(row.get("agent_uri") or "").strip()
        if not uri:
            continue
        block = int(row["block_number"])
        log_index = int(row["log_index"])
        current = agents.get(agent_id)
        if current is None or (block, log_index) >= (current[0], current[1]):
            agents[agent_id] = (block, log_index, uri)
    return {agent_id: uri for agent_id, (_, _, uri) in agents.items()}


def refresh_registration_jsonl(
    layout: DataLayout,
    meta: EnsMeta | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rebuild claimed + cross-network JSONL from cached registration files."""
    reg_dir = layout.ens_dir / "registrations"
    if not reg_dir.is_dir():
        return [], []

    claimed_records: list[dict[str, Any]] = []
    cross_records: list[dict[str, Any]] = []

    for path in sorted(reg_dir.glob("*.json")):
        home_agent_id = int(path.stem)
        try:
            registration = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        token_uri = ""
        fetched_at = _now_iso()
        if meta is not None:
            state = meta.registration_uris.get(str(home_agent_id))
            if state:
                token_uri = state.token_uri
                fetched_at = state.fetched_at

        for ens_name in extract_claimed_ens_names(registration):
            claimed_records.append(
                {
                    "agent_id": home_agent_id,
                    "claimed_ens": ens_name,
                    "token_uri": token_uri,
                    "source": "registration",
                    "fetched_at": fetched_at,
                    "fetch_error": None,
                }
            )

        for ref in extract_cross_network_registrations(registration):
            cross_records.append(
                {
                    "home_agent_id": home_agent_id,
                    "chain_id": ref["chain_id"],
                    "registry_address": ref["registry_address"],
                    "agent_id": ref["agent_id"],
                    "source": "registration",
                    "fetched_at": fetched_at,
                }
            )

    claimed_records.sort(key=lambda row: (row["agent_id"], row["claimed_ens"]))
    cross_records.sort(
        key=lambda row: (
            row["home_agent_id"],
            row["chain_id"],
            row["registry_address"],
            row["agent_id"],
        )
    )
    write_rows_replace(layout.ens_claimed_path, claimed_records)
    write_rows_replace(layout.ens_cross_registrations_path, cross_records)
    return claimed_records, cross_records


def refresh_claimed_jsonl(
    layout: DataLayout,
    meta: EnsMeta | None = None,
) -> list[dict[str, Any]]:
    claimed, _cross = refresh_registration_jsonl(layout, meta)
    return claimed


def _fetch_one(
    agent_id: int,
    token_uri: str,
    layout: DataLayout,
    *,
    timeout: int,
    force: bool,
    meta: EnsMeta,
) -> RegistrationFetchState:
    agent_key = str(agent_id)
    prior = meta.registration_uris.get(agent_key)
    if (
        not force
        and prior
        and prior.token_uri == token_uri
        and prior.fetch_error is None
        and layout.ens_registration_path(agent_id).is_file()
    ):
        return prior

    fetched_at = _now_iso()
    try:
        registration = load_registration_from_uri(token_uri, timeout=timeout)
        reg_path = layout.ens_registration_path(agent_id)
        reg_path.parent.mkdir(parents=True, exist_ok=True)
        reg_path.write_text(json.dumps(registration, indent=2) + "\n", encoding="utf-8")
        claimed_names = extract_claimed_ens_names(registration)
        return RegistrationFetchState(
            token_uri=token_uri,
            fetched_at=fetched_at,
            claimed_ens_names=claimed_names,
            fetch_error=None,
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return RegistrationFetchState(
            token_uri=token_uri,
            fetched_at=fetched_at,
            claimed_ens_names=[],
            fetch_error=str(exc),
        )


def fetch_registrations(
    layout: DataLayout,
    meta: EnsMeta,
    *,
    force: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    workers: int = DEFAULT_WORKERS,
) -> tuple[int, int, int]:
    """Fetch registration JSON for agents with token_uri. Returns (fetched, failed, skipped)."""
    agents = latest_agents_with_uri(layout)
    if not agents:
        return 0, 0, 0

    fetched = 0
    failed = 0
    skipped = 0

    with ThreadPoolExecutor(max_workers=max(workers, 1)) as pool:
        futures = {
            pool.submit(
                _fetch_one,
                agent_id,
                token_uri,
                layout,
                timeout=timeout,
                force=force,
                meta=meta,
            ): (agent_id, token_uri)
            for agent_id, token_uri in sorted(agents.items())
        }
        for future in as_completed(futures):
            agent_id, token_uri = futures[future]
            agent_key = str(agent_id)
            prior = meta.registration_uris.get(agent_key)
            if (
                not force
                and prior
                and prior.token_uri == token_uri
                and prior.fetch_error is None
                and layout.ens_registration_path(agent_id).is_file()
            ):
                skipped += 1
                state = prior
            else:
                state = future.result()
                meta.registration_uris[agent_key] = state
                if state.fetch_error:
                    failed += 1
                else:
                    fetched += 1

    refresh_registration_jsonl(layout, meta)

    meta.registrations_fetched = sum(
        1
        for state in meta.registration_uris.values()
        if state.fetch_error is None
    )
    meta.registrations_failed = sum(
        1 for state in meta.registration_uris.values() if state.fetch_error
    )
    meta.registrations_skipped = skipped
    meta.save(layout.ens_meta_path)
    return fetched, failed, skipped
