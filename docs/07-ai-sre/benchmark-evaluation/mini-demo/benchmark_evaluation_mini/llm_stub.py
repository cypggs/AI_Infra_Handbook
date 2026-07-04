"""Deterministic LLM stub for the ReAct agent demo."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Action:
    tool: str
    input: str


@dataclass(frozen=True)
class LLMResponse:
    thought: str
    action: Optional[Action] = None
    final_answer: Optional[str] = None


class StubLLM:
    """A rule-based LLM that always produces predictable ReAct outputs.

    It does not call any external API, so tests are deterministic and CPU-only.
    """

    def __init__(self) -> None:
        self._token_counter = 0

    def complete(self, task: str, history: List[Tuple[str, str]], tools: List[str]) -> Tuple[str, int]:
        """Return (response_text, token_estimate)."""
        self._token_counter += 1
        tokens = 10 + len(task) // 4

        # Determine task category from keywords.
        if "15 + 27" in task or "calculate" in task.lower():
            return self._math_response(history), tokens
        if "Romeo and Juliet" in task or "Who wrote" in task:
            return self._fact_response(history), tokens
        if "population of paris" in task.lower():
            return self._multi_step_response(history), tokens
        if "fault" in task.lower() or "inject" in task.lower():
            return self._fault_response(history), tokens

        # Fallback: echo the task as the final answer.
        return f"Final Answer: {task}", tokens

    def _math_response(self, history: List[Tuple[str, str]]) -> str:
        if not history:
            return "I need to calculate this.\nAction: calculator(15 + 27)"
        return "The calculation gives 42.\nFinal Answer: 42"

    def _fact_response(self, history: List[Tuple[str, str]]) -> str:
        if not history:
            return "I should search for the author.\nAction: search(Romeo and Juliet author)"
        return "Romeo and Juliet was written by William Shakespeare.\nFinal Answer: William Shakespeare"

    def _multi_step_response(self, history: List[Tuple[str, str]]) -> str:
        if not history:
            return "I need the population of Paris first.\nAction: search(population of Paris)"
        if len(history) == 2:
            return "Now divide by 2.\nAction: calculator(2100000 / 2)"
        return "The result is 1050000.\nFinal Answer: 1050000"

    def _fault_response(self, history: List[Tuple[str, str]]) -> str:
        if not history:
            return "Let me calculate this.\nAction: calculator(20 + 22)"
        # After seeing a tool error, the agent still produces the correct answer.
        return "Even though the calculator failed, I know 20 + 22 = 42.\nFinal Answer: 42"


def parse_response(text: str) -> LLMResponse:
    """Parse a ReAct-style response into thought + action or final answer."""
    thought = ""
    for line in text.splitlines():
        if line.lower().startswith("thought:"):
            thought = line.split(":", 1)[1].strip()

    final_match = re.search(r"Final Answer:\s*(.+)", text, re.IGNORECASE)
    if final_match:
        return LLMResponse(thought=thought, final_answer=final_match.group(1).strip())

    action_match = re.search(r"Action:\s*(\w+)\((.*)\)", text)
    if action_match:
        tool = action_match.group(1).strip()
        arg = action_match.group(2).strip()
        return LLMResponse(thought=thought, action=Action(tool=tool, input=arg))

    return LLMResponse(thought=thought, final_answer=text.strip())
