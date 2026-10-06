"""Audio sources: MicSource (live) and FileSource (WAV file)."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import numpy as np
import soundfile as sf

from trailear.types import Window


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

    Full implementation deferred to Phase 3.
    """

    def __init__(
        self,
        device: int | None = None,
        sample_rate: int = 48000,
        window_s: float = 3.0,
        hop_s: float = 1.0,
    ) -> None:
        self.device = device
        self.sample_rate = sample_rate
        self.window_s = window_s
        self.hop_s = hop_s

    def windows(self) -> Generator[Window, None, None]:
        """Yield overlapping windows from the microphone."""
        raise NotImplementedError("MicSource will be implemented in Phase 3")


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
