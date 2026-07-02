"""Coordinator that orchestrates a team of agents."""

from __future__ import annotations

from typing import Any

from multi_agent_mini.agent import Agent
from multi_agent_mini.blackboard import Blackboard
from multi_agent_mini.bus import MessageBus
from multi_agent_mini.llm_client import MockLLMClient
from multi_agent_mini.observer import Observer
from multi_agent_mini.skills import finalize_post


class Coordinator:
    """Run a team of agents in ``round_robin`` or ``handoff`` mode."""

    def __init__(
        self,
        agents: list[Agent],
        mode: str = "handoff",
        blackboard: Blackboard | None = None,
        bus: MessageBus | None = None,
        observer: Observer | None = None,
        llm_client: MockLLMClient | None = None,
    ) -> None:
        if mode not in {"round_robin", "handoff"}:
            raise ValueError(f"Unsupported mode: {mode}")
        self.mode = mode
        self.agents = list(agents)
        self.agents_by_name: dict[str, Agent] = {a.name: a for a in agents}
        self.blackboard = blackboard if blackboard is not None else Blackboard()
        self.bus = bus if bus is not None else MessageBus()
        self.observer = observer if observer is not None else Observer()
        self.llm_client = llm_client if llm_client is not None else MockLLMClient()

    def run(self, user_request: str, max_turns: int = 20) -> dict[str, Any]:
        """Execute the agent team and return the final blackboard and trace."""
        self.observer.record(
            "run_started",
            request=user_request,
            mode=self.mode,
            agents=[a.name for a in self.agents],
        )
        self.blackboard.write("user_request", user_request, scope="readonly")

        if self.mode == "handoff":
            turns = self._run_handoff(max_turns)
        else:
            turns = self._run_round_robin(max_turns)

        return {
            "blackboard": self.blackboard.to_dict(),
            "trace": list(self.observer.events),
            "turns": turns,
        }

    def _run_handoff(self, max_turns: int) -> int:
        current = self.agents_by_name.get("coordinator", self.agents[0])
        for turn in range(max_turns):
            result = current.act(self.blackboard, self.llm_client, self.observer)
            self.bus.broadcast(
                topic="agent_action",
                content={"agent": current.name, "result": result},
                sender=current.name,
            )
            self.bus.deliver_all()

            if result["action"] == "finalize":
                finalize_post(self.blackboard)
                self.observer.record(
                    "finalized",
                    agent=current.name,
                    final_post_length=len(self.blackboard.read("final_post") or ""),
                )
                return turn + 1

            if result["action"] == "handoff" and result.get("to"):
                next_agent = self.agents_by_name.get(result["to"])
                if next_agent is None:
                    raise RuntimeError(f"Unknown handoff target: {result['to']}")
                current = next_agent
            else:
                current = self._next_by_missing_keys()
        return max_turns

    def _run_round_robin(self, max_turns: int) -> int:
        order = ["researcher", "writer", "reviewer", "coordinator"]
        ordered_agents = [
            self.agents_by_name[name]
            for name in order
            if name in self.agents_by_name
        ]
        if not ordered_agents:
            ordered_agents = self.agents

        current_index = 0
        for turn in range(max_turns):
            current = ordered_agents[current_index % len(ordered_agents)]
            result = current.act(self.blackboard, self.llm_client, self.observer)
            self.bus.broadcast(
                topic="agent_action",
                content={"agent": current.name, "result": result},
                sender=current.name,
            )
            self.bus.deliver_all()

            if result["action"] == "finalize":
                finalize_post(self.blackboard)
                self.observer.record(
                    "finalized",
                    agent=current.name,
                    final_post_length=len(self.blackboard.read("final_post") or ""),
                )
                return turn + 1

            current_index += 1
        return max_turns

    def _next_by_missing_keys(self) -> Agent:
        if self.blackboard.read("facts") is None:
            return self.agents_by_name.get("researcher", self.agents[0])
        if self.blackboard.read("draft") is None:
            return self.agents_by_name.get("writer", self.agents[0])
        if self.blackboard.read("review") is None:
            return self.agents_by_name.get("reviewer", self.agents[0])
        return self.agents_by_name.get("coordinator", self.agents[0])
