"""FastAPI routes for the AgentIndex dashboard."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from agentindex.config.settings import IndexSettings
from agentindex.frontend.analytics import (
    build_indexes,
    build_payload,
    derive_agent,
    dossier_callouts,
)
from agentindex.frontend.networks import build_network_meta
from agentindex.frontend.corpus import (
    agent_agg,
    agent_cross,
    agent_ens,
    agent_feedback,
    agent_row,
    load_ingest_meta,
    load_raw_bundle,
    open_corpus,
)

FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"


def _load_corpus_bundle(conn, settings: IndexSettings) -> dict[str, Any]:
    network = settings.config.network()
    ingest_meta = load_ingest_meta(settings)
    return load_raw_bundle(
        conn,
        home_chain_id=network.chain_id,
        ingest_meta=ingest_meta,
    )


@lru_cache(maxsize=1)
def _bootstrap_cache() -> dict[str, Any]:
    settings = IndexSettings.load()
    conn, paths = open_corpus(settings)
    try:
        raw = _load_corpus_bundle(conn, settings)
        payload = build_payload(
            raw,
            schema_version=paths.schema_version,
            db_path=str(paths.db_path),
            config=settings.config,
        )
        payload["meta"]["network"] = build_network_meta(settings.config)
        return payload
    finally:
        conn.close()


def create_app() -> FastAPI:
    app = FastAPI(title="AgentIndex", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/bootstrap")
    def bootstrap() -> dict[str, Any]:
        try:
            return _bootstrap_cache()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/reload")
    def reload() -> dict[str, str]:
        _bootstrap_cache.cache_clear()
        _bootstrap_cache()
        return {"status": "reloaded"}

    @app.get("/api/agents/{agent_id}")
    def agent_detail(agent_id: int) -> dict[str, Any]:
        conn, _ = open_corpus()
        try:
            agent = agent_row(conn, agent_id)
            if agent is None:
                raise HTTPException(status_code=404, detail="Agent not found")
            entry = {
                "agent": agent,
                "reputation_agg": agent_agg(conn, agent_id),
                "ens_links": agent_ens(conn, agent_id),
                "cross_registrations": agent_cross(conn, agent_id),
                "feedback_events": agent_feedback(conn, agent_id),
            }
            raw = _load_corpus_bundle(conn, IndexSettings.load())
            indexes = build_indexes(raw)
            derived = derive_agent(entry, indexes)
            return {
                "entry": entry,
                "derived": derived,
                "callouts": dossier_callouts(derived),
            }
        finally:
            conn.close()

    @app.get("/api/search")
    def search(q: str = Query("", min_length=0)) -> list[dict[str, Any]]:
        payload = _bootstrap_cache()
        query = q.strip().lower()
        if not query:
            return payload["derived"]["explorerIndex"][:50]
        return [
            row
            for row in payload["derived"]["explorerIndex"]
            if query in str(row["id"])
            or (row.get("name") or "").lower().find(query) >= 0
            or (row.get("owner") or "").lower().find(query) >= 0
            or any(query in ens.lower() for ens in row.get("ens") or [])
        ][:100]

    if FRONTEND_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")

    return app


app = create_app()
