"""REST API and WebSocket route handlers for TrailEar."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from trailear.api.ws import make_ws_sink, ws_manager
from trailear.config import config
from trailear.detect.manager import DetectionManager
from trailear.pipeline import Pipeline, make_storage_sink, make_tts_sink
from trailear.storage.db import (
    end_walk,
    get_walk,
    life_list,
    list_walks,
    start_walk,
)
from trailear.types import Window

logger = logging.getLogger(__name__)

router = APIRouter()

# Global state for background walk session
_session_lock = threading.Lock()
_active_walk_id: int | None = None
_active_pipeline: Pipeline | None = None


class _SyntheticQuietSource:
    """Fallback source when no microphone is present, emitting quiet frames."""

    def __init__(self, sample_rate: int = 48000, hop_s: float = 1.0) -> None:
        self.sample_rate = sample_rate
        self.hop_s = hop_s
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def windows(self):
        import time

        import numpy as np

        samples = np.zeros(int(self.sample_rate * 3.0), dtype=np.float32)
        t = 0.0
        while not self._stop_event.is_set():
            yield Window(samples=samples, sample_rate=self.sample_rate, t_start=t)
            t += self.hop_s
            time.sleep(self.hop_s)


def _get_api_audio_source():
    """Attempt to create MicSource, falling back to FileSource or Synthetic."""
    try:
        from trailear.audio.capture import MicSource

        return MicSource(device=config.audio.device)
    except Exception as exc:  # noqa: BLE001
        sample_file = Path("data/samples/sample.wav")
        if sample_file.exists():
            from trailear.audio.capture import FileSource

            logger.info("MicSource failed (%s); using sample file", exc)
            return FileSource(sample_file)
        logger.info("MicSource failed (%s); using quiet synthetic stream", exc)
        return _SyntheticQuietSource()


@router.post("/api/walks/start")
def api_start_walk() -> dict:
    """Start a new walk session and begin live processing."""
    global _active_pipeline, _active_walk_id

    with _session_lock:
        if _active_pipeline is not None and _active_walk_id is not None:
            return {
                "walk_id": _active_walk_id,
                "status": "already_running",
            }

        from trailear.main import _get_classifier
        from trailear.voice.tts import get_tts

        walk_id = start_walk(lat=config.location.lat, lon=config.location.lon)
        source = _get_api_audio_source()
        classifier = _get_classifier()
        tts = get_tts()

        storage_sink = make_storage_sink(walk_id)
        websocket_sink = make_ws_sink(ws_manager)
        tts_sink = make_tts_sink(
            tts,
            speak_only_new_species=config.pocket_mode.speak_only_new_species,
            chime_on_rare=config.pocket_mode.chime_on_rare,
        )

        pipeline = Pipeline(
            source=source,
            classifier=classifier,
            manager=DetectionManager(),
            sinks=[storage_sink, websocket_sink, tts_sink],
        )
        pipeline.start()

        _active_walk_id = walk_id
        _active_pipeline = pipeline

        return {
            "walk_id": walk_id,
            "status": "started",
        }


@router.post("/api/walks/{walk_id}/stop")
def api_stop_walk(walk_id: int) -> dict:
    """Stop an active walk, trigger journal generation, and return walk details."""
    global _active_pipeline, _active_walk_id

    with _session_lock:
        if _active_pipeline is not None and _active_walk_id == walk_id:
            _active_pipeline.stop()
            _active_pipeline = None
            _active_walk_id = None

    end_walk(walk_id)

    # Generate journal
    from trailear.llm.journal import generate_and_save_journal

    try:
        generate_and_save_journal(walk_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Journal generation error on stop: %s", exc)

    walk = get_walk(walk_id)
    if walk is None:
        raise HTTPException(status_code=404, detail=f"Walk #{walk_id} not found")

    return walk.to_dict()


@router.get("/api/walks")
def api_list_walks() -> list[dict]:
    """List all recorded walks."""
    return list_walks()


@router.get("/api/walks/{walk_id}")
def api_get_walk(walk_id: int) -> dict:
    """Get full details of a specific walk including sightings and journal."""
    walk = get_walk(walk_id)
    if walk is None:
        raise HTTPException(status_code=404, detail=f"Walk #{walk_id} not found")
    return walk.to_dict()


@router.get("/api/lifelist")
def api_lifelist() -> list[dict]:
    """Retrieve all species ever detected with first-seen timestamp and count."""
    return life_list()


@router.get("/api/health")
def api_health() -> dict:
    """Check health and availability of classifier, LLM, and TTS engines."""
    from trailear.classify.birdnet import is_available as is_birdnet_available
    from trailear.llm.ollama_client import OllamaClient

    # Classifier status
    if config.classifier.backend == "mock":
        classifier_status = {"backend": "mock", "available": True}
    else:
        classifier_status = {
            "backend": "birdnet",
            "available": is_birdnet_available(),
        }

    # LLM status
    if config.llm.backend == "mock":
        llm_status = {"backend": "mock", "available": True}
    else:
        ollama = OllamaClient()
        llm_status = {
            "backend": "ollama",
            "available": ollama.is_available(),
        }

    # TTS status
    tts_status = {
        "enabled": config.tts.enabled,
        "voice": config.tts.voice,
    }

    return {
        "status": "ok",
        "classifier": classifier_status,
        "llm": llm_status,
        "tts": tts_status,
    }


@router.websocket("/ws/live")
async def websocket_live_feed(websocket: WebSocket) -> None:
    """WebSocket endpoint pushing real-time detection events."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep-alive receive loop
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:  # noqa: BLE001
        ws_manager.disconnect(websocket)
