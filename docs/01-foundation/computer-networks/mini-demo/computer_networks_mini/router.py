"""Simple L3 router with longest-prefix match."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

from .packet import Packet


def ip_to_int(ip: str) -> int:
    parts = [int(p) for p in ip.split(".")]
    return (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]


def prefix_to_net(prefix: str) -> Tuple[int, int]:
    """Return (network_int, mask_len) for CIDR prefix like '10.0.0.0/8'."""
    net, length = prefix.split("/")
    length = int(length)
    mask = (0xFFFFFFFF << (32 - length)) & 0xFFFFFFFF
    return ip_to_int(net) & mask, length


@dataclass
class Router:
    """Router with a forwarding table and per-interface queues."""
    name: str
    forwarding_table: List[Tuple[str, str]] = field(default_factory=list)
    queue: Deque[Packet] = field(default_factory=deque)
    max_queue_len: int = 10

    def __post_init__(self):
        # Sort by longest prefix first
        self.forwarding_table.sort(key=lambda p: -int(p[0].split("/")[1]))

    def add_route(self, prefix: str, next_hop: str) -> None:
        self.forwarding_table.append((prefix, next_hop))
        self.forwarding_table.sort(key=lambda p: -int(p[0].split("/")[1]))

    def longest_prefix_match(self, dst_ip: str) -> Optional[str]:
        dst = ip_to_int(dst_ip)
        for prefix, next_hop in self.forwarding_table:
            net, length = prefix_to_net(prefix)
            mask = (0xFFFFFFFF << (32 - length)) & 0xFFFFFFFF
            if (dst & mask) == net:
                return next_hop
        return None

    def receive(self, pkt: Packet) -> bool:
        if len(self.queue) >= self.max_queue_len:
            return False
        pkt.ttl -= 1
        if pkt.ttl > 0:
            self.queue.append(pkt)
        return True

    def forward(self) -> List[Tuple[Packet, str]]:
        """Return list of (packet, next_hop) for all queued packets."""
        forwarded: List[Tuple[Packet, str]] = []
        while self.queue:
            pkt = self.queue.popleft()
            next_hop = self.longest_prefix_match(pkt.dst_ip)
            if next_hop:
                forwarded.append((pkt, next_hop))
        return forwarded

    def drop_rate(self) -> float:
        return 0.0
