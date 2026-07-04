"""DNS resolver and L4 load balancer simulator."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import hashlib


@dataclass
class DNSRecord:
    name: str
    ip: str
    ttl: int  # seconds
    created_at: int = 0


@dataclass
class DNSResolver:
    """Simple DNS resolver with TTL-aware cache."""
    cache: Dict[str, DNSRecord] = field(default_factory=dict)
    authoritative: Dict[str, DNSRecord] = field(default_factory=dict)
    current_time: int = 0

    def add_record(self, name: str, ip: str, ttl: int) -> None:
        self.authoritative[name] = DNSRecord(name, ip, ttl)

    def resolve(self, name: str) -> Optional[str]:
        if name in self.cache:
            rec = self.cache[name]
            if self.current_time - rec.created_at < rec.ttl:
                return rec.ip
            del self.cache[name]
        auth = self.authoritative.get(name)
        if auth is None:
            return None
        cached = DNSRecord(auth.name, auth.ip, auth.ttl, self.current_time)
        self.cache[name] = cached
        return cached.ip

    def tick(self) -> None:
        self.current_time += 1


@dataclass
class LoadBalancer:
    """L4 load balancer with round-robin / weighted / consistent-hash strategies."""
    backends: List[str]
    strategy: str = "round-robin"  # round-robin | weighted | consistent-hash
    weights: Dict[str, int] = field(default_factory=dict)
    _rr_index: int = 0

    def __post_init__(self):
        if not self.weights:
            self.weights = {b: 1 for b in self.backends}

    def pick(self, key: str = "") -> Optional[str]:
        if not self.backends:
            return None
        if self.strategy == "round-robin":
            backend = self.backends[self._rr_index % len(self.backends)]
            self._rr_index += 1
            return backend
        if self.strategy == "weighted":
            total = sum(self.weights.get(b, 1) for b in self.backends)
            point = self._rr_index % max(total, 1)
            self._rr_index += 1
            cumulative = 0
            for b in self.backends:
                cumulative += self.weights.get(b, 1)
                if point < cumulative:
                    return b
            return self.backends[-1]
        if self.strategy == "consistent-hash":
            if not key:
                key = str(self._rr_index)
                self._rr_index += 1
            h = int(hashlib.md5(key.encode()).hexdigest(), 16)
            return self.backends[h % len(self.backends)]
        raise ValueError(f"Unknown strategy: {self.strategy}")

    def distribution(self, keys: List[str]) -> Dict[str, int]:
        counts: Dict[str, int] = {b: 0 for b in self.backends}
        for k in keys:
            b = self.pick(k)
            if b:
                counts[b] += 1
        return counts
