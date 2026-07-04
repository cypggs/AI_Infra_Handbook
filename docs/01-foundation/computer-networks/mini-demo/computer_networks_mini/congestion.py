"""Congestion control simulator: AIMD + simplified CUBIC-like."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class CongestionController:
    """Simplified AIMD + CUBIC-like congestion controller."""
    cwnd: float = 1.0
    ssthresh: float = 100.0
    beta: float = 0.7
    max_cwnd: float = 0.0
    epoch_start: int = 0
    K: float = 0.0
    C: float = 0.4
    rtt_ms: float = 10.0
    history: List[float] = field(default_factory=list)

    def on_ack(self, time_step: int) -> None:
        if self.cwnd < self.ssthresh:
            # slow start
            self.cwnd += 1.0
        else:
            # CUBIC-like growth near previous max
            if self.max_cwnd == 0 or self.cwnd >= self.max_cwnd:
                self.cwnd += 1.0 / self.cwnd
            else:
                t = time_step - self.epoch_start
                target = self.max_cwnd + self.C * ((t - self.K) ** 3)
                if target > self.cwnd:
                    self.cwnd += (target - self.cwnd) / self.cwnd
        self.history.append(self.cwnd)

    def on_loss(self, time_step: int) -> None:
        self.max_cwnd = max(self.max_cwnd, self.cwnd)
        self.cwnd *= self.beta
        self.ssthresh = self.cwnd
        self.epoch_start = time_step
        # K is time to grow from cwnd to max_cwnd: Wmax - cwnd = C*(K)^3
        delta = self.max_cwnd - self.cwnd
        if delta > 0:
            self.K = (delta / self.C) ** (1.0 / 3.0)
        else:
            self.K = 0.0
        self.history.append(self.cwnd)
