"""Demo entry point: plan a Beijing->Tokyo trip with a sold-out flight replan."""
from __future__ import annotations

from typing import Any

from planning_mini.executor import PlanExecutor
from planning_mini.llm_client import MockLLMClient
from planning_mini.observer import Observer
from planning_mini.planner import TaskPlanner
from planning_mini.policy import Policy
from planning_mini.replan_trigger import ReplanTrigger
from planning_mini.tool_registry import ToolRegistry


class DemoResult(int):
    """Return value for ``run_demo()``.

    Subclassing ``int`` lets the ``planning-demo`` console entry point exit
    cleanly (0 on success, 1 on failure) while still supporting dict-style
    access for programmatic tests.
    """

    def __new__(cls, success: bool, plan: Any, replan_count: int):
        value = 0 if success else 1
        obj = super().__new__(cls, value)
        obj._success = success
        obj._plan = plan
        obj._replan_count = replan_count
        return obj

    def __getitem__(self, key: str) -> Any:
        if key == "success":
            return self._success
        if key == "plan":
            return self._plan
        if key == "replan_count":
            return self._replan_count
        raise KeyError(key)

    def __repr__(self) -> str:
        return (
            f"DemoResult(success={self._success}, "
            f"replan_count={self._replan_count})"
        )


def run_demo() -> DemoResult:
    """Run the travel-planning mini demo and print a human-readable trace.

    The demo deliberately sets ``sold_out=True`` on the flight tool so the
    executor exercises the failure->replan->success path. After the replan,
    an alternative direct flight is used and a final itinerary is generated.
    """
    task = "帮我规划一次 北京→东京 3 天旅行，预算 8000 元"

    registry = ToolRegistry()
    # First attempt: outbound flight is sold out to trigger replanning.
    registry.sold_out = True

    llm_client = MockLLMClient()
    planner = TaskPlanner(llm_client, registry)
    policy = Policy(
        max_steps=10,
        max_replans=2,
        budget_ceiling=8000.0,
        allowed_tools=set(registry.tools.keys()),
    )
    observer = Observer()
    trigger = ReplanTrigger(policy)
    executor = PlanExecutor(
        registry,
        observer,
        trigger,
        policy,
        llm_client,
    )

    print("=" * 60)
    print("Planning Mini Demo")
    print("=" * 60)
    print(f"Task: {task}\n")

    plan = planner.create_plan(task)
    print("Initial plan steps (topological order):")
    for step in plan.topological_order():
        deps = f"  deps={step.deps}" if step.deps else ""
        print(f"  - {step.id}: {step.tool}{deps}")
    print()

    result = executor.run(plan)
    final_plan = result["plan"]

    print("Execution trace:")
    for event in observer.events:
        step_part = f"[{event['step_id']}] " if event["step_id"] else ""
        print(f"  {step_part}{event['event_type']}: {event['message']}")
    print()

    if result["success"]:
        itinerary_step = final_plan.steps[-1]
        print(f"Final result (after {result['replan_count']} replan(s)):")
        print(f"  {itinerary_step.result}")
    else:
        print("Demo ended in failure.")
        print(f"  Replan count: {result['replan_count']}")
        if result.get("message"):
            print(f"  Reason: {result['message']}")

    print("=" * 60)
    return DemoResult(
        success=result["success"],
        plan=final_plan,
        replan_count=result["replan_count"],
    )


if __name__ == "__main__":
    run_demo()
