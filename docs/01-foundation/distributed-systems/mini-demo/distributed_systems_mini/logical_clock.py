"""Lamport logical clock implementation."""
from dataclasses import dataclass


@dataclass
class LamportClock:
    """Single-node Lamport clock.

    ``tick`` advances the local clock, ``send`` produces a timestamp that is
    sent with a message, and ``receive`` advances the clock past the received
    timestamp.
    """

    _time: int = 0

    def tick(self) -> int:
        self._time += 1
        return self._time

    def send(self) -> int:
        self._time += 1
        return self._time

    def receive(self, ts: int) -> int:
        self._time = max(self._time, ts) + 1
        return self._time

    @property
    def time(self) -> int:
        return self._time
