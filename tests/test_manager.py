"""Tests for DetectionManager: threshold, consecutive hits, and cooldown logic."""

from __future__ import annotations

from trailear.detect.manager import DetectionManager
from trailear.types import Detection


def _make_det(species: str = "Turdus merula", conf: float = 0.80, t: float = 0.0) -> Detection:
    return Detection(
        scientific_name=species,
        common_name="Eurasian Blackbird" if species == "Turdus merula" else species,
        confidence=conf,
        t=t,
    )


class TestDetectionManager:
    def test_rejects_below_threshold(self):
        manager = DetectionManager(announce_threshold=0.70, min_consecutive=1)
        det_low = _make_det(conf=0.69, t=1.0)
        det_high = _make_det(conf=0.70, t=2.0)

        assert manager.process_detection(det_low) is None
        assert manager.process_detection(det_high) is not None

    def test_requires_min_consecutive_hits(self):
        manager = DetectionManager(
            announce_threshold=0.60,
            min_consecutive=2,
            cooldown_s=120.0,
            span_s=10.0,
        )

        d1 = _make_det(conf=0.80, t=1.0)
        d2 = _make_det(conf=0.85, t=2.0)

        # First hit should not announce
        res1 = manager.process_detection(d1)
        assert res1 is None

        # Second hit within span should announce
        res2 = manager.process_detection(d2)
        assert res2 is not None
        assert res2.scientific_name == "Turdus merula"

    def test_hits_outside_span_do_not_count_as_consecutive(self):
        manager = DetectionManager(
            announce_threshold=0.60,
            min_consecutive=2,
            span_s=5.0,
            cooldown_s=120.0,
        )

        d1 = _make_det(t=1.0)
        d2 = _make_det(t=10.0)  # > 5.0 seconds later
        d3 = _make_det(t=12.0)  # within 5.0 of d2

        assert manager.process_detection(d1) is None
        # d2 is too late to pair with d1, so it starts a new streak
        assert manager.process_detection(d2) is None
        # d3 pairs with d2 -> triggers announcement
        assert manager.process_detection(d3) is not None

    def test_cooldown_suppresses_subsequent_detections(self):
        manager = DetectionManager(
            announce_threshold=0.60,
            min_consecutive=2,
            cooldown_s=60.0,
            span_s=10.0,
        )

        # Trigger initial announcement at t=2.0
        assert manager.process_detection(_make_det(t=1.0)) is None
        assert manager.process_detection(_make_det(t=2.0)) is not None

        # Detections during cooldown (up to t=62.0) must be suppressed
        for t in [3.0, 10.0, 30.0, 61.9]:
            assert manager.process_detection(_make_det(t=t)) is None

        # After cooldown (t >= 62.0), new consecutive hits are required
        assert manager.process_detection(_make_det(t=65.0)) is None  # Hit 1
        assert manager.process_detection(_make_det(t=66.0)) is not None  # Hit 2 -> announced

    def test_deterministic_clock_injection(self):
        fake_time = 100.0

        def fake_clock() -> float:
            return fake_time

        manager = DetectionManager(
            announce_threshold=0.60,
            min_consecutive=2,
            cooldown_s=50.0,
            clock=fake_clock,
        )

        d = _make_det(t=0.0)  # Window timestamp ignored when clock is injected
        assert manager.process_detection(d) is None

        fake_time = 102.0
        announced = manager.process_detection(d)
        assert announced is not None

        # Cooldown check via clock
        fake_time = 130.0
        assert manager.process_detection(d) is None

        # After cooldown
        fake_time = 160.0
        assert manager.process_detection(d) is None  # Hit 1
        fake_time = 161.0
        assert manager.process_detection(d) is not None  # Hit 2

    def test_multiple_species_are_independent(self):
        manager = DetectionManager(announce_threshold=0.60, min_consecutive=2)

        sp_a1 = _make_det(species="Turdus merula", t=1.0)
        sp_b1 = _make_det(species="Erithacus rubecula", t=1.5)
        sp_a2 = _make_det(species="Turdus merula", t=2.0)
        sp_b2 = _make_det(species="Erithacus rubecula", t=2.5)

        assert manager.process_detection(sp_a1) is None
        assert manager.process_detection(sp_b1) is None

        # 2nd hit for species A
        ann_a = manager.process_detection(sp_a2)
        assert ann_a is not None
        assert ann_a.scientific_name == "Turdus merula"

        # 2nd hit for species B
        ann_b = manager.process_detection(sp_b2)
        assert ann_b is not None
        assert ann_b.scientific_name == "Erithacus rubecula"

    def test_reset(self):
        manager = DetectionManager(announce_threshold=0.60, min_consecutive=2)
        assert manager.process_detection(_make_det(t=1.0)) is None
        manager.reset()
        # After reset, the previous hit is cleared so a single hit won't trigger
        assert manager.process_detection(_make_det(t=2.0)) is None
