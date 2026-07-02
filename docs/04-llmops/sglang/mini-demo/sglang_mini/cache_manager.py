"""A minimal KV-cache manager built on top of the radix tree.

The manager handles:
- prefix matching when a new request arrives,
- allocating (mock) KV blocks for the un-matched suffix,
- reclaiming references when a request finishes.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from sglang_mini.radix_tree import RadixTree, RadixTreeNode


@dataclass
class KVCacheEntry:
    """A dummy KV-cache entry.

    In real SGLang this would be a pointer to GPU memory blocks. Here we just
    store the token span and a synthetic tensor shape to keep the demo simple.
    """
    token_ids: Tuple[int, ...]
    num_heads: int = 4
    head_size: int = 8

    def __repr__(self) -> str:
        return f"KVCacheEntry(tokens={len(self.token_ids)}, shape=({self.num_heads}, {self.head_size}))"


@dataclass
class CacheContext:
    """Per-request cache state."""
    terminal_node: RadixTreeNode
    prefix_len: int
    suffix_tokens: List[int]
    suffix_entries: List[KVCacheEntry] = field(default_factory=list)


class RadixCacheManager:
    """Manages KV cache using a radix tree for automatic prefix sharing."""

    def __init__(self, max_nodes: int = 256, num_heads: int = 4, head_size: int = 8):
        self.tree = RadixTree(max_nodes=max_nodes)
        self.num_heads = num_heads
        self.head_size = head_size
        self._request_contexts: Dict[str, CacheContext] = {}
        self._hit_tokens = 0
        self._miss_tokens = 0

    def prepare_request(self, request_id: str, token_ids: List[int]) -> CacheContext:
        """Match prefix, allocate suffix entries, and return the cache context."""
        prefix_len, terminal_node = self.tree.match_prefix(token_ids)
        suffix_tokens = list(token_ids[prefix_len:])

        # Allocate suffix KV entries (one per token for simplicity).
        suffix_entries = [
            KVCacheEntry(
                token_ids=(tid,),
                num_heads=self.num_heads,
                head_size=self.head_size,
            )
            for tid in suffix_tokens
        ]

        ctx = CacheContext(
            terminal_node=terminal_node,
            prefix_len=prefix_len,
            suffix_tokens=suffix_tokens,
            suffix_entries=suffix_entries,
        )
        self._request_contexts[request_id] = ctx
        self._hit_tokens += prefix_len
        self._miss_tokens += len(suffix_tokens)
        return ctx

    def commit_request(self, request_id: str) -> None:
        """After a request finishes, insert its full sequence into the tree."""
        ctx = self._request_contexts.get(request_id)
        if ctx is None:
            return

        full_tokens = list(range(ctx.prefix_len)) + ctx.suffix_tokens
        # The real implementation would attach GPU block pointers; we attach
        # a summary object built from suffix entries.
        value = {
            "request_id": request_id,
            "prefix_len": ctx.prefix_len,
            "entries": ctx.suffix_entries,
        }
        # We re-use the matched terminal node as the insertion point by
        # inserting the suffix starting from the root. The tree naturally
        # reuses the matched prefix path.
        terminal = self.tree.insert(full_tokens, value)
        ctx.terminal_node = terminal

    def release_request(self, request_id: str) -> None:
        """Release the reference held by a committed request."""
        ctx = self._request_contexts.pop(request_id, None)
        if ctx and ctx.terminal_node is not None:
            self.tree.release(ctx.terminal_node)

    def hit_rate(self) -> float:
        total = self._hit_tokens + self._miss_tokens
        if total == 0:
            return 0.0
        return self._hit_tokens / total

    def stats(self) -> Dict[str, int]:
        return {
            "tree_nodes": len(self.tree),
            "hit_tokens": self._hit_tokens,
            "miss_tokens": self._miss_tokens,
        }

    def __repr__(self) -> str:
        return (
            f"RadixCacheManager(tree={self.tree}, "
            f"hit_rate={self.hit_rate():.2%})"
        )
