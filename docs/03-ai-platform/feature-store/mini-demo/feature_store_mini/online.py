"""Online feature store: latest-snapshot key/value serving with TTL.

The online store only keeps, per entity, the *newest* feature values.
It answers single-key lookups in O(1) and supports per-store TTL so
stale values are treated as missing instead of silently served.
"""

from __future__ import annotations

import time
from typing import Callable, Iterable

from .offline import OfflineFeatureTable


class OnlineFeatureStore:
    """In-memory online store.

    Args:
        ttl_seconds: Values older than this (relative to the clock) are
            treated as missing. ``None`` disables expiry.
        clock: Injectable clock returning epoch seconds; tests pass a
            controllable fake clock to make TTL behavior deterministic.
    """

    def __init__(
        self,
        ttl_seconds: int | None = None,
        clock: Callable[[], float] | None = None,
    ):
        self.ttl_seconds = ttl_seconds
        self._clock = clock or time.time
        # entity_id -> (event_timestamp, {feature: value})
        self._data: dict[str, tuple[int, dict[str, float]]] = {}

    # ------------------------------------------------------------------ #
    def set(self, entity_id: str, values: dict[str, float], event_timestamp: int | None = None) -> None:
        ts = int(event_timestamp if event_timestamp is not None else self._clock())
        existing = self._data.get(str(entity_id))
        if existing is not None and existing[0] > ts:
            return  # out-of-order write: keep the newer snapshot
        self._data[str(entity_id)] = (ts, {k: float(v) for k, v in values.items()})

    def get(
        self,
        entity_id: str,
        as_of: int | None = None,
        feature_names: Iterable[str] | None = None,
    ) -> dict[str, float] | None:
        """Fetch the latest values for one entity.

        Args:
            entity_id: Entity primary key.
            as_of: Optional logical query time; defaults to the clock.
                Rows with ``event_timestamp > as_of`` or older than the
                TTL are treated as missing.
            feature_names: Optional subset projection.
        """
        entry = self._data.get(str(entity_id))
        if entry is None:
            return None
        ts, values = entry
        now = int(self._clock()) if as_of is None else int(as_of)
        if ts > now:
            return None
        if self.ttl_seconds is not None and now - ts > self.ttl_seconds:
            return None
        if feature_names is None:
            return dict(values)
        return {f: values[f] for f in feature_names if f in values}

    # ------------------------------------------------------------------ #
    def sync_from_offline(self, table: OfflineFeatureTable, as_of: int | None = None) -> int:
        """Materialize the latest offline snapshot into the online store.

        Mirrors the production "materialize / publish" step that copies
        freshly computed features from the offline store to the online
        serving path.
        """
        now = int(self._clock()) if as_of is None else int(as_of)
        count = 0
        for entity_id in table._rows:
            snapshot = table.as_of(entity_id, now)
            if snapshot is not None:
                self.set(entity_id, snapshot, event_timestamp=table.latest_timestamp(entity_id))
                count += 1
        return count

    def __len__(self) -> int:
        return len(self._data)
