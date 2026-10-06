"""Detection manager: threshold filtering, debounce, and cooldown deduplication."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING

from trailear.config import config

if TYPE_CHECKING:
    from trailear.types import Detection


class DetectionManager:
    """Filters raw classifier detections and emits events for new announcements.

    Behavior:
    1. Rejects detections with confidence < announce_threshold.
    2. Rejects detections during cooldown_s after a prior announcement for that species.
    3. Requires at least min_consecutive hits within span_s before announcing.
    4. Emits an event (returns the Detection) only for NEW announcements.
    5. Pure and deterministic: an optional clock callable or explicit timestamp can be injected.
    """

    def __init__(
        self,
        announce_threshold: float | None = None,
        min_consecutive: int | None = None,
        cooldown_s: float | None = None,
        span_s: float = 10.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.announce_threshold = (
            announce_threshold
            if announce_threshold is not None
            else config.detect.announce_threshold
        )
        self.min_consecutive = (
            min_consecutive if min_consecutive is not None else config.detect.min_consecutive
        )
        self.cooldown_s = cooldown_s if cooldown_s is not None else float(config.detect.cooldown_s)
        self.span_s = span_s
        self.clock = clock

        # State: species -> list of hit timestamps within span_s
        self._recent_hits: dict[str, list[float]] = defaultdict(list)
        # State: species -> timestamp of last announcement
        self._last_announced: dict[str, float] = {}

    def _get_time(self, detection: Detection, t: float | None = None) -> float:
        if t is not None:
            return t
        if self.clock is not None:
            return self.clock()
        return detection.t

    def process_detection(self, detection: Detection, t: float | None = None) -> Detection | None:
        """Process a single detection.

        Returns the Detection if it qualifies as a NEW announcement, or None otherwise.
        """
        if detection.confidence < self.announce_threshold:
            return None

        curr_t = self._get_time(detection, t)
        species = detection.scientific_name

        # Cooldown check: if already announced within cooldown_s, suppress
        if species in self._last_announced:
            elapsed = curr_t - self._last_announced[species]
            if elapsed < self.cooldown_s:
                return None

        # Filter recent hits to those within span_s
        hits = [
            ts
            for ts in self._recent_hits[species]
            if (curr_t - ts) <= self.span_s and ts <= curr_t
        ]
        hits.append(curr_t)
        self._recent_hits[species] = hits

        # Check if we have reached required consecutive hits
        if len(hits) >= self.min_consecutive:
            self._last_announced[species] = curr_t
            self._recent_hits[species] = []  # Clear history after successful announcement
            return detection

        return None

    def process_window(
        self, detections: list[Detection], t: float | None = None
    ) -> list[Detection]:
        """Process all detections from a window, returning new announcements."""
        announced: list[Detection] = []
        for d in detections:
            res = self.process_detection(d, t=t)
            if res is not None:
                announced.append(res)
        return announced

    def reset(self) -> None:
        """Reset internal state (e.g., between walks)."""
        self._recent_hits.clear()
        self._last_announced.clear()
