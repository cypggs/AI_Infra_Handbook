"""Multi-Agent Mini Demo - a pure-Python, CPU-runnable multi-agent system."""

from multi_agent_mini.agent import Agent
from multi_agent_mini.blackboard import Blackboard
from multi_agent_mini.bus import MessageBus
from multi_agent_mini.coordinator import Coordinator
from multi_agent_mini.llm_client import MockLLMClient
from multi_agent_mini.message import Message, MessageType
from multi_agent_mini.observer import Observer
from multi_agent_mini.skills import (
    draft_section,
    finalize_post,
    handoff_to,
    review_draft,
    search_facts,
)

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "Blackboard",
    "Coordinator",
    "Message",
    "MessageBus",
    "MessageType",
    "MockLLMClient",
    "Observer",
    "draft_section",
    "finalize_post",
    "handoff_to",
    "review_draft",
    "search_facts",
]
