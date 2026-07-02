"""Agent runtime: ReAct loop with state, memory, tools, guardrails, and traces."""

import json
from typing import Any, Tuple

from .state import SessionState, State
from .memory import WorkingMemory
from .guardrails import Guardrails, GuardrailViolation
from .observer import TraceObserver
from .planner import SimplePlanner
from .llm_client import MockLLMClient
from .tool_registry import ToolRegistry
from .executor import ToolExecutor


class AgentRuntime:
    """Coordinates the ReAct loop for a single task."""

    def __init__(
        self,
        llm_client: MockLLMClient,
        tools: ToolRegistry,
        guardrails: Guardrails,
        observer: TraceObserver,
        planner: SimplePlanner | None = None,
        max_iterations: int = 10,
    ):
        self.llm_client = llm_client
        self.tools = tools
        self.guardrails = guardrails
        self.observer = observer
        self.planner = planner or SimplePlanner()
        self.max_iterations = max_iterations
        self.executor = ToolExecutor(tools)

    def run(self, task: str, session_id: str) -> Tuple[str, TraceObserver]:
        state = SessionState(State.IDLE)
        memory = WorkingMemory()
        call_count = 0

        self.observer.record(
            "task_received", session_id=session_id, task=task
        )

        try:
            self.guardrails.check_input(task)
        except GuardrailViolation as exc:
            state.transition(State.ERROR)
            self.observer.record(
                "guardrail_triggered",
                session_id=session_id,
                reason=exc.reason,
            )
            self.observer.record(
                "task_completed",
                session_id=session_id,
                state=state.state.name,
                answer=exc.reason,
            )
            return exc.reason, self.observer

        state.transition(State.PLANNING)
        subgoals = self.planner.plan(task)
        self.observer.record(
            "planning", session_id=session_id, subgoals=subgoals
        )

        system_prompt = self._build_system_prompt()
        memory.add_system_prompt(system_prompt)
        memory.add_user_message(task)

        for iteration in range(1, self.max_iterations + 1):
            state.transition(State.ACTING)
            self.observer.record(
                "llm_called",
                session_id=session_id,
                iteration=iteration,
                state=state.state.name,
            )
            response = self.llm_client.generate(memory.get_messages())
            choice = response["choices"][0]
            finish_reason = choice["finish_reason"]
            message = choice["message"]

            if finish_reason == "stop":
                answer = message.get("content", "")
                state.transition(State.DONE)
                self.observer.record(
                    "task_completed",
                    session_id=session_id,
                    state=state.state.name,
                    answer=answer,
                )
                return answer, self.observer

            if finish_reason == "tool_calls":
                tool_calls = message.get("tool_calls", [])
                memory.add_assistant_message(
                    content=message.get("content", ""),
                    tool_calls=tool_calls,
                )

                for tool_call in tool_calls:
                    state.transition(State.OBSERVING)
                    call_count += 1
                    try:
                        self.guardrails.check_tool_call(tool_call, call_count)
                    except GuardrailViolation as exc:
                        state.transition(State.ERROR)
                        self.observer.record(
                            "guardrail_triggered",
                            session_id=session_id,
                            reason=exc.reason,
                        )
                        self.observer.record(
                            "task_completed",
                            session_id=session_id,
                            state=state.state.name,
                            answer=exc.reason,
                        )
                        return exc.reason, self.observer

                    approved = self.guardrails.request_approval(tool_call)
                    if not approved:
                        reason = "Human approval denied"
                        state.transition(State.ERROR)
                        self.observer.record(
                            "guardrail_triggered",
                            session_id=session_id,
                            reason=reason,
                        )
                        self.observer.record(
                            "task_completed",
                            session_id=session_id,
                            state=state.state.name,
                            answer=reason,
                        )
                        return reason, self.observer

                    context = {"approved": approved}
                    result = self.executor.execute(tool_call, context=context)
                    memory.add_tool_message(
                        tool_call_id=tool_call["id"],
                        content=str(result),
                    )
                    self.observer.record(
                        "tool_executed",
                        session_id=session_id,
                        tool_name=tool_call["function"]["name"],
                        result=result,
                    )

        reason = f"Max iterations reached ({self.max_iterations})"
        state.transition(State.ERROR)
        self.observer.record(
            "guardrail_triggered",
            session_id=session_id,
            reason=reason,
        )
        self.observer.record(
            "task_completed",
            session_id=session_id,
            state=state.state.name,
            answer=reason,
        )
        return reason, self.observer

    def _build_system_prompt(self) -> str:
        schemas = self.tools.schemas()
        return (
            "You are a helpful agent. Choose a tool when needed.\n"
            f"Available tools: {json.dumps(schemas)}"
        )

    def __repr__(self) -> str:  # pragma: no cover
        return f"AgentRuntime(max_iterations={self.max_iterations})"
