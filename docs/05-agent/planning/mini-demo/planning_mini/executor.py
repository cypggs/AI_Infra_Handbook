"""PlanExecutor runs DAG steps, resolves argument references, and handles replans."""
from __future__ import annotations

from typing import Any, Dict

from planning_mini.llm_client import MockLLMClient
from planning_mini.observer import Observer
from planning_mini.plan import Plan, Step
from planning_mini.planner import TaskPlanner
from planning_mini.policy import Policy
from planning_mini.replan_trigger import ReplanTrigger
from planning_mini.tool_registry import ToolRegistry


class PlanExecutor:
    """Dependency-aware executor for :class:`Plan` objects.

    The executor repeatedly selects ready steps, runs them, and checks the
    :class:`ReplanTrigger`. When a recoverable failure is found and policy
    permits, it asks the LLM client for a new plan and continues execution.

    Attributes:
        tool_registry: Source of tool implementations.
        observer: Shared event trace.
        replan_trigger: Decides when to continue/replan/fail.
        policy: Runtime guardrails.
        planner: Converts LLM output into validated ``Plan`` objects.
        max_iterations: Safety cap on the execution loop.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        observer: Observer,
        replan_trigger: ReplanTrigger,
        policy: Policy,
        llm_client: MockLLMClient,
        max_iterations: int = 50,
    ) -> None:
        self.tool_registry = tool_registry
        self.observer = observer
        self.replan_trigger = replan_trigger
        self.policy = policy
        self.planner = TaskPlanner(llm_client, tool_registry)
        self.max_iterations = max_iterations

    def run(self, plan: Plan) -> Dict[str, Any]:
        """Execute ``plan`` to completion or failure.

        Returns:
            A result dictionary with keys ``success``, ``plan``,
            ``replan_count``, and optionally ``message``.
        """
        replan_count = 0

        for iteration in range(self.max_iterations):
            if plan.is_completed():
                self.observer.record(
                    "plan_completed",
                    message=f"计划在 {iteration} 次迭代后完成",
                )
                return {
                    "success": True,
                    "plan": plan,
                    "replan_count": replan_count,
                }

            ready = plan.ready_steps()
            if not ready:
                if plan.has_failed():
                    action = self.replan_trigger.decide(
                        plan, self.observer, replan_count
                    )
                    if action == "replan":
                        plan = self._replan(plan, replan_count)
                        replan_count += 1
                        continue
                    if action == "fail":
                        self.observer.record(
                            "plan_failed", message="触发器决定终止执行"
                        )
                        return {
                            "success": False,
                            "plan": plan,
                            "replan_count": replan_count,
                        }

                self.observer.record(
                    "plan_failed",
                    message="没有就绪步骤且无失败步骤，可能存在循环",
                )
                return {
                    "success": False,
                    "plan": plan,
                    "replan_count": replan_count,
                }

            # Execute every ready step. Because these steps are independent,
            # a production system could run them in parallel; here we run them
            # sequentially for simplicity and determinism.
            for step in ready:
                self._execute_step(step, plan)

            action = self.replan_trigger.decide(plan, self.observer, replan_count)
            if action == "replan":
                plan = self._replan(plan, replan_count)
                replan_count += 1
            elif action == "fail":
                self.observer.record("plan_failed", message="触发器决定终止执行")
                return {
                    "success": False,
                    "plan": plan,
                    "replan_count": replan_count,
                }

        self.observer.record("plan_failed", message="达到最大迭代次数")
        return {
            "success": False,
            "plan": plan,
            "replan_count": replan_count,
            "message": "max iterations reached",
        }

    def _execute_step(self, step: Step, plan: Plan) -> None:
        """Run a single step, resolve references, and update its status."""
        step.status = "running"
        self.observer.record(
            "step_started", step_id=step.id, message=f"开始执行 {step.tool}"
        )

        try:
            resolved_args = self._resolve_args(step.args, plan)
            result = self.tool_registry.execute(step.tool, resolved_args)
            step.result = result

            if isinstance(result, dict):
                if result.get("status") == "sold_out":
                    step.status = "failed"
                    step.observations.append("sold_out")
                    self.observer.record(
                        "step_failed",
                        step_id=step.id,
                        message=result.get("message", "航班售罄"),
                    )
                    return

            step.status = "completed"
            self.observer.record(
                "step_completed",
                step_id=step.id,
                message=f"完成 {step.tool}",
            )
        except Exception as exc:  # pragma: no cover - defensive
            step.status = "failed"
            step.observations.append(str(exc))
            self.observer.record(
                "step_failed",
                step_id=step.id,
                message=str(exc),
            )

    def _resolve_args(self, args: Dict[str, Any], plan: Plan) -> Dict[str, Any]:
        """Replace string argument values that reference completed steps.

        For example, ``{"flight_price": "search_flight"}`` becomes
        ``{"flight_price": search_flight_step.result}`` once ``search_flight``
        has completed.
        """
        mapping = plan.step_map()

        def resolve(value: Any) -> Any:
            if isinstance(value, str) and value in mapping:
                dep = mapping[value]
                if dep.status == "completed":
                    return dep.result
                raise ValueError(
                    f"Dependency '{value}' is not completed for argument resolution"
                )
            if isinstance(value, dict):
                return {k: resolve(v) for k, v in value.items()}
            if isinstance(value, list):
                return [resolve(v) for v in value]
            return value

        return {k: resolve(v) for k, v in args.items()}

    def _replan(self, plan: Plan, replan_count: int) -> Plan:
        """Request a new plan from the LLM and validate it."""
        failed_step = plan.failed_steps()[0]
        observation = (
            failed_step.observations[-1]
            if failed_step.observations
            else str(failed_step.result)
        )
        raw = self.planner.llm_client.replan(
            plan, failed_step.id, observation
        )
        new_plan = self.planner.create_plan_from_raw(plan.task, raw)
        self.policy.validate(new_plan)
        self.observer.record(
            "replan_executed",
            message=f"第 {replan_count + 1} 次 replan，生成 {len(new_plan.steps)} 步",
        )
        return new_plan
