"""Tests for classifiers: MockClassifier and BirdNET (if available)."""

from __future__ import annotations

import numpy as np
import pytest

from trailear.classify.mock import MockClassifier
from trailear.types import Window


def _make_window(t_start: float = 0.0) -> Window:
    """Create a synthetic audio window for testing."""
    sr = 48000
    duration = 3.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
    # Generate a simple sine wave (440 Hz)
    samples = 0.5 * np.sin(2 * np.pi * 440 * t)
    return Window(samples=samples, sample_rate=sr, t_start=t_start)


class TestMockClassifier:
    def test_returns_detections(self):
        clf = MockClassifier()
        window = _make_window()
        results = clf.classify(window)
        assert len(results) > 0

    def test_sorted_by_confidence_desc(self):
        clf = MockClassifier()
        window = _make_window()
        results = clf.classify(window)
        confidences = [d.confidence for d in results]
        assert confidences == sorted(confidences, reverse=True)

    def test_detections_have_correct_time(self):
        clf = MockClassifier()
        window = _make_window(t_start=5.0)
        results = clf.classify(window)
        for d in results:
            assert d.t == 5.0

    def test_deterministic(self):
        clf = MockClassifier()
        w1 = _make_window()
        w2 = _make_window()
        r1 = clf.classify(w1)
        r2 = clf.classify(w2)
        assert len(r1) == len(r2)
        for a, b in zip(r1, r2):
            assert a.scientific_name == b.scientific_name
            assert a.common_name == b.common_name
            assert a.confidence == b.confidence


class TestBirdNETClassifier:
    @pytest.fixture(autouse=True)
    def _check_birdnet(self):
        try:
            from birdnetlib.analyzer import Analyzer  # noqa
        except ImportError:
            pytest.skip("birdnetlib not installed, skipping BirdNET tests")

    def test_classify_returns_list(self):
        from trailear.classify.birdnet import BirdNETClassifier

        clf = BirdNETClassifier(min_confidence=0.1)
        window = _make_window()
        results = clf.classify(window)
        assert isinstance(results, list)

    def test_sorted_by_confidence_desc(self):
        from trailear.classify.birdnet import BirdNETClassifier

        clf = BirdNETClassifier(min_confidence=0.1)
        window = _make_window()
        results = clf.classify(window)
        if results:
            confidences = [d.confidence for d in results]
            assert confidences == sorted(confidences, reverse=True)


class TestLocationFilter:
    def test_date_to_birdnet_week(self):
        import datetime

        from trailear.classify.location_filter import date_to_birdnet_week

        # Month 1 (January): day 1 -> week 1
        assert date_to_birdnet_week(datetime.date(2026, 1, 1)) == 1
        # Day 7 -> week 1
        assert date_to_birdnet_week(datetime.date(2026, 1, 7)) == 1
        # Day 8 -> week 2
        assert date_to_birdnet_week(datetime.date(2026, 1, 8)) == 2
        # Day 15 -> week 3
        assert date_to_birdnet_week(datetime.date(2026, 1, 15)) == 3
        # Day 25 -> week 4
        assert date_to_birdnet_week(datetime.date(2026, 1, 25)) == 4
        # Month 12 (December): day 31 -> week 48
        assert date_to_birdnet_week(datetime.date(2026, 12, 31)) == 48

    def test_filter_detections_by_species(self):
        from trailear.classify.location_filter import filter_detections_by_species
        from trailear.types import Detection

        d1 = Detection("Turdus merula", "Eurasian Blackbird", 0.9, 0.0)
        d2 = Detection("Oceanodroma leucorhoa", "Leach's Storm Petrel", 0.8, 0.0)

        allowed = {"Turdus merula"}
        filtered = filter_detections_by_species([d1, d2], allowed)
        assert len(filtered) == 1
        assert filtered[0].scientific_name == "Turdus merula"

        # None allowed set passes everything through
        assert len(filter_detections_by_species([d1, d2], None)) == 2
