"""ReplanTrigger decides whether to continue, replan, or fail."""
from __future__ import annotations

from typing import Any

from planning_mini.observer import Observer
from planning_mini.plan import Plan
from planning_mini.policy import Policy


class ReplanTrigger:
    """Inspects observations and plan state to choose the next action."""

    def __init__(self, policy: Policy) -> None:
        self.policy = policy

    def decide(self, plan: Plan, observer: Observer, replan_count: int) -> str:
        """Return one of ``continue``, ``replan``, or ``fail``.

        The trigger looks for:

        * A failed ``search_flight`` step reporting ``sold_out``.
        * A completed ``check_policy`` step reporting ``approved=False``.

        If a recoverable issue is found and the policy still allows replanning,
        ``replan`` is returned. If the issue is recoverable but the replan
        budget is exhausted, ``fail`` is returned. Otherwise ``continue``.
        """
        for step in plan.failed_steps():
            if step.tool == "search_flight":
                result = step.result
                if isinstance(result, dict) and result.get("status") == "sold_out":
                    if self.policy.can_replan(replan_count):
                        observer.record(
                            "replan_decision",
                            step_id=step.id,
                            message="航班售罄，触发 replan",
                        )
                        return "replan"
                    observer.record(
                        "plan_failed",
                        step_id=step.id,
                        message="航班售罄且 replan 次数耗尽",
                    )
                    return "fail"

        for step in plan.steps:
            if step.status != "completed" or step.tool != "check_policy":
                continue
            result = step.result
            if isinstance(result, dict) and result.get("approved") is False:
                if self.policy.can_replan(replan_count):
                    observer.record(
                        "replan_decision",
                        step_id=step.id,
                        message="超出预算，触发 replan",
                    )
                    return "replan"
                observer.record(
                    "plan_failed",
                    step_id=step.id,
                    message="超出预算且 replan 次数耗尽",
                )
                return "fail"

        return "continue"
