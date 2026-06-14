"""ENS backfill: BigQuery discovery + registration JSON fetch."""

from __future__ import annotations

from agentindex.bq.client import BigQueryRunner
from agentindex.config.models import NetworkConfig
from agentindex.config.settings import Settings
from agentindex.ens.discovery import discover_verified_agents
from agentindex.ens.registrations import fetch_registrations
from agentindex.index.ens_sources import read_jsonl
from agentindex.storage.ens_meta import EnsMeta
from agentindex.storage.paths import DataLayout


def backfill_ens_network(settings: Settings, network: NetworkConfig) -> None:
    if not network.ens_enabled:
        print(f"ENS disabled for {network.key}; skip")
        return

    layout = DataLayout(settings.data_dir, network=network.key)
    layout.ensure_ens()
    meta = EnsMeta.load(layout.ens_meta_path)
    ens = network.ens
    assert ens is not None

    print(f"ENS backfill ({network.key}, chain_id={network.chain_id})")
    print(f"Data dir: {layout.ens_dir}")
    print()

    print("Phase 1/2: BigQuery ENSIP-25 discovery")
    runner = BigQueryRunner(settings.max_bytes_billed)
    verified, billed = discover_verified_agents(runner, layout, meta, ens)
    print(f"  verified links: {verified:,} ({billed:,} bytes billed)")
    print(f"  -> {layout.ens_verified_path}")
    print()

    print("Phase 2/2: fetch registration JSON from token_uri")
    fetch = network.registration_fetch
    fetched, failed, skipped = fetch_registrations(
        layout,
        meta,
        force=True,
        timeout=fetch.timeout_seconds,
        workers=fetch.workers,
    )
    claimed = len(read_jsonl(layout.ens_claimed_path))
    cross = len(read_jsonl(layout.ens_cross_registrations_path))
    print(
        f"  registrations: {fetched:,} fetched, {failed:,} failed, "
        f"{skipped:,} skipped"
    )
    print(f"  claimed ENS names: {claimed:,}")
    print(f"  cross-network registrations: {cross:,}")
    print(f"  -> {layout.ens_claimed_path}")
    print(f"Meta: {layout.ens_meta_path}")
    print()
    print("Run `poetry run agentindex-build` to merge ENS data into SQLite.")


def backfill_ens_all(settings: Settings | None = None) -> None:
    settings = settings or Settings.load()
    for network in settings.config.enabled_networks():
        backfill_ens_network(settings, network)
        print()


def backfill_ens(settings: Settings | None = None) -> None:
    settings = settings or Settings.load()
    backfill_ens_network(settings, settings.network())
