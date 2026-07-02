"""Agent abstraction for the multi-agent mini demo."""

from __future__ import annotations

from typing import Any, Callable

from multi_agent_mini.blackboard import Blackboard
from multi_agent_mini.llm_client import MockLLMClient
from multi_agent_mini.message import Message
from multi_agent_mini.observer import Observer

SkillFn = Callable[..., Any]


class Agent:
    """An agent with a role, instructions, skill registry, and inbox."""

    def __init__(
        self,
        name: str,
        role: str,
        instructions: str = "",
        skills: dict[str, SkillFn] | None = None,
    ) -> None:
        self.name = name
        self.role = role
        self.instructions = instructions
        self.skills: dict[str, SkillFn] = dict(skills) if skills else {}
        self.inbox: list[Message] = []

    def register_skill(self, name: str, fn: SkillFn) -> None:
        """Add a callable skill under ``name``."""
        self.skills[name] = fn

    def receive(self, message: Message) -> None:
        """Accept a message into the inbox."""
        self.inbox.append(message)

    def act(
        self,
        blackboard: Blackboard,
        llm_client: MockLLMClient,
        observer: Observer,
    ) -> dict[str, Any]:
        """Ask the LLM client what to do and execute the chosen action.

        Returns a dict describing the action taken and its result.
        """
        context = {
            "instructions": self.instructions,
            "inbox": [
                {
                    "sender": m.sender,
                    "topic": m.topic,
                    "content": m.content,
                }
                for m in self.inbox
            ],
        }
        decision = llm_client.decide(self, blackboard, context)
        observer.record(
            "llm_decision",
            agent=self.name,
            role=self.role,
            decision=decision,
        )

        action = decision.get("action")

        if action == "skill":
            return self._run_skill(decision, blackboard, observer)

        if action == "handoff":
            target = decision.get("to", "")
            result = self._run_handoff(target, blackboard)
            observer.record(
                "handoff",
                agent=self.name,
                to=target,
                result=result,
            )
            return {
                "action": "handoff",
                "agent": self.name,
                "to": target,
                "result": result,
            }

        if action == "finalize":
            observer.record("finalize", agent=self.name)
            return {"action": "finalize", "agent": self.name}

        observer.record("noop", agent=self.name, decision=decision)
        return {"action": "noop", "agent": self.name, "decision": decision}

    def _run_skill(
        self,
        decision: dict[str, Any],
        blackboard: Blackboard,
        observer: Observer,
    ) -> dict[str, Any]:
        name = decision.get("name", "")
        args = dict(decision.get("args", {}))
        skill = self.skills.get(name)
        if skill is None:
            error = f"Skill {name!r} not found on agent {self.name!r}"
            observer.record("skill_error", agent=self.name, skill=name, error=error)
            return {"action": "skill", "agent": self.name, "name": name, "error": error}

        args.setdefault("blackboard", blackboard)
        try:
            result = skill(**args)
        except Exception as exc:  # pragma: no cover - defensive
            observer.record(
                "skill_error",
                agent=self.name,
                skill=name,
                error=str(exc),
            )
            return {
                "action": "skill",
                "agent": self.name,
                "name": name,
                "error": str(exc),
            }

        observer.record(
            "skill_executed",
            agent=self.name,
            skill=name,
            result=result,
        )
        return {
            "action": "skill",
            "agent": self.name,
            "name": name,
            "result": result,
        }

    def _run_handoff(self, target: str, blackboard: Blackboard) -> str:
        handoff_skill = self.skills.get("handoff_to")
        if handoff_skill:
            return handoff_skill(target=target, blackboard=blackboard)
        from multi_agent_mini.skills import handoff_to

        return handoff_to(target=target, blackboard=blackboard)

    def __repr__(self) -> str:  # pragma: no cover
        return f"Agent(name={self.name!r}, role={self.role!r})"
