"""A teaching implementation of a RadixAttention-style radix tree cache.

Real SGLang uses a high-performance C++/CUDA implementation. This pure-Python
version focuses on the algorithmic idea: token sequences are paths in a tree,
and longest-prefix matching lets different requests share KV cache for common
prefixes automatically.
"""

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


@dataclass
class RadixTreeNode:
    """One node in the radix tree.

    Each edge from parent to child is labelled with a single token id. The
    concatenation of edge labels from root to a node is the token sequence that
    node represents.
    """
    parent: Optional["RadixTreeNode"] = None
    children: dict = field(default_factory=dict)
    value: Any = None
    ref_count: int = 0

    def is_leaf(self) -> bool:
        return len(self.children) == 0


class RadixTree:
    """Radix tree for token-sequence prefix sharing.

    The tree stores KV-cache metadata per node. When a new request arrives we
    first try to match as much of its token sequence as possible against the
    existing tree. The matched prefix can be reused; only the remaining suffix
    needs fresh computation.
    """

    def __init__(self, max_nodes: int = 256):
        self.root = RadixTreeNode()
        self.max_nodes = max_nodes
        self._node_count = 1
        # Keeps nodes with a value in LRU order for eviction.
        self._lru: "OrderedDict[int, RadixTreeNode]" = OrderedDict()
        self._node_id_counter = 0

    def _lru_key(self, node: RadixTreeNode) -> int:
        """Return a stable integer key for the LRU map."""
        if not hasattr(node, "_lru_id"):
            node._lru_id = self._node_id_counter  # type: ignore
            self._node_id_counter += 1
        return node._lru_id  # type: ignore

    def match_prefix(self, token_ids: List[int]) -> Tuple[int, RadixTreeNode]:
        """Return (matched_length, node_at_that_position).

        Walks the tree following token_ids as long as the edges exist.
        """
        node = self.root
        matched = 0
        for tid in token_ids:
            child = node.children.get(tid)
            if child is None:
                break
            node = child
            matched += 1
        return matched, node

    def insert(self, token_ids: List[int], value: Any) -> RadixTreeNode:
        """Insert a token sequence into the tree, attaching ``value`` at the end.

        Already-existing prefix nodes are reused; only the suffix creates new
        nodes. The terminal node gets its reference count bumped and becomes
        the newest entry in the LRU list.
        """
        matched, node = self.match_prefix(token_ids)
        for tid in token_ids[matched:]:
            child = RadixTreeNode(parent=node)
            node.children[tid] = child
            node = child
            self._node_count += 1

        node.value = value
        node.ref_count += 1
        key = self._lru_key(node)
        self._lru[key] = node
        self._lru.move_to_end(key)
        self._evict_if_needed()
        return node

    def release(self, node: RadixTreeNode) -> None:
        """Decrease the reference count of a previously inserted terminal node."""
        if node is None:
            return
        node.ref_count = max(0, node.ref_count - 1)

    def _evict_if_needed(self) -> None:
        """Evict LRU leaf nodes with zero references when over capacity.

        After removing a leaf, also prune any ancestors that have become
        unreferenced leaves so internal dead branches do not linger.
        """
        while self._node_count > self.max_nodes:
            victim = None
            for key, node in self._lru.items():
                if node.ref_count == 0 and node.is_leaf():
                    victim = (key, node)
                    break
            if victim is None:
                break
            key, node = victim
            del self._lru[key]
            self._delete_node(node)

    def _delete_node(self, node: RadixTreeNode) -> None:
        """Remove a leaf node and recursively prune its now-empty ancestors."""
        while node is not None and node is not self.root:
            parent = node.parent
            if parent is not None:
                for edge_tid, child in list(parent.children.items()):
                    if child is node:
                        del parent.children[edge_tid]
                        break
            node.parent = None
            self._node_count -= 1
            # Stop pruning if the parent still has other children or is referenced.
            if (
                parent is None
                or parent is self.root
                or parent.ref_count > 0
                or not parent.is_leaf()
            ):
                break
            # If parent is in LRU, let the next eviction round handle it.
            if any(parent is n for n in self._lru.values()):
                break
            node = parent

    def prefix_match_rate(self, token_ids: List[int]) -> float:
        """Return the fraction of token_ids that already exists in the tree."""
        if not token_ids:
            return 0.0
        matched, _ = self.match_prefix(token_ids)
        return matched / len(token_ids)

    def __len__(self) -> int:
        return self._node_count

    def __repr__(self) -> str:
        return f"RadixTree(nodes={self._node_count}, max_nodes={self.max_nodes})"
