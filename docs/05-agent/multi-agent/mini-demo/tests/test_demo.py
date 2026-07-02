"""End-to-end test for the demo entry point."""

from multi_agent_mini.demo import make_team, run_demo


def test_make_team_has_four_roles():
    agents = make_team()
    roles = {a.role for a in agents}
    assert roles == {"coordinator", "researcher", "writer", "reviewer"}


def test_run_demo_completes(capsys):
    run_demo()
    captured = capsys.readouterr()
    assert "Multi-Agent Mini Demo" in captured.out
    assert "final_post" in captured.out
    assert "Observer trace:" in captured.out


def test_run_demo_blackboard_contains_expected_keys():
    from multi_agent_mini.blackboard import Blackboard
    from multi_agent_mini.bus import MessageBus
    from multi_agent_mini.coordinator import Coordinator
    from multi_agent_mini.llm_client import MockLLMClient
    from multi_agent_mini.observer import Observer

    coordinator = Coordinator(
        agents=make_team(),
        mode="handoff",
        blackboard=Blackboard(),
        bus=MessageBus(),
        observer=Observer(),
        llm_client=MockLLMClient(),
    )
    result = coordinator.run(
        "Write a short blog post about multi-agent collaboration best practices."
    )
    bb = result["blackboard"]
    assert "facts" in bb
    assert "draft" in bb
    assert "review" in bb
    assert "final_post" in bb

    event_types = {e["type"] for e in result["trace"]}
    assert "run_started" in event_types
    assert "finalized" in event_types
    assert "skill_executed" in event_types
