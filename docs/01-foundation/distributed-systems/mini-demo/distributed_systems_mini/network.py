"""Fake clock and in-process message-passing network for deterministic simulation."""
from __future__ import annotations

import heapq
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set


class FakeClock:
    """Deterministic, steppable clock used by all simulations.

    The clock maintains a monotonically increasing integer time and a priority
    queue of scheduled callbacks.  Callers advance ``now`` explicitly and then
    run pending callbacks, which makes every test fully deterministic.
    """

    def __init__(self, start: int = 0) -> None:
        self._now = start
        self._events: List[tuple[int, int, Callable, tuple, dict]] = []
        self._seq = 0

    @property
    def now(self) -> int:
        return self._now

    def advance(self, ticks: int = 1) -> int:
        """Move time forward by ``ticks`` and return the new time."""
        self._now += ticks
        return self._now

    def sleep_until(self, t: int) -> None:
        """Advance time to ``t`` if it is in the future."""
        self._now = max(self._now, t)

    def schedule(self, delay: int, callback: Callable, *args: Any, **kwargs: Any) -> None:
        """Schedule ``callback(*args, **kwargs)`` at ``now + delay``."""
        self._seq += 1
        heapq.heappush(
            self._events,
            (self._now + delay, self._seq, callback, args, kwargs),
        )

    def run_pending(self) -> None:
        """Execute every scheduled callback whose due time has been reached."""
        while self._events and self._events[0][0] <= self._now:
            _, _, callback, args, kwargs = heapq.heappop(self._events)
            callback(*args, **kwargs)

    def run_all(self) -> None:
        """Execute every remaining scheduled callback regardless of time."""
        while self._events:
            _, _, callback, args, kwargs = heapq.heappop(self._events)
            callback(*args, **kwargs)


@dataclass
class InProcessNetwork:
    """Routes messages between local node handlers using the shared FakeClock.

    Features:

    * ``send`` and ``broadcast`` with configurable per-hop delay.
    * Probabilistic message loss (seeded RNG for determinism).
    * Network partitions: nodes in different partition groups cannot communicate.
    * ``isolate`` helper to cut off a set of nodes from the rest.
    """

    clock: FakeClock
    handlers: Dict[str, Callable[[Any], None]] = field(default_factory=dict)
    delivery_delay: int = 0
    loss_prob: float = 0.0
    partitions: Optional[List[Set[str]]] = None
    seed: int = 0
    _rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def register(self, node_id: str, handler: Callable[[Any], None]) -> None:
        self.handlers[node_id] = handler

    def unregister(self, node_id: str) -> None:
        self.handlers.pop(node_id, None)

    def set_partition(self, groups: List[Set[str]]) -> None:
        """Install a partition: traffic is only allowed inside each group."""
        self.partitions = groups

    def clear_partition(self) -> None:
        self.partitions = None

    def isolate(self, node_ids: Set[str]) -> None:
        """Put each listed node in its own partition; keep the rest together."""
        groups: List[Set[str]] = [{nid} for nid in node_ids]
        rest = set(self.handlers.keys()) - set(node_ids)
        if rest:
            groups.append(rest)
        self.set_partition(groups)

    def _can_deliver(self, src: str, dst: str) -> bool:
        if src == dst:
            return True
        if not self.partitions:
            return True
        src_group = dst_group = None
        for i, group in enumerate(self.partitions):
            if src in group:
                src_group = i
            if dst in group:
                dst_group = i
        # If both endpoints are assigned to different groups, drop the message.
        if src_group is not None and dst_group is not None and src_group != dst_group:
            return False
        return True

    def send(self, src: str, dst: str, payload: Any) -> bool:
        """Schedule ``payload`` for delivery to ``dst`` if the link is up."""
        if not self._can_deliver(src, dst):
            return False
        handler = self.handlers.get(dst)
        if handler is None:
            return False
        if self.loss_prob > 0 and self._rng.random() < self.loss_prob:
            return False
        self.clock.schedule(self.delivery_delay, handler, payload)
        return True

    def broadcast(self, src: str, payload: Any) -> int:
        """Send ``payload`` to every registered handler except ``src``."""
        count = 0
        for dst in list(self.handlers.keys()):
            if dst != src and self.send(src, dst, payload):
                count += 1
        return count

    def deliver_pending(self) -> None:
        """Deliver all messages that are due at the current clock time."""
        self.clock.run_pending()
