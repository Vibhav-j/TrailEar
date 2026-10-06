"""Classifier abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod

from trailear.types import Detection, Window


class Classifier(ABC):
    """Abstract interface for bird-call classifiers."""

    @abstractmethod
    def classify(self, window: Window) -> list[Detection]:
        """Classify an audio window. Returns detections sorted by confidence descending."""
        ...
