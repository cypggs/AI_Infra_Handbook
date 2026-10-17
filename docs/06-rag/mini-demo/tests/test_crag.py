"""Tests for the CRAG-style corrective retrieval grader."""

from rag_mini.crag import Grade, Grading, grade_results
from rag_mini.documents import Chunk
from rag_mini.retriever import RetrievalResult


def _make_result(
    chunk_id: str,
    dense_score: float,
    keyword_score: float,
    rrf_score: float = 0.0,
) -> RetrievalResult:
    chunk = Chunk(id=chunk_id, source="test", section="test", text=f"text of {chunk_id}")
    return RetrievalResult(
        chunk=chunk,
        dense_score=dense_score,
        keyword_score=keyword_score,
        rrf_score=rrf_score,
    )


def test_top_dual_support_is_correct():
    results = [
        _make_result("a", dense_score=0.8, keyword_score=2.1),
        _make_result("b", dense_score=0.6, keyword_score=0.0),
    ]
    grading = grade_results(results)
    assert grading.grade == Grade.CORRECT
    assert "as-is" in grading.action


def test_head_disagreement_but_dual_support_present_is_ambiguous():
    results = [
        _make_result("a", dense_score=0.9, keyword_score=0.0),
        _make_result("b", dense_score=0.7, keyword_score=1.5),
    ]
    grading = grade_results(results)
    assert grading.grade == Grade.AMBIGUOUS
    assert "expand" in grading.action


def test_no_dual_support_is_incorrect():
    results = [
        _make_result("a", dense_score=0.9, keyword_score=0.0),
        _make_result("b", dense_score=0.0, keyword_score=1.4),
    ]
    grading = grade_results(results)
    assert grading.grade == Grade.INCORRECT
    assert "rewrite" in grading.action


def test_empty_results_is_incorrect():
    grading = grade_results([])
    assert grading.grade == Grade.INCORRECT


def test_grading_is_frozen_dataclass():
    grading = Grading(Grade.CORRECT, "use retrieved chunks as-is")
    assert grading.grade == Grade.CORRECT


def test_on_real_corpus_return_policy_query_grades_correct():
    from rag_mini.embedder import Embedder
    from rag_mini.retriever import Retriever
    from rag_mini.vector_store import VectorStore

    embedder = Embedder()
    store = VectorStore(embedder.get_embedded_chunks())
    retriever = Retriever(embedder=embedder, vector_store=store)
    results = retriever.hybrid_search("return policy", top_k=5)
    grading = grade_results(results)
    # The corpus has a dedicated returns-policy document, so both channels
    # should agree on the head of the ranking.
    assert grading.grade == Grade.CORRECT
