"""Core data types for TrailEar."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class Window:
    """A chunk of audio to classify."""

    samples: np.ndarray
    sample_rate: int
    t_start: float  # seconds since walk start


@dataclass(frozen=True)
class Detection:
    """A single bird detection result."""

    scientific_name: str
    common_name: str
    confidence: float
    t: float


@dataclass
class WalkSummary:
    """Summary of a completed walk."""

    walk_id: int
    started_at: str
    ended_at: str
    duration_s: int
    species: list[dict] = field(default_factory=list)
