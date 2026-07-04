"""Two-phase commit (2PC) coordinator and cohort simulation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .network import FakeClock, InProcessNetwork


@dataclass
class TwoPCMessage:
    src: str
    dst: str
    type: str
    payload: Any = None


class Cohort:
    """A 2PC participant that votes and records the final decision."""

    def __init__(self, cohort_id: str, vote_yes: bool = True) -> None:
        self.id = cohort_id
        self.vote_yes = vote_yes
        self.decision: str | None = None

    def step(self, msg: TwoPCMessage) -> TwoPCMessage | None:
        if msg.type == "prepare":
            vote = "yes" if self.vote_yes else "no"
            return TwoPCMessage(src=self.id, dst=msg.src, type=vote, payload=msg.payload)
        if msg.type == "commit":
            self.decision = "committed"
        elif msg.type == "abort":
            self.decision = "aborted"
        return None


class Coordinator:
    """2PC coordinator with a deterministic timeout.

    Happy path: all cohorts vote yes -> commit.
    Abort paths: any no vote, or timeout waiting for votes -> abort.
    """

    def __init__(
        self,
        coordinator_id: str,
        cohort_ids: List[str],
        clock: FakeClock,
        network: InProcessNetwork,
        timeout: int = 20,
    ) -> None:
        self.id = coordinator_id
        self.cohort_ids = list(cohort_ids)
        self.clock = clock
        self.network = network
        self.timeout = timeout

        self.state = "idle"
        self.value: Any = None
        self.votes: Dict[str, bool] = {}
        self.deadline: int | None = None

    def start_transaction(self, value: Any) -> bool:
        if self.state != "idle":
            return False
        self.state = "preparing"
        self.value = value
        self.votes = {}
        self.deadline = self.clock.now + self.timeout
        for cid in self.cohort_ids:
            self.network.send(
                self.id,
                cid,
                TwoPCMessage(src=self.id, dst=cid, type="prepare", payload=value),
            )
        return True

    def step(self, msg: TwoPCMessage) -> None:
        if self.state != "preparing":
            return
        if msg.type == "yes":
            self.votes[msg.src] = True
        elif msg.type == "no":
            self.votes[msg.src] = False
            self._abort()
            return

        if len(self.votes) == len(self.cohort_ids) and all(self.votes.values()):
            self._commit()

    def tick(self) -> None:
        if self.state == "preparing" and self.deadline is not None:
            if self.clock.now >= self.deadline:
                self._abort()

    def _commit(self) -> None:
        self.state = "committed"
        for cid in self.cohort_ids:
            self.network.send(
                self.id,
                cid,
                TwoPCMessage(src=self.id, dst=cid, type="commit", payload=self.value),
            )

    def _abort(self) -> None:
        self.state = "aborted"
        for cid in self.cohort_ids:
            self.network.send(
                self.id,
                cid,
                TwoPCMessage(src=self.id, dst=cid, type="abort", payload=self.value),
            )
