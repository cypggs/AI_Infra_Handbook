"""A minimal, deterministic Raft implementation for educational simulation."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class LogEntry:
    term: int
    command: Any


class RaftNode:
    """Single Raft node using an external FakeClock + InProcessNetwork.

    The node exposes ``tick`` for time-based events and ``step`` for incoming
    messages.  All outgoing messages are sent through the supplied network.
    """

    def __init__(
        self,
        node_id: str,
        peers: List[str],
        clock: Any,
        network: Any,
        election_timeout: Tuple[int, int] = (50, 150),
        heartbeat_interval: int = 25,
    ) -> None:
        self.id = node_id
        self.node_id = node_id
        self.peers = peers
        self.clock = clock
        self.network = network
        self.election_timeout = election_timeout
        self.heartbeat_interval = heartbeat_interval

        self.state = "follower"
        self.term = 0
        self.voted_for: Optional[str] = None
        self.log: List[LogEntry] = []
        self.commit_index = 0
        self.last_applied = 0

        self.votes_received: Set[str] = set()
        self.leader_id: Optional[str] = None
        self.next_index: Dict[str, int] = {}
        self.match_index: Dict[str, int] = {}

        self._rng = random.Random(node_id)
        self._election_deadline = clock.now + self._random_election_timeout()
        self._heartbeat_deadline = clock.now + heartbeat_interval

        network.register(node_id, self.step)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _random_election_timeout(self) -> int:
        lo, hi = self.election_timeout
        return self._rng.randint(lo, hi)

    def _reset_election_timer(self) -> None:
        self._election_deadline = self.clock.now + self._random_election_timeout()

    def _become_follower(self, term: int) -> None:
        self.state = "follower"
        self.term = term
        self.voted_for = None
        self.votes_received = set()
        self._reset_election_timer()

    def _become_candidate(self) -> None:
        self.state = "candidate"
        self.term += 1
        self.voted_for = self.id
        self.votes_received = {self.id}
        self._reset_election_timer()
        self._send_request_vote()

    def _become_leader(self) -> None:
        self.state = "leader"
        self.leader_id = self.id
        self.next_index = {p: len(self.log) + 1 for p in self.peers}
        self.match_index = {p: 0 for p in self.peers}
        self._heartbeat_deadline = self.clock.now

    def _last_log_index(self) -> int:
        return len(self.log)

    def _last_log_term(self) -> int:
        if not self.log:
            return 0
        return self.log[-1].term

    def _log_term_at(self, index: int) -> int:
        if index == 0 or index > len(self.log):
            return 0
        return self.log[index - 1].term

    def _quorum(self) -> int:
        return (len(self.peers) + 1) // 2 + 1

    # ------------------------------------------------------------------ #
    # Outgoing messages
    # ------------------------------------------------------------------ #
    def _send_request_vote(self) -> None:
        msg = {
            "type": "request_vote",
            "term": self.term,
            "candidate_id": self.id,
            "last_log_index": self._last_log_index(),
            "last_log_term": self._last_log_term(),
        }
        for p in self.peers:
            self.network.send(self.id, p, msg)

    def _send_append_entries(self, peer: str) -> None:
        next_i = self.next_index.get(peer, len(self.log) + 1)
        prev_index = next_i - 1
        prev_term = self._log_term_at(prev_index)
        entries = self.log[prev_index:]
        msg = {
            "type": "append_entries",
            "term": self.term,
            "leader_id": self.id,
            "prev_log_index": prev_index,
            "prev_log_term": prev_term,
            "entries": [(e.term, e.command) for e in entries],
            "leader_commit": self.commit_index,
        }
        self.network.send(self.id, peer, msg)

    def _broadcast_append_entries(self) -> None:
        for p in self.peers:
            self._send_append_entries(p)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    @property
    def is_leader(self) -> bool:
        return self.state == "leader"

    def propose(self, command: Any) -> int:
        if not self.is_leader:
            raise RuntimeError(f"node {self.id} is not the leader")
        self.log.append(LogEntry(self.term, command))
        index = len(self.log)
        self._broadcast_append_entries()
        self._heartbeat_deadline = self.clock.now + self.heartbeat_interval
        return index

    def tick(self) -> None:
        if self.state == "leader":
            if self.clock.now >= self._heartbeat_deadline:
                self._broadcast_append_entries()
                self._heartbeat_deadline = self.clock.now + self.heartbeat_interval
            for p in self.peers:
                if self.match_index.get(p, 0) < len(self.log):
                    self._send_append_entries(p)
        else:
            if self.clock.now >= self._election_deadline:
                self._become_candidate()

    def step(self, msg: Dict[str, Any]) -> None:
        msg_type = msg.get("type")
        if msg_type == "request_vote":
            self._handle_request_vote(msg)
        elif msg_type == "vote":
            self._handle_vote(msg)
        elif msg_type == "append_entries":
            self._handle_append_entries(msg)
        elif msg_type == "append_entries_response":
            self._handle_append_entries_response(msg)

    # ------------------------------------------------------------------ #
    # Message handlers
    # ------------------------------------------------------------------ #
    def _handle_request_vote(self, msg: Dict[str, Any]) -> None:
        term = msg["term"]
        candidate = msg["candidate_id"]
        if term > self.term:
            self._become_follower(term)

        vote_granted = False
        if term == self.term:
            last_index = msg["last_log_index"]
            last_term = msg["last_log_term"]
            log_ok = (last_term > self._last_log_term()) or (
                last_term == self._last_log_term() and last_index >= self._last_log_index()
            )
            if log_ok and (self.voted_for is None or self.voted_for == candidate):
                self.voted_for = candidate
                vote_granted = True
                self._reset_election_timer()

        self.network.send(
            self.id,
            candidate,
            {
                "type": "vote",
                "term": self.term,
                "vote_granted": vote_granted,
                "voter_id": self.id,
            },
        )

    def _handle_vote(self, msg: Dict[str, Any]) -> None:
        term = msg["term"]
        if term > self.term:
            self._become_follower(term)
            return
        if term < self.term or self.state != "candidate":
            return
        if msg.get("vote_granted"):
            self.votes_received.add(msg["voter_id"])
            if len(self.votes_received) >= self._quorum():
                self._become_leader()

    def _handle_append_entries(self, msg: Dict[str, Any]) -> None:
        term = msg["term"]
        if term < self.term:
            self.network.send(
                self.id,
                msg["leader_id"],
                {
                    "type": "append_entries_response",
                    "term": self.term,
                    "success": False,
                    "match_index": 0,
                    "follower_id": self.id,
                },
            )
            return

        if term > self.term:
            self._become_follower(term)

        self.state = "follower"
        self.leader_id = msg["leader_id"]
        self._reset_election_timer()

        prev_index = msg["prev_log_index"]
        prev_term = msg["prev_log_term"]
        success = True
        if prev_index > 0:
            if prev_index > len(self.log) or self.log[prev_index - 1].term != prev_term:
                success = False

        if success:
            entries = [LogEntry(t, c) for t, c in msg["entries"]]
            for i, entry in enumerate(entries, start=prev_index + 1):
                if i <= len(self.log):
                    if self.log[i - 1].term != entry.term:
                        self.log = self.log[: i - 1]
                        self.log.append(entry)
                else:
                    self.log.append(entry)

            leader_commit = msg["leader_commit"]
            if leader_commit > self.commit_index:
                self.commit_index = min(leader_commit, len(self.log))

        self.network.send(
            self.id,
            msg["leader_id"],
            {
                "type": "append_entries_response",
                "term": self.term,
                "success": success,
                "match_index": prev_index + len(msg["entries"]) if success else 0,
                "follower_id": self.id,
            },
        )

    def _handle_append_entries_response(self, msg: Dict[str, Any]) -> None:
        term = msg["term"]
        if term > self.term:
            self._become_follower(term)
            return
        if term < self.term or self.state != "leader":
            return

        follower = msg["follower_id"]
        if msg["success"]:
            self.match_index[follower] = max(self.match_index.get(follower, 0), msg["match_index"])
            self.next_index[follower] = self.match_index[follower] + 1
        else:
            self.next_index[follower] = max(1, self.next_index.get(follower, 2) - 1)

        for index in range(self.commit_index + 1, len(self.log) + 1):
            if self.log[index - 1].term != self.term:
                continue
            count = 1
            for p in self.peers:
                if self.match_index.get(p, 0) >= index:
                    count += 1
            if count >= self._quorum():
                self.commit_index = index

    def applied_entries(self) -> List[Any]:
        return [e.command for e in self.log[: self.commit_index]]
