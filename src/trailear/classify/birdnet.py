"""BirdNET classifier backend using birdnetlib."""

from __future__ import annotations

import datetime
import tempfile
import wave
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from trailear.classify.base import Classifier
from trailear.config import config
from trailear.types import Detection, Window

if TYPE_CHECKING:
    from birdnetlib.analyzer import Analyzer


def is_available() -> bool:
    """Check if birdnetlib is installed and importable."""
    try:
        from birdnetlib.analyzer import Analyzer  # noqa: F401

        return True
    except (ImportError, ModuleNotFoundError):
        return False


class BirdNETClassifier(Classifier):
    """Wraps birdnetlib for bird species classification.

    Loads the BirdNET model once on first use. Passes lat/lon and week-of-year
    from config for species filtering. Only returns detections at or above
    min_confidence.
    """

    def __init__(self, min_confidence: float | None = None) -> None:
        self._analyzer: Analyzer | None = None
        self._min_confidence = min_confidence or config.classifier.min_confidence

    def _get_analyzer(self) -> Analyzer:
        if self._analyzer is None:
            from birdnetlib.analyzer import Analyzer  # lazy import

            self._analyzer = Analyzer()
        return self._analyzer

    def classify(self, window: Window) -> list[Detection]:
        """Classify an audio window using BirdNET."""
        from birdnetlib import Recording  # lazy import

        analyzer = self._get_analyzer()

        # Write window to a temporary WAV file (birdnetlib requires a file path)
        tmp_path = Path(tempfile.mktemp(suffix=".wav"))
        try:
            with wave.open(str(tmp_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(window.sample_rate)
                # Convert float32 [-1,1] to int16
                pcm = (window.samples * 32767).astype(np.int16)
                wf.writeframes(pcm.tobytes())

            from trailear.classify.location_filter import date_to_birdnet_week

            now = datetime.datetime.now(datetime.UTC)
            week = date_to_birdnet_week(now)

            recording_kwargs = {
                "min_conf": self._min_confidence,
            }
            if config.classifier.use_location_filter:
                recording_kwargs["lat"] = config.location.lat
                recording_kwargs["lon"] = config.location.lon
                recording_kwargs["week"] = week

            recording = Recording(
                analyzer,
                str(tmp_path),
                **recording_kwargs,
            )
            recording.analyze()

            detections = [
                Detection(
                    scientific_name=d["scientific_name"],
                    common_name=d["common_name"],
                    confidence=d["confidence"],
                    t=window.t_start,
                )
                for d in recording.detections
            ]
            # Sort by confidence descending
            detections.sort(key=lambda x: x.confidence, reverse=True)
            return detections
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
