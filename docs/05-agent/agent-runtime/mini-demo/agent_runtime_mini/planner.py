"""Simple task planner."""

import re
from typing import List


class SimplePlanner:
    """Splits a user task into a handful of subgoals based on keywords."""

    def plan(self, task: str) -> List[str]:
        lowered = task.lower()
        subgoals = ["Understand the user request"]

        if any(word in lowered for word in ("calculate", "compute", "what is", "25*4+10")):
            subgoals.append("Use calculator to evaluate the expression")

        if "search" in lowered:
            subgoals.append("Use search to find relevant information")

        if re.search(r"read[_\s]?file", lowered) or "read" in lowered:
            subgoals.append("Use read_file to fetch the requested file")

        if re.search(r"write[_\s]?file", lowered) or "write" in lowered:
            subgoals.append("Use write_file to persist the result")

        subgoals.append("Return a clear final answer")
        return subgoals

    def __repr__(self) -> str:  # pragma: no cover
        return "SimplePlanner()"
