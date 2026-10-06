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
