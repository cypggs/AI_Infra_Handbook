"""Plan dataclasses: DAG-aware steps, topological ordering, and status tracking."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Step:
    """A single unit of work inside a plan.

    Attributes:
        id: Unique identifier used by dependencies.
        tool: Name of the registered tool to execute.
        args: Keyword arguments passed to the tool. String values that match a
            dependency step id are resolved at execution time.
        deps: List of step ids that must complete before this step runs.
        status: One of ``pending``, ``running``, ``completed``, or ``failed``.
        result: Value returned by the tool execution.
        observations: Human-readable notes collected during execution.
    """

    id: str
    tool: str
    args: Dict[str, Any] = field(default_factory=dict)
    deps: List[str] = field(default_factory=list)
    status: str = "pending"
    result: Any = None
    observations: List[str] = field(default_factory=list)

    def reset(self) -> None:
        """Return the step to a fresh pending state."""
        self.status = "pending"
        self.result = None
        self.observations = []


@dataclass
class Plan:
    """A collection of steps that form a directed acyclic graph (DAG).

    Attributes:
        task: Natural-language description of the goal.
        steps: Ordered list of :class:`Step` objects.
    """

    task: str
    steps: List[Step]

    def step_map(self) -> Dict[str, Step]:
        """Return a mapping from step id to step, checking for duplicates."""
        mapping: Dict[str, Step] = {}
        for step in self.steps:
            if step.id in mapping:
                raise ValueError(f"Duplicate step id: {step.id}")
            mapping[step.id] = step
        return mapping

    def topological_order(self) -> List[Step]:
        """Return steps sorted in dependency-respecting order.

        Raises:
            ValueError: If a dependency is unknown or the graph contains a cycle.
        """
        mapping = self.step_map()
        in_degree = {step.id: 0 for step in self.steps}
        for step in self.steps:
            for dep in step.deps:
                if dep not in mapping:
                    raise ValueError(f"Unknown dependency '{dep}' in step '{step.id}'")
                in_degree[step.id] += 1

        ready = [step for step in self.steps if in_degree[step.id] == 0]
        ready.sort(key=lambda s: self.steps.index(s))
        ordered: List[Step] = []

        while ready:
            current = ready.pop(0)
            ordered.append(current)
            for step in self.steps:
                if current.id in step.deps:
                    in_degree[step.id] -= 1
                    if in_degree[step.id] == 0:
                        ready.append(step)
                        ready.sort(key=lambda s: self.steps.index(s))

        if len(ordered) != len(self.steps):
            raise ValueError("Cycle detected in plan dependencies")

        return ordered

    def ready_steps(self) -> List[Step]:
        """Return pending steps whose dependencies are all completed."""
        completed = {step.id for step in self.steps if step.status == "completed"}
        ready: List[Step] = []
        for step in self.steps:
            if step.status != "pending":
                continue
            if all(dep in completed for dep in step.deps):
                ready.append(step)
        return ready

    def is_completed(self) -> bool:
        """True when every step has finished successfully."""
        return all(step.status == "completed" for step in self.steps)

    def has_failed(self) -> bool:
        """True when at least one step has failed."""
        return any(step.status == "failed" for step in self.steps)

    def failed_steps(self) -> List[Step]:
        """Return all steps currently marked as failed."""
        return [step for step in self.steps if step.status == "failed"]
