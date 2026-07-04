"""Sliding-window reliable transport simulator."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set

from .packet import Packet


@dataclass
class ReliableTransport:
    """TCP-like reliable transport over a lossy channel."""
    name: str
    window_size: int = 4
    timeout: int = 3
    _next_seq: int = 0
    _unacked: dict[int, int] = field(default_factory=dict)  # seq -> age
    _received: Set[int] = field(default_factory=set)
    _delivered: List[int] = field(default_factory=list)
    _peer_ack: int = 0

    def send_window(self) -> List[Packet]:
        """Generate packets for the current window."""
        packets: List[Packet] = []
        while len(self._unacked) < self.window_size:
            seq = self._next_seq
            pkt = Packet(src_ip=self.name, dst_ip="peer", seq=seq, flags="DATA")
            packets.append(pkt)
            self._unacked[seq] = 0
            self._next_seq += 1
        return packets

    def age_and_retransmit(self) -> List[Packet]:
        """Increase age of unacked packets and retransmit timed-out ones."""
        retrans: List[Packet] = []
        for seq, age in list(self._unacked.items()):
            age += 1
            self._unacked[seq] = age
            if age >= self.timeout:
                retrans.append(Packet(src_ip=self.name, dst_ip="peer", seq=seq, flags="DATA"))
                self._unacked[seq] = 0
        return retrans

    def receive(self, pkt: Packet) -> Optional[Packet]:
        """Process incoming packet; return ACK if applicable."""
        if pkt.flags == "DATA":
            self._received.add(pkt.seq)
            # cumulative ACK: largest contiguous sequence received
            ack = 0
            while ack in self._received:
                if ack not in self._delivered:
                    self._delivered.append(ack)
                ack += 1
            return Packet(src_ip=self.name, dst_ip="peer", ack=ack, flags="ACK")
        if pkt.flags == "ACK":
            # remove all seq < ack from unacked
            for seq in list(self._unacked.keys()):
                if seq < pkt.ack:
                    del self._unacked[seq]
            self._peer_ack = max(self._peer_ack, pkt.ack)
        return None

    def in_flight(self) -> int:
        return len(self._unacked)

    def delivered_count(self) -> int:
        return len(self._delivered)
