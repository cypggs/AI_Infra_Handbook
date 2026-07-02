"""Reflection mini demo package.

A CPU-runnable, pure-Python miniature of a reflection-based agent loop:
generator, critic, evaluator, workspace, observer, and revision loop.
"""

from reflection_mini.critic import CriticAgent
from reflection_mini.demo import run_demo
from reflection_mini.evaluator import Evaluator
from reflection_mini.generator import GeneratorAgent
from reflection_mini.llm_client import MockLLMClient
from reflection_mini.observer import Observer
from reflection_mini.reflection_loop import RevisionLoop
from reflection_mini.workspace import Workspace

__all__ = [
    "CriticAgent",
    "Evaluator",
    "GeneratorAgent",
    "MockLLMClient",
    "Observer",
    "RevisionLoop",
    "Workspace",
    "run_demo",
]
