"""Data provenance labels and deterministic random generators."""

from __future__ import annotations

from enum import StrEnum

import numpy as np


class DataOrigin(StrEnum):
    """Origin label required on every dataset/table."""

    OBSERVED = "observed"
    SYNTHETIC = "synthetic"
    DERIVED = "derived"


def make_rng(seed: int) -> np.random.Generator:
    """Return a reproducible NumPy generator. Seed must be a non-negative int."""
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError(f"seed must be a non-negative int, got {seed!r}")
    return np.random.default_rng(seed)
