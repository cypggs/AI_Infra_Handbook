"""Sample documents about Acme Corp and a simple overlapping chunker."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    """A single text chunk with metadata."""

    id: str
    text: str
    source: str
    section: str


# Sample documents about the fictional Acme Corp.
_RAW_DOCUMENTS: list[dict[str, str]] = [
    {
        "source": "acme-handbook",
        "section": "company-history",
        "text": (
            "Acme Corp was founded in 1985 by Jane Doe and John Smith. "
            "Originally a small hardware shop in Seattle, it grew into a global "
            "technology company with offices in over twenty countries. The "
            "company mission is to build reliable, affordable gadgets for "
            "everyday problem solving."
        ),
    },
    {
        "source": "acme-handbook",
        "section": "products",
        "text": (
            "Acme Corp offers a wide range of products including the Acme "
            "Smart Widget, Acme Power Bank, and Acme Home Hub. The Smart "
            "Widget is a modular sensor that monitors temperature, humidity, "
            "and motion. The Power Bank provides fast charging for up to five "
            "devices at once. The Home Hub connects all Acme devices through a "
            "single mobile app."
        ),
    },
    {
        "source": "support-policy",
        "section": "returns",
        "text": (
            "Acme Corp accepts returns within thirty days of purchase with the "
            "original receipt. Items must be unused and in original packaging. "
            "Refunds are processed to the original payment method within five "
            "to seven business days. Opened consumables, such as batteries and "
            "cleaning solution, are not eligible for return."
        ),
    },
    {
        "source": "support-policy",
        "section": "warranty",
        "text": (
            "All Acme electronics come with a one-year limited warranty "
            "covering manufacturing defects. Customers can extend coverage to "
            "three years by purchasing Acme Care. Warranty claims require a "
            "proof of purchase and a short diagnostic test. Damage from spills, "
            "drops, and unauthorized repairs is not covered."
        ),
    },
]


def chunk_text(
    text: str,
    chunk_size: int = 40,
    overlap: int = 10,
) -> list[str]:
    """Split text into overlapping word-level chunks.

    Args:
        text: Input text to chunk.
        chunk_size: Number of words per chunk.
        overlap: Number of words overlapping between consecutive chunks.

    Returns:
        A list of text chunks.

    Raises:
        ValueError: If overlap is not smaller than chunk_size.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    step = chunk_size - overlap
    start = 0
    while start < len(words):
        window = words[start : start + chunk_size]
        chunks.append(" ".join(window))
        if len(window) < chunk_size:
            break
        start += step

    return chunks


def load_chunks(
    chunk_size: int = 40,
    overlap: int = 10,
) -> list[Chunk]:
    """Load the Acme Corp documents as overlapping chunks.

    Args:
        chunk_size: Number of words per chunk.
        overlap: Number of words overlapping between consecutive chunks.

    Returns:
        A list of Chunk objects with unique IDs.
    """
    chunks: list[Chunk] = []
    for doc_index, doc in enumerate(_RAW_DOCUMENTS):
        raw_chunks = chunk_text(doc["text"], chunk_size=chunk_size, overlap=overlap)
        for chunk_index, text in enumerate(raw_chunks):
            chunk_id = f"{doc['section']}-{doc_index}-{chunk_index}"
            chunks.append(
                Chunk(
                    id=chunk_id,
                    text=text,
                    source=doc["source"],
                    section=doc["section"],
                )
            )
    return chunks
