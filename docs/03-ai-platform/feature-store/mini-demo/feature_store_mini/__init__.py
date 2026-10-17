"""Minimal offline/online feature store demo.

This package implements the three pillars of a feature store
with a deliberately small codebase:

- ``entity``   : entity / primary-key model (user, item, ...)
- ``offline``  : point-in-time correct offline feature tables
- ``online``   : low-latency online key/value store with TTL
- ``skew``     : training/serving skew detection utilities
"""

from .entity import Entity
from .offline import OfflineFeatureTable
from .online import OnlineFeatureStore
from .skew import detect_skew, feature_distribution, psi

__all__ = [
    "Entity",
    "OfflineFeatureTable",
    "OnlineFeatureStore",
    "detect_skew",
    "feature_distribution",
    "psi",
]

__version__ = "0.1.0"
