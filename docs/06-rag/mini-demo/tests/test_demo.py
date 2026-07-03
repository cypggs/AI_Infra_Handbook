"""End-to-end test for the RAG demo."""

from rag_mini.demo import run_demo


def test_run_demo_returns_answer():
    answer = run_demo()
    assert isinstance(answer, str)
    assert len(answer) > 0


def test_run_demo_answers_return_policy():
    answer = run_demo()
    assert "thirty days" in answer
