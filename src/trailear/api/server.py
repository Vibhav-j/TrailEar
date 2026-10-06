"""FastAPI application factory and server entry point."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from trailear.api.routes import router
from trailear.api.ws import ws_manager
from trailear.config import config

_WEB_DIR = Path(__file__).resolve().parent.parent.parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown lifecycle events."""
    loop = asyncio.get_running_loop()
    ws_manager.set_loop(loop)
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="TrailEar",
        description="Offline bird-call companion API & PWA",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Include REST & WebSocket routes
    app.include_router(router)

    # Mount static assets for PWA at root
    if _WEB_DIR.exists():
        app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")

    return app


# Application singleton for uvicorn
app = create_app()


def run_server(host: str | None = None, port: int | None = None) -> None:
    """Start uvicorn server serving API and static PWA."""
    import uvicorn

    bind_host = host or config.server.host
    bind_port = port or config.server.port
    print(f"Starting TrailEar server on http://{bind_host}:{bind_port}...")
    uvicorn.run(app, host=bind_host, port=bind_port)
