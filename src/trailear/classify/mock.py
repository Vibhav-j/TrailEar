"""Mock classifier returning deterministic fake detections for testing."""

from __future__ import annotations

from trailear.classify.base import Classifier
from trailear.types import Detection, Window


class MockClassifier(Classifier):
    """Returns a fixed set of fake detections for any input window."""

    _FAKE_SPECIES: tuple[tuple[str, str, float], ...] = (
        ("Turdus merula", "Eurasian Blackbird", 0.92),
        ("Erithacus rubecula", "European Robin", 0.85),
        ("Parus major", "Great Tit", 0.73),
    )

    def classify(self, window: Window) -> list[Detection]:
        """Return deterministic fake detections sorted by confidence descending."""
        return [
            Detection(
                scientific_name=sci,
                common_name=common,
                confidence=conf,
                t=window.t_start,
            )
            for sci, common, conf in self._FAKE_SPECIES
        ]
