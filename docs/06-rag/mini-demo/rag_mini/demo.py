"""End-to-end RAG demo entry point."""

from __future__ import annotations

from rag_mini.embedder import Embedder
from rag_mini.generator import Generator
from rag_mini.retriever import Retriever
from rag_mini.reranker import Reranker
from rag_mini.vector_store import VectorStore


QUERY = "What is Acme Corp's return policy?"


def run_demo() -> str:
    """Run the full RAG pipeline on the sample return-policy query.

    Returns:
        The generated answer text.
    """
    # 1. Embed corpus and build the vector store.
    embedder = Embedder()
    vector_store = VectorStore(embedder.get_embedded_chunks())

    # 2. Retrieve candidates with hybrid search (dense + keyword fused by RRF).
    retriever = Retriever(embedder=embedder, vector_store=vector_store)
    candidates = retriever.hybrid_search(QUERY, top_k=3)

    # 3. Rerank the fused candidates.
    reranker = Reranker()
    ranked = reranker.rerank(QUERY, candidates)

    # 4. Generate an answer from the top-ranked chunks.
    generator = Generator()
    context = [r.chunk for r in ranked]
    answer = generator.generate(QUERY, context)

    # 5. Print a concise trace.
    print("Question:", QUERY)
    print("\nRetrieved chunks:")
    for i, chunk in enumerate(answer.sources, start=1):
        print(f"  {i}. [{chunk.section}] {chunk.text[:100]}...")
    print("\nAnswer:", answer.text)

    return answer.text


if __name__ == "__main__":
    run_demo()
