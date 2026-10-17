"""Proactive personal agent: sense -> relevance gate -> gated act -> notify.

The loop is intentionally explicit and rule-based so the whole pipeline is
deterministic; a production agent replaces the scorer and planner with an LLM
but keeps the same shape: personal connectors, personal memory, a permission
gate in front of every side effect, and a notification queue for proactivity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .memory import PersonalMemory

AUTO = "auto"
ASK = "ask"
DENY = "deny"

DEFAULT_POLICIES = {
    "read_email": AUTO,
    "read_calendar": AUTO,
    "summarize_email": AUTO,
    "send_email": ASK,
    "create_event": ASK,
    "external_payment": DENY,
}


@dataclass
class PermissionDecision:
    allowed: bool
    requires_approval: bool = False
    reason: str = ""


@dataclass
class Notification:
    id: str
    level: str  # info / digest / confirm
    title: str
    body: str
    ts: datetime


class PermissionGate:
    """Per-action-type policy: auto / ask / deny."""

    def __init__(self, policies: dict | None = None) -> None:
        self.policies = dict(DEFAULT_POLICIES)
        self.policies.update(policies or {})

    def check(self, action_type: str) -> PermissionDecision:
        policy = self.policies.get(action_type, ASK)
        if policy == DENY:
            return PermissionDecision(False, False, f"action {action_type!r} is denied by policy")
        if policy == ASK:
            return PermissionDecision(False, True, f"action {action_type!r} requires user approval")
        return PermissionDecision(True, False, "")


class RelevanceScorer:
    """Rule-based relevance: profile contacts + urgency words + source weight."""

    URGENT_WORDS = ("紧急", "urgent", "asap", "截止", "deadline")

    def score(self, event, memory: PersonalMemory) -> tuple[float, list[str]]:
        reasons: list[str] = []
        score = 0.0
        if event.source == "email":
            sender = event.payload.get("from", "")
            for fact in memory.profile().values():
                if sender and (sender in fact.value or fact.value in sender):
                    score += 3.0
                    reasons.append(f"sender matches profile:{fact.key}")
            text = f"{event.payload.get('subject', '')} {event.payload.get('body', '')}"
            for word in self.URGENT_WORDS:
                if word in text:
                    score += 2.0
                    reasons.append(f"urgent keyword {word!r}")
        elif event.source == "calendar":
            score += 2.0
            reasons.append("calendar event")
        elif event.source == "files":
            score += 1.0
            reasons.append("file change")
        return score, reasons


class PersonalAgent:
    """A minimal proactive personal agent around personal data connectors."""

    def __init__(self, clock, memory: PersonalMemory | None = None,
                 gate: PermissionGate | None = None,
                 scorer: RelevanceScorer | None = None,
                 threshold: float = 2.0) -> None:
        self.clock = clock
        self.memory = memory or PersonalMemory()
        self.gate = gate or PermissionGate()
        self.scorer = scorer or RelevanceScorer()
        self.threshold = threshold
        self.connectors: dict[str, object] = {}
        self.notifications: list[Notification] = []
        self.trace: list[dict] = []
        self.pending: list[dict] = []
        self._seen_conflicts: set[tuple[str, str]] = set()
        self._n_counter = 0
        self._p_counter = 0

    # ---------- wiring ----------

    def attach(self, connector) -> None:
        self.connectors[connector.name] = connector

    # ---------- trace & notify ----------

    def _log(self, event: str, **kw) -> dict:
        entry = {"seq": len(self.trace) + 1, "event": event,
                 "ts": self.clock.now().isoformat(), **kw}
        self.trace.append(entry)
        return entry

    def _notify(self, level: str, title: str, body: str) -> Notification:
        self._n_counter += 1
        note = Notification(f"n{self._n_counter}", level, title, body, self.clock.now())
        self.notifications.append(note)
        self._log("notify", id=note.id, level=level, title=title)
        return note

    # ---------- proactive loop ----------

    def step(self) -> bool:
        """One sense-judge-act sweep. Returns True if anything was processed."""
        acted = False
        for conn in self.connectors.values():
            for ev in conn.poll():
                acted = True
                self._log("sense", id=ev.id, source=ev.source, kind=ev.kind)
                score, reasons = self.scorer.score(ev, self.memory)
                if score < self.threshold:
                    self._log("ignore", id=ev.id, score=score, reasons=reasons)
                    continue
                self.memory.add_episode(ev.source, self._describe(ev), ev.ts, tags=("observation",))
                self._log("relevant", id=ev.id, score=score, reasons=reasons)
                self._handle(ev)
        if self._check_conflicts():
            acted = True
        return acted

    def run_until_idle(self, max_steps: int = 20) -> int:
        steps = 0
        for _ in range(max_steps):
            steps += 1
            if not self.step():
                break
        return steps

    def _describe(self, ev) -> str:
        p = ev.payload
        if ev.source == "email":
            return f"收到邮件「{p['subject']}」（来自 {p['from']}）"
        if ev.source == "calendar":
            return f"日程新增「{p['title']}」"
        if ev.source == "files":
            return f"文件新增 {p['name']}"
        return str(p)

    def _handle(self, ev) -> None:
        if ev.source == "email" and ev.kind == "new_email":
            self.gate.check("read_email")  # read-only, always allowed
            snippet = ev.payload["body"][:30]
            self._notify("digest", "新邮件摘要", f"{ev.payload['from']}: {ev.payload['subject']} — {snippet}")
        elif ev.source == "files" and ev.kind == "file_added":
            self._notify("info", "文件更新", f"新增文件 {ev.payload['name']}")

    def _check_conflicts(self) -> bool:
        cal = self.connectors.get("calendar")
        if cal is None:
            return False
        acted = False
        for a, b in cal.conflicts():
            key = (a["id"], b["id"])
            if key in self._seen_conflicts:
                continue
            self._seen_conflicts.add(key)
            title = f"日程冲突：{a['title']} 与 {b['title']}"
            body = (f"{a['start']:%m-%d %H:%M} 起两场活动重叠"
                    f"（{a['title']} 至 {a['end']:%H:%M}，{b['title']} 至 {b['end']:%H:%M}），建议调整其一。")
            self._notify("info", title, body)
            self.memory.add_episode("calendar", title, self.clock.now(), tags=("conflict",))
            self._log("conflict", a=a["title"], b=b["title"])
            acted = True
        return acted

    # ---------- gated actions ----------

    def act(self, action_type: str, **kw) -> dict:
        """Every side effect goes through the permission gate."""
        decision = self.gate.check(action_type)
        self._log("permission", action=action_type, allowed=decision.allowed,
                  requires_approval=decision.requires_approval, reason=decision.reason)
        if decision.requires_approval:
            self._p_counter += 1
            pid = f"p{self._p_counter}"
            self.pending.append({"id": pid, "action_type": action_type, "args": kw, "status": "awaiting"})
            self._notify("confirm", "需要确认", f"{action_type} 等待批准：{kw}")
            return {"status": "awaiting_approval", "pending_id": pid}
        if not decision.allowed:
            self._notify("info", "操作被拒绝", decision.reason)
            return {"status": "denied", "reason": decision.reason}
        return {"status": "ok", "result": self._execute(action_type, **kw)}

    def _execute(self, action_type: str, **kw):
        if action_type == "send_email":
            conn = self.connectors["email"]
            conn.send(kw["to"], kw["subject"], kw["body"])
            self.memory.add_episode("agent", f"已发送邮件给 {kw['to']}：{kw['subject']}", self.clock.now())
            self._notify("info", "已发送", f"邮件已发送给 {kw['to']}")
            return kw
        if action_type == "create_event":
            conn = self.connectors["calendar"]
            conn.add_event(kw["title"], kw["start"], kw["end"])
            self.memory.add_episode("agent", f"已创建日程「{kw['title']}」", self.clock.now())
            return kw
        raise ValueError(f"unknown action {action_type!r}")

    def pending_actions(self) -> list[dict]:
        return [p for p in self.pending if p["status"] == "awaiting"]

    def approve(self, pending_id: str):
        for p in self.pending:
            if p["id"] == pending_id and p["status"] == "awaiting":
                p["status"] = "approved"
                return self._execute(p["action_type"], **p["args"])
        raise KeyError(pending_id)

    # ---------- answering ----------

    def answer(self, query: str, limit: int = 3) -> str:
        """Pull-style recall: answer from personal memory + user profile."""
        parts: list[str] = []
        for fact in self.memory.profile_match(query):
            parts.append(f"你的画像：{fact.key} = {fact.value}")
        for ep in self.memory.recall(query, limit=limit):
            parts.append(f"{ep.day} [{ep.kind}] {ep.content}")
        if not parts:
            return "我暂时没有关于这个话题的记忆。"
        return "；".join(parts)
