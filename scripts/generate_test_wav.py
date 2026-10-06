"""Generate a short synthetic WAV file for testing."""

import wave
from pathlib import Path

import numpy as np


def generate_test_wav(path: Path, duration_s: float = 5.0, sample_rate: int = 48000) -> None:
    """Generate a WAV file with a sine wave for testing."""
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
    # Mix of bird-like frequencies
    samples = 0.3 * np.sin(2 * np.pi * 2000 * t) + 0.2 * np.sin(2 * np.pi * 4000 * t)
    samples = (samples * 32767).astype(np.int16)

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    print(f"Created {path} ({duration_s}s, {sample_rate} Hz)")


if __name__ == "__main__":
    generate_test_wav(
        Path(__file__).resolve().parent.parent / "data" / "samples" / "test_tone.wav"
    )
