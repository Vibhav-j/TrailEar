"""Audio preprocessing: mono conversion, resampling, normalization."""

from __future__ import annotations

import numpy as np


def to_mono(samples: np.ndarray) -> np.ndarray:
    """Convert multi-channel audio to mono by averaging channels."""
    if samples.ndim > 1:
        return samples.mean(axis=1)
    return samples


def normalize(samples: np.ndarray) -> np.ndarray:
    """Peak-normalize audio to [-1, 1] range."""
    peak = np.max(np.abs(samples))
    if peak > 0:
        return samples / peak
    return samples
