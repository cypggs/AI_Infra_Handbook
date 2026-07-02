"""Tests for the Agent class."""

from multi_agent_mini.agent import Agent
from multi_agent_mini.blackboard import Blackboard
from multi_agent_mini.llm_client import MockLLMClient
from multi_agent_mini.message import Message
from multi_agent_mini.observer import Observer
from multi_agent_mini.skills import search_facts


def test_register_skill():
    agent = Agent(name="a", role="researcher")
    agent.register_skill("search", search_facts)
    assert "search" in agent.skills


def test_receive_message():
    agent = Agent(name="a", role="writer")
    msg = Message(sender="bus", recipient="a", topic="ping", content="hi")
    agent.receive(msg)
    assert len(agent.inbox) == 1
    assert agent.inbox[0].content == "hi"


def test_act_runs_skill_decision():
    board = Blackboard()
    observer = Observer()
    llm = MockLLMClient()
    agent = Agent(name="researcher", role="researcher")
    agent.register_skill("search_facts", search_facts)

    result = agent.act(board, llm, observer)

    assert result["action"] == "skill"
    assert result["name"] == "search_facts"
    assert board.read("facts") is not None
    assert any(e["type"] == "skill_executed" for e in observer.events)


def test_act_finalize():
    board = Blackboard()
    board.write("facts", "x")
    board.write("draft", "y")
    board.write("review", "z")
    observer = Observer()
    llm = MockLLMClient()
    agent = Agent(name="coordinator", role="coordinator")

    result = agent.act(board, llm, observer)

    assert result["action"] == "finalize"
    assert result["agent"] == "coordinator"


def test_act_handoff():
    board = Blackboard()
    observer = Observer()
    llm = MockLLMClient()
    agent = Agent(name="coordinator", role="coordinator")

    result = agent.act(board, llm, observer)

    assert result["action"] == "handoff"
    assert result["to"] == "researcher"
    assert board.read("next_agent") == "researcher"
