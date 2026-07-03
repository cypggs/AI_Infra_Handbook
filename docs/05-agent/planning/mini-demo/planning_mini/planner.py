"""TaskPlanner turns LLM output into a validated Plan object."""
from __future__ import annotations

from typing import Any, Dict

from planning_mini.llm_client import MockLLMClient
from planning_mini.plan import Plan, Step
from planning_mini.tool_registry import ToolRegistry


class TaskPlanner:
    """Builds a :class:`Plan` from an LLM-generated plan description.

    The planner is responsible for parsing the raw LLM response and validating
    that every referenced tool is registered.
    """

    def __init__(
        self,
        llm_client: MockLLMClient,
        tool_registry: ToolRegistry,
    ) -> None:
        self.llm_client = llm_client
        self.tool_registry = tool_registry

    def create_plan(self, task: str) -> Plan:
        """Generate and validate a plan for ``task``.

        Args:
            task: Natural-language user request.

        Returns:
            A validated :class:`Plan` instance.

        Raises:
            ValueError: If the LLM response is malformed or references an
                unknown tool.
        """
        raw = self.llm_client.generate_plan(task, list(self.tool_registry.tools.keys()))
        if "steps" not in raw:
            raise ValueError("LLM plan is missing the 'steps' key")

        steps: list[Step] = []
        for item in raw["steps"]:
            tool_name = item["tool"]
            if tool_name not in self.tool_registry.tools:
                raise ValueError(f"Unknown tool '{tool_name}' in plan")
            steps.append(
                Step(
                    id=item["id"],
                    tool=tool_name,
                    args=item.get("args", {}),
                    deps=item.get("deps", []),
                )
            )

        plan = Plan(task=task, steps=steps)
        # Sanity check the DAG while constructing the plan.
        plan.topological_order()
        return plan

    def create_plan_from_raw(self, task: str, raw: Dict[str, Any]) -> Plan:
        """Build a plan from an already-parsed raw structure.

        This helper is used by the executor when applying a replan.
        """
        if "steps" not in raw:
            raise ValueError("Raw plan is missing the 'steps' key")

        steps: list[Step] = []
        for item in raw["steps"]:
            tool_name = item["tool"]
            if tool_name not in self.tool_registry.tools:
                raise ValueError(f"Unknown tool '{tool_name}' in raw plan")
            steps.append(
                Step(
                    id=item["id"],
                    tool=tool_name,
                    args=item.get("args", {}),
                    deps=item.get("deps", []),
                )
            )

        plan = Plan(task=task, steps=steps)
        plan.topological_order()
        return plan
