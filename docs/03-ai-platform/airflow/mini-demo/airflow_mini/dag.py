"""DAG, Task and Operator abstractions."""

from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, List


class DeferSignal(Exception):
    """Raised by a deferrable operator to signal it should enter deferred state."""


class BaseOperator:
    """Base class for operators."""

    def __init__(self, task_id: str, retries: int = 0, **kwargs):
        self.task_id = task_id
        self.retries = retries
        self.kwargs = kwargs

    def execute(self, context: dict) -> Any:
        raise NotImplementedError


class PythonOperator(BaseOperator):
    """Execute a Python callable."""

    def __init__(self, task_id: str, python_callable: Callable, **kwargs):
        super().__init__(task_id, **kwargs)
        self.python_callable = python_callable

    def execute(self, context: dict) -> Any:
        return self.python_callable(context)


class BashOperator(BaseOperator):
    """Simulate a bash command by echoing it."""

    def __init__(self, task_id: str, bash_command: str, **kwargs):
        super().__init__(task_id, **kwargs)
        self.bash_command = bash_command

    def execute(self, context: dict) -> Any:
        return {"command": self.bash_command, "status": "ok"}


class WaitFileOperator(BaseOperator):
    """Deferrable operator that waits for a file to be ready."""

    def __init__(self, task_id: str, filepath: str, **kwargs):
        super().__init__(task_id, **kwargs)
        self.filepath = filepath

    def execute(self, context: dict) -> Any:
        triggerer = context.get("triggerer")
        if triggerer is not None and triggerer.is_ready(self.filepath):
            return {"filepath": self.filepath, "ready": True}
        if triggerer is not None:
            triggerer.register(self.filepath, context)
        raise DeferSignal()


@dataclass
class Task:
    task_id: str
    operator: BaseOperator
    upstream: List["Task"] = field(default_factory=list)
    downstream: List["Task"] = field(default_factory=list)

    def __rshift__(self, other: "Task") -> "Task":
        if other is self:
            raise ValueError("Cannot depend on self")
        if other not in self.downstream:
            self.downstream.append(other)
        if self not in other.upstream:
            other.upstream.append(self)
        return other


@dataclass
class DAG:
    dag_id: str
    schedule: str = "@daily"
    tasks: dict[str, Task] = field(default_factory=dict)

    def add_task(self, operator: BaseOperator) -> Task:
        """Wrap an operator in a Task and register it."""
        task = Task(task_id=operator.task_id, operator=operator)
        self.tasks[task.task_id] = task
        return task

    def topo_order(self) -> List[Task]:
        """Return tasks in topological order using Kahn's algorithm."""
        in_degree = {t.task_id: len(t.upstream) for t in self.tasks.values()}
        queue = [t for t in self.tasks.values() if in_degree[t.task_id] == 0]
        result: List[Task] = []
        visited: set[str] = set()

        while queue:
            task = queue.pop(0)
            if task.task_id in visited:
                continue
            visited.add(task.task_id)
            result.append(task)
            for down in task.downstream:
                in_degree[down.task_id] -= 1
                if in_degree[down.task_id] == 0:
                    queue.append(down)

        if len(result) != len(self.tasks):
            raise ValueError("Cycle detected in DAG dependencies")
        return result

    def iter_tasks(self) -> Iterator[Task]:
        return iter(self.topo_order())
