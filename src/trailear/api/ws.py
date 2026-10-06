"""WebSocket connection management and live detection broadcaster."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import WebSocket

    from trailear.types import Detection

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts detections safely across threads."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the running asyncio event loop."""
        self._loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        with self._lock:
            self.active_connections.append(websocket)
        logger.info("WebSocket client connected. Active: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket."""
        with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info("WebSocket client disconnected. Active: %d", len(self.active_connections))

    async def broadcast_json(self, data: dict) -> None:
        """Broadcast a JSON message to all active WebSocket clients."""
        with self._lock:
            targets = list(self.active_connections)

        for ws in targets:
            try:
                await ws.send_json(data)
            except Exception:  # noqa: BLE001
                self.disconnect(ws)

    def broadcast_from_thread(self, data: dict) -> None:
        """Thread-safe dispatch of a broadcast from background worker threads."""
        if self._loop is not None and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast_json(data), self._loop)


# Module-level singleton manager
ws_manager = ConnectionManager()


def make_ws_sink(manager: ConnectionManager | None = None) -> Callable[[Detection], None]:
    """Create a sink callable that broadcasts detection events to WebSockets."""
    mgr = manager or ws_manager

    def _ws_sink(d: Detection) -> None:
        payload = {
            "type": "detection",
            "common_name": d.common_name,
            "scientific_name": d.scientific_name,
            "confidence": round(d.confidence, 2),
            "t": round(d.t, 1),
        }
        mgr.broadcast_from_thread(payload)

    return _ws_sink
