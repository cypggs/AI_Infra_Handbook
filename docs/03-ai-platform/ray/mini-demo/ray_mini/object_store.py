"""Per-node Plasma-like object store with reference counting and spilling."""
from __future__ import annotations

from collections import OrderedDict

from .model import ObjectRef


class ObjectStore:
    """A simplified Plasma object store for one node.

    Three categories (mirroring Ray's whitepaper "Lifetime of an Object"):
      - ``primary``: the first copy, made by the producing task or ray.put.
        Pinned by the raylet: NOT LRU-evicted while any reference is in scope.
      - ``evictable``: copies from ray.get / arg-fetch. LRU-evictable.
      - ``spilled``: evictable objects pushed to external storage; restorable.

    Ref counting is explicit: ``add_ref`` / ``release``. A primary copy is held
    while its refcount > 0; once released it becomes evictable.
    """

    def __init__(self, node_id: int, capacity: int, spill_threshold: float):
        self.node_id = node_id
        self.capacity = capacity
        self.spill_threshold = spill_threshold
        self.used = 0

        # ref id -> size
        self.primary: dict[int, int] = {}
        self.evictable: OrderedDict[int, int] = OrderedDict()  # LRU order
        self.spilled: dict[int, int] = {}                      # ref id -> size
        self.refcount: dict[int, int] = {}                     # ref id -> count

        # stats
        self.spill_count = 0
        self.evict_count = 0

    # ---- reference counting -------------------------------------------------

    def add_ref(self, ref_id: int) -> None:
        self.refcount[ref_id] = self.refcount.get(ref_id, 0) + 1

    def release(self, ref_id: int) -> None:
        if self.refcount.get(ref_id, 0) <= 0:
            return
        self.refcount[ref_id] -= 1
        if self.refcount[ref_id] == 0:
            # No more references -> a primary copy becomes evictable.
            if ref_id in self.primary:
                size = self.primary.pop(ref_id)
                self.evictable[ref_id] = size
            del self.refcount[ref_id]

    # ---- placement ---------------------------------------------------------

    def put_primary(self, ref: ObjectRef) -> None:
        """Place the primary (pinned) copy of an object produced on this node."""
        assert ref.id not in self.primary, "primary already present"
        self.primary[ref.id] = ref.size
        self.used += ref.size
        self.refcount[ref.id] = self.refcount.get(ref.id, 0) + 1
        self._maybe_spill()

    def add_evictable_copy(self, ref: ObjectRef) -> None:
        """A non-primary copy (from get / arg-fetch)."""
        if ref.id in self.evictable or ref.id in self.primary:
            return
        self.evictable[ref.id] = ref.size
        self.used += ref.size
        self._maybe_spill()

    # ---- resolution --------------------------------------------------------

    def has(self, ref_id: int) -> bool:
        return ref_id in self.primary or ref_id in self.evictable

    def get(self, ref_id: int) -> bool:
        """Resolve a read; restore from spill if needed. Returns True if present."""
        if ref_id in self.primary or ref_id in self.evictable:
            self.evictable.move_to_end(ref_id) if ref_id in self.evictable else None
            return True
        if ref_id in self.spilled:
            self._restore(ref_id)
            return True
        return False

    # ---- failure ------------------------------------------------------------

    def lose_all(self) -> dict:
        """Node died: all local copies gone. Returns what was lost (by category)."""
        lost = {
            "primary": dict(self.primary),
            "evictable": dict(self.evictable),
            "spilled": dict(self.spilled),
        }
        self.primary.clear()
        self.evictable.clear()
        self.spilled.clear()
        self.used = 0
        return lost

    # ---- internal: spilling / eviction -------------------------------------

    def _maybe_spill(self) -> None:
        """Eager spilling at spill_threshold (whitepaper 'Handling OOM')."""
        while self.used > self.capacity * self.spill_threshold and self.evictable:
            ref_id, size = self.evictable.popitem(last=False)  # LRU
            self.used -= size
            self.spilled[ref_id] = size
            self.spill_count += 1

    def _restore(self, ref_id: int) -> None:
        size = self.spilled.pop(ref_id)
        # Make room if needed, then restore as evictable.
        self._free(size)
        self.evictable[ref_id] = size
        self.used += size

    def _free(self, needed: int) -> None:
        """Evict LRU evictables until at least `needed` units are free."""
        while self.used + needed > self.capacity and self.evictable:
            ref_id, size = self.evictable.popitem(last=False)
            self.used -= size
            self.evict_count += 1
