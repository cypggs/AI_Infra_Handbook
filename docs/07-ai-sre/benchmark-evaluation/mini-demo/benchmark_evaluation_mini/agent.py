"""Deterministic ReAct agent with built-in tracing."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .environment import ToolError, ToolRegistry
from .llm_stub import StubLLM, parse_response
from .tracer import Tracer


class AgentResult:
    def __init__(self, answer: Optional[str], trace: Tracer) -> None:
        self.answer = answer
        self.trace = trace


class Agent:
    """A minimal ReAct agent that records every thought and tool call as trace spans."""

    def __init__(
        self,
        llm: StubLLM,
        tools: ToolRegistry,
        tracer: Tracer,
        max_steps: int = 5,
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.tracer = tracer
        self.max_steps = max_steps

    def run(self, task: str, scenario: Optional[Dict[str, Any]] = None) -> AgentResult:
        scenario = scenario or {}
        history: List[Tuple[str, str]] = []
        answer: Optional[str] = None

        with self.tracer.span("agent.run", task=task, scenario=scenario):
            for step in range(self.max_steps):
                with self.tracer.span("llm.complete", step=step):
                    self.tracer.advance(2)  # simulate thinking latency
                    raw, tokens = self.llm.complete(task, history, ["search", "calculator"])
                    self.tracer.add_event("llm.response", text=raw, tokens=tokens)
                    self.tracer.advance(1)

                parsed = parse_response(raw)

                if parsed.final_answer is not None:
                    answer = parsed.final_answer
                    self.tracer.add_event("agent.final_answer", answer=answer)
                    break

                if parsed.action is None:
                    self.tracer.add_event("agent.parse_error", raw=raw)
                    break

                with self.tracer.span(
                    "tool.call",
                    tool=parsed.action.tool,
                    input=parsed.action.input,
                ):
                    self.tracer.advance(1)
                    try:
                        output = self.tools.execute(
                            parsed.action.tool,
                            parsed.action.input,
                            scenario,
                        )
                        self.tracer.add_event("tool.result", output=output)
                    except ToolError as exc:
                        output = f"ERROR: {exc}"
                        self.tracer.add_event("tool.error", error=str(exc))
                    self.tracer.advance(1)

                history.append(("assistant", raw))
                history.append(("tool", output))

        return AgentResult(answer=answer, trace=self.tracer)
