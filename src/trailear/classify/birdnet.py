"""BirdNET classifier backend using birdnetlib."""

from __future__ import annotations

import datetime
import tempfile
import wave
from pathlib import Path
from typing import TYPE_CHECKING, Any

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

    def __init__(
        self,
        min_confidence: float | None = None,
        verbose: bool = False,
    ) -> None:
        self._analyzer: Analyzer | None = None
        self._custom_min_confidence = min_confidence
        self._verbose = verbose

    @property
    def min_confidence(self) -> float:
        if self._custom_min_confidence is not None:
            return self._custom_min_confidence
        return config.classifier.min_confidence

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

            now = datetime.datetime.now(datetime.UTC)

            recording_kwargs: dict[str, Any] = {
                "min_conf": 0.0 if self._verbose else self.min_confidence,
                "return_all_detections": bool(self._verbose),
            }
            if config.classifier.use_location_filter:
                recording_kwargs["lat"] = config.location.lat
                recording_kwargs["lon"] = config.location.lon
                recording_kwargs["date"] = now

            recording = Recording(
                analyzer,
                str(tmp_path),
                **recording_kwargs,
            )
            recording.analyze()

            raw_detections = recording.detections

            if self._verbose:
                if raw_detections:
                    raw_sorted = sorted(
                        raw_detections,
                        key=lambda d: float(d.get("confidence", 0.0)),
                        reverse=True,
                    )
                    top = raw_sorted[0]
                    top_name = top.get("common_name") or top.get("scientific_name") or "Unknown"
                    top_conf = float(top.get("confidence", 0.0))
                    is_regional = top.get("is_predicted_for_location_and_date", True)

                    if top_conf < self.min_confidence:
                        status = (
                            f"Discarded: Confidence {top_conf:.2f} < {self.min_confidence:.2f}"
                        )
                    elif config.classifier.use_location_filter and not is_regional:
                        status = "Discarded: Not in regional filter"
                    else:
                        status = "Accepted"
                else:
                    top_name = "None"
                    top_conf = 0.0
                    status = f"Discarded: Confidence 0.00 < {self.min_confidence:.2f}"

                print(
                    f"  [RAW] t={window.t_start:.1f}s | Top: {top_name} | "
                    f"Confidence: {top_conf:.2f} | Status: {status}"
                )

                accepted = [
                    d
                    for d in raw_detections
                    if float(d.get("confidence", 0.0)) >= self.min_confidence
                    and (
                        not config.classifier.use_location_filter
                        or d.get("is_predicted_for_location_and_date", True)
                    )
                ]
            else:
                accepted = raw_detections

            detections = [
                Detection(
                    scientific_name=d["scientific_name"],
                    common_name=d["common_name"],
                    confidence=float(d["confidence"]),
                    t=window.t_start,
                )
                for d in accepted
            ]
            # Sort by confidence descending
            detections.sort(key=lambda x: x.confidence, reverse=True)
            return detections
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
