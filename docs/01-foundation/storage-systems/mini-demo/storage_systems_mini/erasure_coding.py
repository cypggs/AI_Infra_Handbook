"""Simple XOR erasure coding simulator."""

from typing import List, Optional


class SimpleXORCodec:
    """Split bytes into k equal-sized data chunks and produce 1 XOR parity chunk.

    Can recover any single lost chunk from the remaining k chunks.
    """

    def __init__(self, k: int = 3):
        if k < 2:
            raise ValueError("k must be at least 2")
        self.k = k

    def encode(self, data: bytes) -> List[bytes]:
        """Return k data chunks + 1 parity chunk."""
        if not data:
            return [b""] * (self.k + 1)
        # Prefix a 4-byte length so trailing zeros in the payload are preserved.
        payload = len(data).to_bytes(4, "big") + data
        pad = (self.k - len(payload) % self.k) % self.k
        padded = payload + b"\x00" * pad
        chunk_size = len(padded) // self.k
        chunks = [padded[i * chunk_size : (i + 1) * chunk_size] for i in range(self.k)]
        parity = bytearray(chunk_size)
        for chunk in chunks:
            for i, byte in enumerate(chunk):
                parity[i] ^= byte
        chunks.append(bytes(parity))
        return chunks

    def decode(self, chunks: List[Optional[bytes]]) -> bytes:
        """Reconstruct original bytes even if exactly one chunk is missing."""
        if len(chunks) != self.k + 1:
            raise ValueError(f"expected {self.k + 1} chunks, got {len(chunks)}")
        present = [i for i, c in enumerate(chunks) if c is not None]
        if len(present) < self.k:
            raise RuntimeError("too many chunks missing")
        if len(chunks) - len(present) > 1:
            raise RuntimeError("this codec can only recover one missing chunk")

        chunk_size = len(next(c for c in chunks if c is not None))
        reconstructed = list(chunks)
        if len(present) == self.k + 1:
            result = bytearray(chunk_size)
            for chunk in reconstructed:
                for i, byte in enumerate(chunk):
                    result[i] ^= byte
            # parity XOR all data = zero for valid input
            if any(result):
                raise RuntimeError("parity check failed")
            data = b"".join(reconstructed[:-1])
        else:
            missing = next(i for i, c in enumerate(chunks) if c is None)
            filler = bytearray(chunk_size)
            for i, chunk in enumerate(reconstructed):
                if chunk is None or i == missing:
                    continue
                for j, byte in enumerate(chunk):
                    filler[j] ^= byte
            reconstructed[missing] = bytes(filler)
            data = b"".join(reconstructed[:-1])

        if len(data) < 4:
            return b""
        length = int.from_bytes(data[:4], "big")
        return data[4 : 4 + length]
