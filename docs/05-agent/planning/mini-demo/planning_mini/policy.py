"""Policy enforces runtime constraints on plans and replanning."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set

from planning_mini.plan import Plan


@dataclass
class Policy:
    """Guardrails for plan size, tool set, budget, and replanning.

    Attributes:
        max_steps: Maximum number of steps allowed in a single plan.
        max_replans: Maximum number of times a failed plan may be replanned.
        budget_ceiling: Hard upper bound for any ``total`` value.
        allowed_tools: Optional set of permitted tool names. When ``None``,
            any registered tool is allowed.
    """

    max_steps: int = 10
    max_replans: int = 2
    budget_ceiling: float = 8000.0
    allowed_tools: Optional[Set[str]] = field(default=None)

    def validate(self, plan: Plan) -> None:
        """Validate a plan against size and allowed-tool constraints.

        Raises:
            ValueError: If the plan violates a policy.
        """
        if len(plan.steps) > self.max_steps:
            raise ValueError(
                f"Plan has {len(plan.steps)} steps, exceeding max_steps={self.max_steps}"
            )
        if self.allowed_tools is not None:
            for step in plan.steps:
                if step.tool not in self.allowed_tools:
                    raise ValueError(
                        f"Tool '{step.tool}' is not in the allowed tool set"
                    )

    def check_budget(self, total: float) -> bool:
        """Return ``True`` if ``total`` is within the budget ceiling."""
        return total <= self.budget_ceiling

    def can_replan(self, replan_count: int) -> bool:
        """Return ``True`` if another replan is still allowed."""
        return replan_count < self.max_replans
