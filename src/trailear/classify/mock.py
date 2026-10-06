"""Mock classifier returning deterministic fake detections for testing."""

from __future__ import annotations

from trailear.classify.base import Classifier
from trailear.config import config
from trailear.types import Detection, Window


class MockClassifier(Classifier):
    """Returns a fixed set of fake detections for any input window."""

    _FAKE_SPECIES: tuple[tuple[str, str, float], ...] = (
        ("Turdus merula", "Eurasian Blackbird", 0.92),
        ("Erithacus rubecula", "European Robin", 0.85),
        ("Parus major", "Great Tit", 0.73),
    )

    def __init__(
        self,
        min_confidence: float | None = None,
        verbose: bool = False,
    ) -> None:
        self._min_confidence = (
            min_confidence if min_confidence is not None else config.classifier.min_confidence
        )
        self._verbose = verbose

    def classify(self, window: Window) -> list[Detection]:
        """Return deterministic fake detections sorted by confidence descending."""
        if self._verbose:
            if self._FAKE_SPECIES:
                _top_sci, top_common, top_conf = self._FAKE_SPECIES[0]
                if top_conf < self._min_confidence:
                    status = f"Discarded: Confidence {top_conf:.2f} < {self._min_confidence:.2f}"
                else:
                    status = "Accepted"
            else:
                top_common = "None"
                top_conf = 0.0
                status = f"Discarded: Confidence 0.00 < {self._min_confidence:.2f}"

            print(
                f"  [RAW] t={window.t_start:.1f}s | Top: {top_common} | "
                f"Confidence: {top_conf:.2f} | {status}"
            )

        return [
            Detection(
                scientific_name=sci,
                common_name=common,
                confidence=conf,
                t=window.t_start,
            )
            for sci, common, conf in self._FAKE_SPECIES
            if conf >= self._min_confidence
        ]
