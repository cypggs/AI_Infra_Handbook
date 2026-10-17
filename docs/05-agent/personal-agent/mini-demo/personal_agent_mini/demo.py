"""End-to-end scenarios for the mini proactive personal agent.

Scenarios:
1. calendar conflict detection -> proactive notification
2. email digest push (low-relevance mail filtered out)
3. cross-day memory recall (episode store + user profile)
4. permission gate: approval flow + hard denial path
"""
from __future__ import annotations

from .agent import PersonalAgent
from .clock import FakeClock
from .connectors import CalendarConnector, EmailConnector
from .memory import PersonalMemory


def scenario_calendar_conflict() -> PersonalAgent:
    """Two overlapping meetings on Monday morning -> conflict push."""
    clock = FakeClock("2026-10-19T08:00:00")
    agent = PersonalAgent(clock)
    cal = CalendarConnector(clock, events=[
        ("产品评审会", "2026-10-19T14:00:00", "2026-10-19T15:00:00"),
        ("牙医预约", "2026-10-19T14:30:00", "2026-10-19T15:15:00"),
    ])
    agent.attach(cal)
    agent.run_until_idle()
    return agent


def scenario_email_digest() -> PersonalAgent:
    """Boss email pushed as digest; newsletter ignored by the relevance gate."""
    clock = FakeClock("2026-10-17T09:00:00")
    agent = PersonalAgent(clock)
    agent.memory.add_episode(
        "user", "记住：重要联系人=老板 <boss@corp.com>", clock.now())
    email = EmailConnector(clock, inbox=[
        ("老板 <boss@corp.com>", "Q4 预算审批紧急", "请在本周五前批复 Q4 预算，否则影响采购"),
        ("newsletter@dev.io", "Weekly Digest", "本周开源社区动态汇总……"),
    ])
    agent.attach(email)
    agent.run_until_idle()
    return agent


def scenario_memory_recall() -> tuple[PersonalAgent, str]:
    """Facts remembered days ago are still recallable."""
    clock = FakeClock("2026-10-14T09:00:00")
    agent = PersonalAgent(clock)
    agent.memory.add_episode("user", "记住：咖啡偏好=燕麦拿铁", clock.now())
    agent.memory.add_episode("user", "周末去了杭州，在西湖边的咖啡馆工作了一下午", clock.now())
    clock.advance(days=3)
    answer = agent.answer("我上周末喝了什么咖啡？")
    return agent, answer


def scenario_permission() -> PersonalAgent:
    """Sending email requires approval; external payment is hard-denied."""
    clock = FakeClock("2026-10-17T10:00:00")
    agent = PersonalAgent(clock)
    agent.attach(EmailConnector(clock))
    result = agent.act("send_email", to="client@corp.com", subject="报价单", body="请查收附件。")
    assert result["status"] == "awaiting_approval"
    agent.act("external_payment", amount=199, merchant="某商城")
    agent.approve(result["pending_id"])
    return agent


SCENARIOS = [
    ("场景 1：日程冲突主动提醒", scenario_calendar_conflict),
    ("场景 2：重要邮件摘要推送", scenario_email_digest),
    ("场景 3：跨天记忆召回", scenario_memory_recall),
    ("场景 4：权限拒绝与人工确认", scenario_permission),
]


def _show_agent(agent: PersonalAgent) -> None:
    for note in agent.notifications:
        print(f"[{note.ts:%m-%d %H:%M}] ({note.level}) {note.title}: {note.body}")
    for entry in agent.trace:
        if entry["event"] in ("sense", "ignore", "relevant", "conflict", "permission"):
            print(f"  trace#{entry['seq']} {entry['event']}: "
                  + ", ".join(f"{k}={v}" for k, v in entry.items()
                              if k not in ("seq", "event", "ts")))


def _show(title: str, body) -> None:
    print(f"\n=== {title} ===")
    if isinstance(body, tuple):
        agent, answer = body
        _show_agent(agent)
        print("  Q: 我上周末喝了什么咖啡？")
        print(f"  A: {answer}")
    elif isinstance(body, PersonalAgent):
        _show_agent(body)
    else:
        print(body)


def run_demo() -> None:
    print("Mini Personal Agent Demo (fake clock, zero deps)")
    for title, fn in SCENARIOS:
        _show(title, fn())


if __name__ == "__main__":
    run_demo()
