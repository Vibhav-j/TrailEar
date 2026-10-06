"""Text-to-speech module using Piper TTS with NullTTS fallback."""

from __future__ import annotations

import io
import logging
import queue
import threading
import wave
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from trailear.config import config

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_MODELS_DIR = _PROJECT_ROOT / "models"


def generate_chime(sample_rate: int = 44100, duration_s: float = 0.3) -> np.ndarray:
    """Generate a pleasant two-tone chime using pure numpy (no audio files)."""
    half = duration_s / 2
    n_samples = int(sample_rate * half)
    t = np.linspace(0, half, n_samples, endpoint=False, dtype=np.float32)
    envelope = np.exp(-7 * t / half)
    # A5 (880 Hz) followed by E6 (1320 Hz)
    tone1 = 0.25 * np.sin(2 * np.pi * 880 * t) * envelope
    tone2 = 0.25 * np.sin(2 * np.pi * 1320 * t) * envelope
    return np.concatenate([tone1, tone2]).astype(np.float32)


class TTS(ABC):
    """Abstract interface for speech synthesis."""

    @abstractmethod
    def speak(self, text: str) -> None:
        """Queue text to be spoken non-blockingly."""
        ...

    def play_chime(self) -> None:
        """Play a short chime (default: no-op)."""

    def stop(self) -> None:
        """Cleanly stop worker threads."""


class NullTTS(TTS):
    """No-op TTS used when TTS is disabled or unavailable."""

    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.chimes_played: int = 0

    def speak(self, text: str) -> None:
        self.spoken.append(text)
        logger.debug("[NullTTS] Spoke: %s", text)

    def play_chime(self) -> None:
        self.chimes_played += 1
        logger.debug("[NullTTS] Chime played")

    def stop(self) -> None:
        pass


class PiperTTS(TTS):
    """Offline Piper TTS engine playing through sounddevice on a dedicated thread."""

    def __init__(
        self,
        voice_name: str | None = None,
        model_path: Path | None = None,
    ) -> None:
        voice = voice_name or config.tts.voice
        self.model_path = model_path or self._resolve_model_path(voice)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Piper model not found at {self.model_path}")

        # Lazy import of piper
        try:
            from piper import PiperVoice  # type: ignore[import-untyped]
        except ImportError as err:
            raise ImportError(
                "piper-tts is not installed. Install with 'pip install -e .[ml]'"
            ) from err

        config_path = self.model_path.with_suffix(".onnx.json")
        self._voice = PiperVoice.load(
            str(self.model_path),
            config_path=str(config_path) if config_path.exists() else None,
        )

        # Worker thread and queue
        self._queue: queue.Queue[Callable[[], None] | None] = queue.Queue(maxsize=10)
        self._stop_event = threading.Event()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="PiperTTSWorker",
            daemon=True,
        )
        self._worker_thread.start()

    @staticmethod
    def _resolve_model_path(voice_name: str) -> Path:
        """Find the .onnx model in models/ or models/piper/."""
        candidates = [
            _MODELS_DIR / f"{voice_name}.onnx",
            _MODELS_DIR / "piper" / f"{voice_name}.onnx",
        ]
        for p in candidates:
            if p.exists():
                return p
        return candidates[1]  # Default expected location

    def _worker_loop(self) -> None:
        """Dedicated audio playback thread."""

        while not self._stop_event.is_set():
            try:
                task = self._queue.get()
                if task is None:
                    break
                task()
            except Exception:
                logger.exception("Error during TTS playback")

    def speak(self, text: str) -> None:
        """Queue text to be synthesized and spoken non-blockingly."""
        import sounddevice as sd

        def _synthesize_and_play() -> None:
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wav_file:
                self._voice.synthesize(text, wav_file)
            buf.seek(0)
            with wave.open(buf, "rb") as wf:
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                data = wf.readframes(n_frames)
                samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32767.0
            sd.play(samples, samplerate=sample_rate)
            sd.wait()

        # Drop stale queued speech if queue grows beyond 3 items
        while self._queue.qsize() >= 3:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        try:
            self._queue.put_nowait(_synthesize_and_play)
        except queue.Full:
            logger.warning("TTS queue full; dropping speech: '%s'", text)

    def play_chime(self) -> None:
        """Queue a short chime non-blockingly."""
        import sounddevice as sd

        def _play_chime() -> None:
            chime = generate_chime(sample_rate=44100, duration_s=0.25)
            sd.play(chime, samplerate=44100)
            sd.wait()

        try:
            self._queue.put_nowait(_play_chime)
        except queue.Full:
            pass

    def stop(self) -> None:
        """Stop worker thread and wait for completion."""
        self._stop_event.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)


_LOAD_WARNING_PRINTED = False


def get_tts() -> TTS:
    """Factory function returning a configured TTS instance, degrading to NullTTS on error."""
    global _LOAD_WARNING_PRINTED

    if not config.tts.enabled:
        return NullTTS()

    try:
        return PiperTTS()
    except Exception as exc:  # noqa: BLE001
        if not _LOAD_WARNING_PRINTED:
            logger.debug("Piper TTS unavailable (%s). Degrading to NullTTS.", exc)
            print(f"[INFO] Piper TTS unavailable ({exc}). Spoken audio disabled.")
            _LOAD_WARNING_PRINTED = True
        return NullTTS()
