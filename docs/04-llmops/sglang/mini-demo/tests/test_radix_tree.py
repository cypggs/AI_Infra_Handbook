"""Tests for the RadixAttention-style radix tree."""

import pytest

from sglang_mini.radix_tree import RadixTree


def test_basic_insert_and_match():
    tree = RadixTree(max_nodes=100)
    tokens = [1, 2, 3, 4]
    node = tree.insert(tokens, "kv-1234")
    assert node.value == "kv-1234"

    matched, n = tree.match_prefix([1, 2, 3, 4, 5])
    assert matched == 4
    assert n is node


def test_prefix_sharing():
    tree = RadixTree(max_nodes=100)
    tree.insert([1, 2, 3, 4], "a")
    tree.insert([1, 2, 3, 5], "b")

    # Both sequences share the prefix [1, 2, 3].
    for seq in ([1, 2, 3, 4], [1, 2, 3, 5]):
        matched, _ = tree.match_prefix(seq)
        assert matched == 4  # the full stored sequence is matched

    assert len(tree) == 6  # root + 1 + 2 + 3 + 4 + 5


def test_eviction_removes_unreferenced_leaves():
    tree = RadixTree(max_nodes=5)
    tree.insert([1, 2, 3, 4], "x")
    tree.release(tree.root.children[1].children[2].children[3].children[4])
    # Force an insertion to trigger eviction.
    tree.insert([10, 11, 12, 13], "y")
    # The unreferenced leaf path 1-2-3-4 should be pruned.
    matched, _ = tree.match_prefix([1, 2, 3, 4])
    assert matched == 0


def test_ref_count_keeps_shared_prefix():
    tree = RadixTree(max_nodes=10)
    n1 = tree.insert([1, 2, 3], "a")
    n2 = tree.insert([1, 2, 3], "b")
    assert n1 is n2
    assert n1.ref_count == 2

    tree.release(n1)
    tree.release(n2)
    assert n1.ref_count == 0
