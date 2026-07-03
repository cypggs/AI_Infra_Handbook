"""observer.py — 事件观测器，记录调度/控制循环的关键事件，输出可读 trace。

对应真实 K8s：Pod 的 Events（`kubectl describe pod` 看到的）、kube-scheduler 日志、
kube-state-metrics。教学版只记录"值得审计"的事件，便于演示与测试断言。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from k8s_mini.model import Condition, Pod, PodPhase
from k8s_mini.store import Event, EventType


@dataclass
class TraceEvent:
    tick: int
    kind: str  # "schedule" / "evict" / "phase" / "create" / "delete" / "gang"
    message: str


@dataclass
class Observer:
    events: list[TraceEvent] = field(default_factory=list)
    _tick: int = 0
    _prev_phase: dict[str, PodPhase] = field(default_factory=dict)
    _prev_node: dict[str, str] = field(default_factory=dict)
    _seen_pod: set[str] = field(default_factory=set)

    def set_tick(self, tick: int) -> None:
        self._tick = tick

    def on_event(self, event: Event) -> None:
        if event.resource_kind != "pod":
            return
        name = event.key
        pod: Pod = event.obj
        if event.type == EventType.ADDED and name not in self._seen_pod:
            self.events.append(TraceEvent(self._tick, "create", f"Pod/{name} created (phase=Pending)"))
            self._seen_pod.add(name)
        elif event.type == EventType.DELETED:
            self.events.append(TraceEvent(self._tick, "delete", f"Pod/{name} deleted"))
            self._prev_phase.pop(name, None)
            self._prev_node.pop(name, None)
            return

        prev_phase = self._prev_phase.get(name)
        if prev_phase != pod.phase:
            self.events.append(TraceEvent(self._tick, "phase", f"Pod/{name} {prev_phase}→{pod.phase}"))
            self._prev_phase[name] = pod.phase

        prev_node = self._prev_node.get(name)
        if pod.node_name and prev_node != pod.node_name:
            self.events.append(TraceEvent(
                self._tick, "schedule", f"Pod/{name} bound to Node/{pod.node_name}"
            ))
            self._prev_node[name] = pod.node_name

    def render(self) -> str:
        lines = [f"[t={e.tick:02d}] {e.kind.upper():8} {e.message}" for e in self.events]
        return "\n".join(lines)
