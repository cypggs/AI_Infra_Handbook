"""Minimal Byte Pair Encoding (BPE) tokenizer.

This is an educational implementation designed to fit in a single file and run on
CPU. It starts from UTF-8 byte tokens and performs a fixed number of greedy
pair merges, exactly the idea used by GPT-2 / RoBERTa style tokenizers.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple


# Special token used to delimit examples in the training corpus.
ENDOFTEXT = "<|endoftext|>"


def _encode_bytes(text: str) -> List[int]:
    """Encode text into the list of UTF-8 byte values."""
    return list(text.encode("utf-8"))


def _decode_bytes(ids: List[int]) -> str:
    """Decode a list of byte values back into a Python string."""
    return bytes(ids).decode("utf-8", errors="replace")


def _most_frequent_pair(token_ids: List[int]) -> Tuple[int, int]:
    """Return the most frequent adjacent pair in ``token_ids``."""
    counts: Dict[Tuple[int, int], int] = {}
    for a, b in zip(token_ids, token_ids[1:]):
        counts[(a, b)] = counts.get((a, b), 0) + 1
    if not counts:
        # Cannot happen for a non-empty sequence, but keep the type checker happy.
        return (token_ids[0], token_ids[0])
    return max(counts, key=counts.get)  # type: ignore[arg-type]


def _merge(ids: List[int], pair: Tuple[int, int], new_id: int) -> List[int]:
    """Replace every occurrence of ``pair`` in ``ids`` with ``new_id``."""
    merged: List[int] = []
    i = 0
    a, b = pair
    while i < len(ids):
        if i < len(ids) - 1 and ids[i] == a and ids[i + 1] == b:
            merged.append(new_id)
            i += 2
        else:
            merged.append(ids[i])
            i += 1
    return merged


class BPETokenizer:
    """A tiny BPE tokenizer.

    Training produces ``num_merges`` merge rules on top of the initial byte
    vocabulary. The vocabulary starts at 256 (one id per byte). After training
    it contains ``256 + num_merges`` tokens, plus one reserved id for the
    ``<|endoftext|>`` special token.

    Args:
        num_merges: Number of byte-pair merges to learn.
    """

    def __init__(self, num_merges: int = 100):
        self.num_merges = num_merges
        # Mapping from byte ids (0..255) to single characters.  The actual
        # decoding happens via bytes(ids).decode(...), this is just a fallback
        # for pretty inspection.
        self.byte_vocab: Dict[int, bytes] = {i: bytes([i]) for i in range(256)}
        # Merge rules: pair -> new token id.
        self.merges: Dict[Tuple[int, int], int] = {}
        # Complete vocabulary: id -> bytes/merge token representation.
        self.vocab: Dict[int, bytes] = dict(self.byte_vocab)
        # Special token id is always the last id, reserved after training.
        self.eot_id: int | None = None

    def train(self, text: str) -> "BPETokenizer":
        """Train the tokenizer on ``text`` and return self."""
        # Convert the raw text to byte ids.
        ids = _encode_bytes(text)

        # Build initial vocabulary and merge table.
        next_id = 256
        for _ in range(self.num_merges):
            if len(ids) < 2:
                break
            pair = _most_frequent_pair(ids)
            if pair not in self.merges:
                self.merges[pair] = next_id
                # Vocab entry is just the concatenation of its two parts.
                self.vocab[next_id] = self.vocab[pair[0]] + self.vocab[pair[1]]
                next_id += 1
            ids = _merge(ids, pair, self.merges[pair])

        # Reserve one id for the end-of-text token.
        self.eot_id = next_id
        self.vocab[self.eot_id] = ENDOFTEXT.encode("utf-8")
        return self

    def encode(self, text: str) -> List[int]:
        """Encode ``text`` into a list of token ids.

        The ``<|endoftext|>`` literal is mapped to the reserved special id.
        """
        # Split on the special token so it never participates in BPE merging.
        if self.eot_id is None:
            raise RuntimeError("Tokenizer must be trained before encode() is called.")

        parts = text.split(ENDOFTEXT)
        result: List[int] = []
        for i, part in enumerate(parts):
            if i > 0:
                result.append(self.eot_id)
            ids = _encode_bytes(part)
            # Apply merges in the exact order they were learned.
            for pair, new_id in self.merges.items():
                ids = _merge(ids, pair, new_id)
            result.extend(ids)
        return result

    def decode(self, ids: Iterable[int]) -> str:
        """Decode a list of token ids back into a string."""
        if self.eot_id is None:
            raise RuntimeError("Tokenizer must be trained before decode() is called.")

        bytes_parts: List[bytes] = []
        for token_id in ids:
            if token_id == self.eot_id:
                bytes_parts.append(ENDOFTEXT.encode("utf-8"))
            elif token_id in self.vocab:
                bytes_parts.append(self.vocab[token_id])
            else:
                # Unknown id: replace with the Unicode replacement character.
                bytes_parts.append(b"\xef\xbf\xbd")
        return b"".join(bytes_parts).decode("utf-8", errors="replace")

    @property
    def vocab_size(self) -> int:
        """Current vocabulary size including the special token."""
        return len(self.vocab)


def train_tokenizer(text: str, num_merges: int = 100) -> BPETokenizer:
    """Convenience helper: create and train a ``BPETokenizer``."""
    return BPETokenizer(num_merges=num_merges).train(text)
