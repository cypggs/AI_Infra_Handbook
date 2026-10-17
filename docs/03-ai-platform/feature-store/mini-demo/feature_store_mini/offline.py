"""Offline feature table with point-in-time correct joins.

The offline store keeps the *full history* of feature values keyed by
entity id and ``event_timestamp``.  The crucial operation is the
point-in-time (PIT) join used to build training datasets: for every
labeled example we must assemble the feature values as they were known
*at the label timestamp*, never from the future.
"""

from __future__ import annotations

from bisect import bisect_right
from typing import Any, Iterable

from .entity import Entity

#: Sentinel used in query rows to carry the observation timestamp.
QUERY_TS = "query_timestamp"


class OfflineFeatureTable:
    """Append-only offline feature table.

    Rows are stored per entity, sorted by ``(event_timestamp, seq)``
    so lookups are ``O(log n)`` and deterministic.
    """

    def __init__(self, name: str, entity: Entity, feature_names: Iterable[str]):
        self.name = name
        self.entity = entity
        self.feature_names = tuple(feature_names)
        if not self.feature_names:
            raise ValueError("feature_names must not be empty")
        # entity_key -> list of (event_timestamp, seq, values tuple)
        self._rows: dict[str, list[tuple[int, int, tuple[float, ...]]]] = {}
        self._seq = 0

    # ------------------------------------------------------------------ #
    # ingestion
    # ------------------------------------------------------------------ #
    def ingest(self, entity_id: str, event_timestamp: int, values: dict[str, float]) -> None:
        """Append one feature row.

        Args:
            entity_id: Primary key of the entity.
            event_timestamp: Logical event time (epoch seconds).
            values: Mapping from feature name to value. Every declared
                feature must be present (use ``float("nan")`` for nulls).
        """
        missing = [f for f in self.feature_names if f not in values]
        if missing:
            raise KeyError(f"{self.name}: missing features {missing}")
        extra = [k for k in values if k not in self.feature_names]
        if extra:
            raise KeyError(f"{self.name}: unknown features {extra}")
        row = (int(event_timestamp), self._seq, tuple(float(values[f]) for f in self.feature_names))
        self._seq += 1
        bucket = self._rows.setdefault(str(entity_id), [])
        pos = bisect_right(bucket, (row[0], row[1]))
        bucket.insert(pos, row)

    def ingest_many(self, rows: Iterable[dict]) -> int:
        """Ingest raw records; each must contain the join key and a timestamp."""
        count = 0
        for raw in rows:
            entity_id = self.entity.key_of(raw)
            ts = int(raw[QUERY_TS])
            self.ingest(entity_id, ts, {f: raw[f] for f in self.feature_names})
            count += 1
        return count

    # ------------------------------------------------------------------ #
    # point-in-time access
    # ------------------------------------------------------------------ #
    def as_of(self, entity_id: str, query_timestamp: int, max_age: int | None = None):
        """Return the feature values valid at ``query_timestamp``.

        Semantics: the latest row with ``event_timestamp <= query_timestamp``;
        ``max_age`` (seconds) further drops rows that are too stale.
        Returns ``None`` when nothing qualifies.
        """
        bucket = self._rows.get(str(entity_id))
        if not bucket:
            return None
        pos = bisect_right(bucket, (int(query_timestamp), self._seq))
        if pos == 0:
            return None
        ts, _, values = bucket[pos - 1]
        if max_age is not None and int(query_timestamp) - ts > max_age:
            return None
        return dict(zip(self.feature_names, values))

    def point_in_time_join(
        self,
        query_rows: Iterable[dict],
        max_age: int | None = None,
    ) -> list[dict]:
        """Build a point-in-time correct training dataset.

        Args:
            query_rows: Each row contains the entity join key, a
                ``query_timestamp`` (when the label was observed) and
                arbitrary extra columns (e.g. the label) that are
                passed through unchanged.
            max_age: Optional freshness requirement in seconds.

        Returns:
            One dict per query row: join key, ``query_timestamp``, one
            column per feature (``None`` when unavailable) and all
            passthrough columns.
        """
        out = []
        for q in query_rows:
            entity_id = self.entity.key_of(q)
            ts = int(q[QUERY_TS])
            features = self.as_of(entity_id, ts, max_age=max_age)
            row = {self.entity.join_key: entity_id, QUERY_TS: ts}
            for f in self.feature_names:
                row[f] = None if features is None else features[f]
            for k, v in q.items():
                if k not in row:
                    row[k] = v
            out.append(row)
        return out

    # ------------------------------------------------------------------ #
    # introspection
    # ------------------------------------------------------------------ #
    def row_count(self, entity_id: str | None = None) -> int:
        if entity_id is not None:
            return len(self._rows.get(str(entity_id), []))
        return sum(len(b) for b in self._rows.values())

    def latest_timestamp(self, entity_id: str) -> int | None:
        bucket = self._rows.get(str(entity_id))
        return None if not bucket else bucket[-1][0]

    def all_timestamps(self, entity_id: str) -> list[int]:
        return [ts for ts, _, _ in self._rows.get(str(entity_id), [])]
