from personal_agent_mini import demo


def test_scenario_calendar_conflict_pushes_notification():
    agent = demo.scenario_calendar_conflict()
    assert any("日程冲突" in n.title for n in agent.notifications)
    assert any(ep.kind == "calendar" for ep in agent.memory.episodes())


def test_scenario_email_digest_pushes_boss_only():
    agent = demo.scenario_email_digest()
    digests = [n for n in agent.notifications if n.level == "digest"]
    assert len(digests) == 1
    assert "Q4 预算审批紧急" in digests[0].body
    ignored = [t for t in agent.trace if t["event"] == "ignore"]
    assert len(ignored) == 1  # newsletter filtered out


def test_scenario_memory_recall_mentions_oat_latte():
    agent, answer = demo.scenario_memory_recall()
    assert "燕麦拿铁" in answer
    assert "咖啡偏好" in answer


def test_scenario_permission_denies_then_sends_after_approval():
    agent = demo.scenario_permission()
    email = agent.connectors["email"]
    assert len(email.sent) == 1
    denied = [n for n in agent.notifications if n.title == "操作被拒绝"]
    assert len(denied) == 1
    confirm = [n for n in agent.notifications if n.level == "confirm"]
    assert len(confirm) == 1


def test_run_demo_prints_all_scenarios(capsys):
    demo.run_demo()
    out = capsys.readouterr().out
    for title, _ in demo.SCENARIOS:
        assert title in out
    assert "燕麦拿铁" in out
