"""Entry point for the multi-agent mini demo."""

from __future__ import annotations

from multi_agent_mini.agent import Agent
from multi_agent_mini.blackboard import Blackboard
from multi_agent_mini.bus import MessageBus
from multi_agent_mini.coordinator import Coordinator
from multi_agent_mini.llm_client import MockLLMClient
from multi_agent_mini.observer import Observer
from multi_agent_mini.skills import (
    draft_section,
    finalize_post,
    handoff_to,
    review_draft,
    search_facts,
)


def make_team() -> list[Agent]:
    """Create the default researcher/writer/reviewer/coordinator team."""
    researcher = Agent(
        name="researcher",
        role="researcher",
        instructions="Collect key facts on the requested topic.",
    )
    writer = Agent(
        name="writer",
        role="writer",
        instructions="Produce a structured draft using available facts.",
    )
    reviewer = Agent(
        name="reviewer",
        role="reviewer",
        instructions="Review the draft and list concrete improvements.",
    )
    coordinator = Agent(
        name="coordinator",
        role="coordinator",
        instructions="Coordinate the team and finalize the deliverable.",
    )

    for agent in (researcher, writer, reviewer, coordinator):
        agent.register_skill("search_facts", search_facts)
        agent.register_skill("draft_section", draft_section)
        agent.register_skill("review_draft", review_draft)
        agent.register_skill("finalize_post", finalize_post)
        agent.register_skill("handoff_to", handoff_to)

    return [coordinator, researcher, writer, reviewer]


def run_demo() -> None:
    """Run the blog-writing task in handoff mode and print results."""
    agents = make_team()
    coordinator = Coordinator(
        agents=agents,
        mode="handoff",
        blackboard=Blackboard(),
        bus=MessageBus(),
        observer=Observer(),
        llm_client=MockLLMClient(),
    )

    result = coordinator.run(
        user_request="Write a short blog post about multi-agent collaboration best practices.",
        max_turns=20,
    )

    print("\n" + "=" * 60)
    print("Multi-Agent Mini Demo")
    print("=" * 60)
    print(f"Mode : {coordinator.mode}")
    print(f"Turns: {result['turns']}")
    print("\nBlackboard:")
    for key, value in result["blackboard"].items():
        preview = str(value).replace("\n", " ")[:120]
        print(f"  {key}: {preview}")
    print("\n" + coordinator.observer.render())
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
