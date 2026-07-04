"""Quorum-based replicated key/value store simulation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from .network import FakeClock, InProcessNetwork


@dataclass
class KVMessage:
    src: str
    dst: str
    type: str
    key: str = ""
    value: Any = None
    version: int = 0
    req_id: str = ""


class KVNode:
    """Single storage node holding a local copy of the key space."""

    def __init__(self, node_id: str) -> None:
        self.id = node_id
        self.data: Dict[str, Any] = {}
        self.versions: Dict[str, int] = {}

    def handle(self, msg: KVMessage) -> Optional[KVMessage]:
        if msg.type == "put":
            if msg.version > self.versions.get(msg.key, 0):
                self.versions[msg.key] = msg.version
                self.data[msg.key] = msg.value
            return KVMessage(
                src=self.id,
                dst=msg.src,
                type="put_ack",
                key=msg.key,
                value=msg.value,
                version=msg.version,
                req_id=msg.req_id,
            )
        if msg.type == "get":
            return KVMessage(
                src=self.id,
                dst=msg.src,
                type="get_ack",
                key=msg.key,
                value=self.data.get(msg.key),
                version=self.versions.get(msg.key, 0),
                req_id=msg.req_id,
            )
        return None


class QuorumKVStore:
    """Client view of an N/W/R quorum replicated key/value store.

    The client talks to storage nodes through the shared ``InProcessNetwork``.
    Network partitions can be simulated with ``set_reachable`` so that the
    client only sees a subset of nodes.
    """

    def __init__(
        self,
        N: int,
        W: int,
        R: int,
        clock: FakeClock,
        network: InProcessNetwork,
        node_prefix: str = "node",
    ) -> None:
        self.N = N
        self.W = W
        self.R = R
        self.clock = clock
        self.network = network
        self.node_ids = [f"{node_prefix}{i}" for i in range(N)]
        self.nodes: Dict[str, KVNode] = {}
        self._acks: Dict[str, List[KVMessage]] = {}
        self._req_counter = 0
        self._version_counter: Dict[str, int] = {}
        self._committed: Dict[str, Tuple[Any, int]] = {}

        for nid in self.node_ids:
            node = KVNode(nid)
            self.nodes[nid] = node
            self.network.register(
                nid, lambda msg, n=node: self._dispatch_node_response(n.handle(msg))
            )
        self.network.register("client", self._client_handler)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _dispatch_node_response(self, resp: Optional[KVMessage]) -> None:
        if resp is not None:
            self.network.send(resp.src, resp.dst, resp)

    def _client_handler(self, msg: KVMessage) -> None:
        if msg.req_id:
            self._acks.setdefault(msg.req_id, []).append(msg)

    def _next_req_id(self) -> str:
        self._req_counter += 1
        return f"req-{self._req_counter}"

    # ------------------------------------------------------------------ #
    # Partition control
    # ------------------------------------------------------------------ #
    def set_reachable(self, node_ids: Set[str]) -> None:
        """Put the client and the listed nodes in one partition; the rest together."""
        visible = set(node_ids) & set(self.node_ids)
        visible.add("client")
        rest = set(self.node_ids) - visible
        groups: List[Set[str]] = [visible]
        if rest:
            groups.append(rest)
        self.network.set_partition(groups)

    def clear_partition(self) -> None:
        self.network.clear_partition()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def put(self, key: str, value: Any) -> bool:
        new_version = self._version_counter.get(key, 0) + 1
        self._version_counter[key] = new_version
        req_id = self._next_req_id()
        self._acks[req_id] = []

        for nid in self.node_ids:
            msg = KVMessage(
                src="client",
                dst=nid,
                type="put",
                key=key,
                value=value,
                version=new_version,
                req_id=req_id,
            )
            self.network.send("client", nid, msg)

        self.network.deliver_pending()

        acks = [m for m in self._acks.get(req_id, []) if m.type == "put_ack"]
        if len(acks) >= self.W:
            self._committed[key] = (value, new_version)
            return True
        return False

    def get(self, key: str) -> Tuple[Optional[Any], int, bool]:
        req_id = self._next_req_id()
        self._acks[req_id] = []

        for nid in self.node_ids:
            msg = KVMessage(
                src="client",
                dst=nid,
                type="get",
                key=key,
                req_id=req_id,
            )
            self.network.send("client", nid, msg)

        self.network.deliver_pending()

        acks = [m for m in self._acks.get(req_id, []) if m.type == "get_ack"]
        if len(acks) < self.R:
            return (None, 0, False)

        best = max(acks, key=lambda m: m.version)
        committed_version = self._committed.get(key, (None, 0))[1]
        stale = best.version < committed_version
        return (best.value, best.version, stale)
