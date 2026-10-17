from personal_agent_mini.agent import DENY, PermissionGate, PersonalAgent, RelevanceScorer
from personal_agent_mini.clock import FakeClock
from personal_agent_mini.connectors import CalendarConnector, EmailConnector
from personal_agent_mini.memory import PersonalMemory


def _agent(clock=None, **kw):
    return PersonalAgent(clock or FakeClock(), **kw)


def test_sense_logs_events_with_sequential_trace():
    agent = _agent()
    agent.attach(EmailConnector(agent.clock, inbox=[("a@b.c", "s", "b")]))
    agent.step()
    senses = [t for t in agent.trace if t["event"] == "sense"]
    assert len(senses) == 1
    assert senses[0]["seq"] == 1


def test_low_relevance_email_is_ignored():
    agent = _agent()
    agent.attach(EmailConnector(agent.clock, inbox=[("news@x.io", "促销", "买买买")]))
    agent.step()
    ignored = [t for t in agent.trace if t["event"] == "ignore"]
    assert len(ignored) == 1
    assert agent.notifications == []


def test_urgent_email_from_profile_contact_pushed_as_digest():
    agent = _agent()
    agent.memory.add_episode("user", "记住：重要联系人=老板 <boss@corp.com>", agent.clock.now())
    agent.attach(EmailConnector(agent.clock, inbox=[
        ("boss@corp.com", "预算紧急", "请尽快批复"),
    ]))
    agent.step()
    assert agent.notifications[0].level == "digest"
    assert "预算紧急" in agent.notifications[0].body
    relevant = [t for t in agent.trace if t["event"] == "relevant"]
    assert len(relevant) == 1


def test_calendar_conflict_notifies_once():
    agent = _agent()
    agent.attach(CalendarConnector(agent.clock, events=[
        ("评审", "2026-10-19T14:00:00", "2026-10-19T15:00:00"),
        ("牙医", "2026-10-19T14:30:00", "2026-10-19T15:15:00"),
    ]))
    agent.run_until_idle()
    conflicts = [n for n in agent.notifications if "日程冲突" in n.title]
    assert len(conflicts) == 1
    agent.step()  # idempotent: no duplicate
    conflicts = [n for n in agent.notifications if "日程冲突" in n.title]
    assert len(conflicts) == 1


def test_send_email_requires_approval():
    agent = _agent()
    agent.attach(EmailConnector(agent.clock))
    result = agent.act("send_email", to="x@y.com", subject="s", body="b")
    assert result["status"] == "awaiting_approval"
    assert len(agent.pending_actions()) == 1
    confirm = [n for n in agent.notifications if n.level == "confirm"]
    assert len(confirm) == 1


def test_external_payment_hard_denied():
    agent = _agent()
    result = agent.act("external_payment", amount=1, merchant="m")
    assert result["status"] == "denied"
    denied = [n for n in agent.notifications if n.title == "操作被拒绝"]
    assert len(denied) == 1


def test_approve_executes_pending_action():
    agent = _agent()
    agent.attach(EmailConnector(agent.clock))
    result = agent.act("send_email", to="x@y.com", subject="s", body="b")
    agent.approve(result["pending_id"])
    email = agent.connectors["email"]
    assert len(email.sent) == 1
    assert agent.pending_actions() == []
    sent = [n for n in agent.notifications if n.title == "已发送"]
    assert len(sent) == 1


def test_permission_trace_records_every_check():
    agent = _agent()
    agent.act("external_payment", amount=1, merchant="m")
    perms = [t for t in agent.trace if t["event"] == "permission"]
    assert perms[0]["allowed"] is False
    assert perms[0]["action"] == "external_payment"


def test_custom_gate_policy_can_deny_send_email():
    gate = PermissionGate({"send_email": DENY})
    agent = _agent(gate=gate)
    agent.attach(EmailConnector(agent.clock))
    result = agent.act("send_email", to="x@y.com", subject="s", body="b")
    assert result["status"] == "denied"


def test_notification_ids_are_sequential():
    agent = _agent()
    agent.attach(EmailConnector(agent.clock, inbox=[
        ("老板 <boss@corp.com>", "一", "x"),
    ]))
    agent.memory.add_episode("user", "记住：重要联系人=老板", agent.clock.now())
    agent.step()
    ids = [n.id for n in agent.notifications]
    assert ids == [f"n{i}" for i in range(1, len(ids) + 1)]


def test_answer_uses_profile_and_episodes():
    agent = _agent()
    agent.memory.add_episode("user", "记住：咖啡偏好=燕麦拿铁", agent.clock.now())
    agent.memory.add_episode("user", "周末在杭州的咖啡馆喝了手冲", agent.clock.now())
    answer = agent.answer("杭州咖啡")
    assert "咖啡偏好 = 燕麦拿铁" in answer
    assert "手冲" in answer


def test_answer_fallback_when_no_memory():
    agent = _agent()
    assert agent.answer("完全不相关的话题") == "我暂时没有关于这个话题的记忆。"


def test_scorer_reasons_are_explanatory():
    agent = _agent()
    agent.memory.add_episode("user", "记住：重要联系人=老板 <boss@corp.com>", agent.clock.now())
    email = EmailConnector(agent.clock, inbox=[("boss@corp.com", "紧急截止", "asap")])
    ev = email.poll()[0]
    score, reasons = RelevanceScorer().score(ev, agent.memory)
    assert score >= 5.0
    assert any("profile" in r for r in reasons)
    assert any("urgent" in r for r in reasons)
