"""Console demo for the reflection mini package."""

from reflection_mini.critic import CriticAgent
from reflection_mini.evaluator import Evaluator
from reflection_mini.generator import GeneratorAgent
from reflection_mini.llm_client import MockLLMClient
from reflection_mini.observer import Observer
from reflection_mini.reflection_loop import RevisionLoop
from reflection_mini.workspace import Workspace


def run_demo() -> None:
    """Run the agent-reflection demo scenario and print the results."""
    request = "Explain Agent Reflection in one paragraph"

    llm_client = MockLLMClient()
    workspace = Workspace()
    observer = Observer()

    generator = GeneratorAgent(llm_client)
    critic = CriticAgent(llm_client)
    evaluator = Evaluator(llm_client)

    loop = RevisionLoop(
        generator=generator,
        critic=critic,
        evaluator=evaluator,
        workspace=workspace,
        observer=observer,
        max_iterations=3,
        score_threshold=1.0,
    )

    result = loop.run(request)

    print("=" * 60)
    print("Reflection Mini Demo")
    print("=" * 60)
    print(f"Request: {request}")
    print(f"Iterations run: {result['iterations_run']}")
    print(f"Passed: {result['passed']}")
    print("-" * 60)
    print("Workspace contents:")
    for key, value in sorted(result["workspace"].items()):
        print(f"  {key}: {value!r}")
    print("-" * 60)
    observer.print_trace()
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
