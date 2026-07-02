"""Reflection/revision loop orchestrating generator, critic, and evaluator."""

from typing import Any

from reflection_mini.critic import CriticAgent
from reflection_mini.evaluator import Evaluator
from reflection_mini.generator import GeneratorAgent
from reflection_mini.observer import Observer
from reflection_mini.workspace import Workspace


class RevisionLoop:
    """Repeatedly generate, critique, and evaluate until the draft passes."""

    def __init__(
        self,
        generator: GeneratorAgent,
        critic: CriticAgent,
        evaluator: Evaluator,
        workspace: Workspace,
        observer: Observer,
        max_iterations: int = 3,
        score_threshold: float = 1.0,
    ) -> None:
        """Create a reflection loop.

        Args:
            generator: Agent that produces drafts.
            critic: Agent that critiques drafts.
            evaluator: Agent that scores draft/critique pairs.
            workspace: Shared workspace for artifacts.
            observer: Event recorder for observability.
            max_iterations: Upper bound on revision rounds.
            score_threshold: Minimum score that counts as a pass.
        """
        self.generator = generator
        self.critic = critic
        self.evaluator = evaluator
        self.workspace = workspace
        self.observer = observer
        self.max_iterations = max_iterations
        self.score_threshold = score_threshold

    def run(self, request: str) -> dict[str, Any]:
        """Execute the reflection loop for ``request``.

        Args:
            request: The user's instruction.

        Returns:
            A summary containing the final workspace state, the observer
            trace, the number of iterations run, and whether the loop passed.
        """
        self.observer.record("loop_start", request=request)

        for iteration in range(self.max_iterations):
            self.observer.record("generate", iteration=iteration)
            draft = self.generator.produce(request, self.workspace, iteration)

            self.observer.record("critique", iteration=iteration, draft=draft)
            critique = self.critic.evaluate(draft, self.workspace)

            self.observer.record(
                "evaluate", iteration=iteration, critique=critique
            )
            result = self.evaluator.score(draft, critique, self.workspace)

            score = float(result.get("score", 0.0))
            verdict = result.get("verdict", "fail")

            if score >= self.score_threshold and verdict == "pass":
                self.workspace.write("final_draft", draft)
                self.observer.record(
                    "finalize",
                    reason="passed",
                    iterations_run=iteration + 1,
                    final_draft=draft,
                )
                return {
                    "workspace": self.workspace.to_dict(),
                    "trace": self.observer.events,
                    "iterations_run": iteration + 1,
                    "passed": True,
                }

        final_draft = self.workspace.read("latest_draft")
        self.workspace.write("final_draft", final_draft)
        self.observer.record(
            "finalize",
            reason="max_iterations",
            iterations_run=self.max_iterations,
            final_draft=final_draft,
        )
        return {
            "workspace": self.workspace.to_dict(),
            "trace": self.observer.events,
            "iterations_run": self.max_iterations,
            "passed": False,
        }
