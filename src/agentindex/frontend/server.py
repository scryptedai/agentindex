"""Run the AgentIndex dashboard (FastAPI + static frontend)."""

from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    host = os.environ.get("FRONTEND_HOST", "127.0.0.1")
    port = int(os.environ.get("FRONTEND_PORT", "8787"))
    reload = os.environ.get("FRONTEND_RELOAD", "").lower() in {"1", "true", "yes"}

    uvicorn.run(
        "agentindex.frontend.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
