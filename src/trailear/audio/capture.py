"""Audio sources: MicSource (live) and FileSource (WAV file)."""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Generator
from pathlib import Path

import numpy as np
import soundfile as sf

from trailear.config import config
from trailear.types import Window

logger = logging.getLogger(__name__)


def _resample_mono(samples: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Convert to mono and resample to target_sr using linear interpolation."""
    # Ensure mono
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    # Resample if needed
    if orig_sr != target_sr:
        duration = len(samples) / orig_sr
        target_len = int(duration * target_sr)
        indices = np.linspace(0, len(samples) - 1, target_len)
        samples = np.interp(indices, np.arange(len(samples)), samples)
    return samples.astype(np.float32)


class FileSource:
    """Reads a WAV file and yields 3 s windows with 1 s hop, resampled to 48 kHz mono."""

    def __init__(
        self,
        path: Path | str,
        sample_rate: int = 48000,
        window_s: float = 3.0,
        hop_s: float = 1.0,
    ) -> None:
        self.path = Path(path)
        self.sample_rate = sample_rate
        self.window_s = window_s
        self.hop_s = hop_s

    def windows(self) -> Generator[Window, None, None]:
        """Yield overlapping windows from the WAV file."""
        data, orig_sr = sf.read(str(self.path), dtype="float32")
        samples = _resample_mono(data, orig_sr, self.sample_rate)

        window_len = int(self.window_s * self.sample_rate)
        hop_len = int(self.hop_s * self.sample_rate)
        total = len(samples)

        offset = 0
        while offset + window_len <= total:
            chunk = samples[offset : offset + window_len]
            t_start = offset / self.sample_rate
            yield Window(samples=chunk, sample_rate=self.sample_rate, t_start=t_start)
            offset += hop_len


class MicSource:
    """Live microphone capture using sounddevice.

    Yields 3 s windows with 1 s hop at 48 kHz mono.
    Device is selectable from config.audio.device or explicit argument.
    """

    def __init__(
        self,
        device: int | None = None,
        sample_rate: int | None = None,
        window_s: float | None = None,
        hop_s: float | None = None,
    ) -> None:
        self.device = device if device is not None else config.audio.device
        self.sample_rate = sample_rate if sample_rate is not None else config.audio.sample_rate
        self.window_s = window_s if window_s is not None else config.audio.window_s
        self.hop_s = hop_s if hop_s is not None else config.audio.hop_s
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """Signal the capture loop to stop."""
        self._stop_event.set()

    def windows(self) -> Generator[Window, None, None]:
        """Yield overlapping audio windows from the live microphone stream."""
        import sounddevice as sd

        self._stop_event.clear()
        audio_q: queue.Queue[np.ndarray | None] = queue.Queue()

        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.warning("Audio input status flag: %s", status)
            audio_q.put(indata.copy())

        try:
            stream = sd.InputStream(
                device=self.device,
                channels=1,
                samplerate=self.sample_rate,
                dtype="float32",
                callback=audio_callback,
            )
        except Exception as err:
            dev_str = f"index {self.device}" if self.device is not None else "system default"
            msg = (
                f"Failed to open audio input device ({dev_str}): {err}. "
                "Check audio.device in config.yaml or run 'python -m trailear devices' to list valid devices."
            )
            logger.error(msg)
            raise RuntimeError(msg) from err

        window_len = int(self.window_s * self.sample_rate)
        hop_len = int(self.hop_s * self.sample_rate)
        buffer = np.zeros(0, dtype=np.float32)
        t_start = 0.0

        with stream:
            while not self._stop_event.is_set():
                try:
                    chunk = audio_q.get(timeout=0.2)
                except queue.Empty:
                    continue
                if chunk is None:
                    break

                mono_chunk = chunk.squeeze()
                if mono_chunk.ndim > 1:
                    mono_chunk = mono_chunk.mean(axis=1)
                buffer = np.concatenate([buffer, mono_chunk])

                while len(buffer) >= window_len:
                    window_samples = buffer[:window_len]
                    yield Window(
                        samples=window_samples,
                        sample_rate=self.sample_rate,
                        t_start=t_start,
                    )
                    buffer = buffer[hop_len:]
                    t_start += self.hop_s


def list_devices() -> list[dict]:
    """List available audio input devices."""
    import sounddevice as sd

    devices = sd.query_devices()
    result = []
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            result.append(
                {
                    "index": i,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "sample_rate": dev["default_samplerate"],
                }
            )
    return result
