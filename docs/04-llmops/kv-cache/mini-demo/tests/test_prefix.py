from kv_cache_mini.prefix import RadixTree


class TestRadixMatch:
    def test_match_empty_tree(self):
        tree = RadixTree()
        assert tree.match([1, 2, 3]) == 0

    def test_insert_then_exact_match(self):
        tree = RadixTree()
        tokens = list(range(10))
        assert tree.insert(tokens) == 0
        assert tree.match(tokens) == 10

    def test_partial_prefix_match(self):
        tree = RadixTree()
        tree.insert([1, 2, 3, 4, 5])
        assert tree.match([1, 2, 3, 99]) == 3

    def test_no_common_prefix(self):
        tree = RadixTree()
        tree.insert([7, 8, 9])
        assert tree.match([1, 2]) == 0

    def test_shared_prefix_reuses_nodes(self):
        tree = RadixTree()
        tree.insert(list(range(20)))
        hit = tree.insert(list(range(20)) + [100, 200])
        assert hit == 20
        assert tree.num_nodes() == 3  # root + 公共段 + 分叉叶子

    def test_diverging_sequences_split(self):
        tree = RadixTree()
        tree.insert([1, 2, 3, 4])
        tree.insert([1, 2, 9, 9])
        assert tree.match([1, 2, 3, 4]) == 4
        assert tree.match([1, 2, 9, 9]) == 4
        assert tree.match([1, 2, 5]) == 2

    def test_total_tokens_counts_all_segments(self):
        tree = RadixTree()
        tree.insert(list(range(10)))
        tree.insert(list(range(10)) + list(range(20, 25)))
        assert tree.total_tokens() == 15


class TestRadixEviction:
    def test_evict_lru_frees_tokens(self):
        tree = RadixTree()
        tree.insert([1, 2, 3])
        tree.insert([9, 9, 9])
        freed = tree.evict_lru()
        assert freed == 3
        assert tree.total_tokens() == 3

    def test_evict_keeps_more_recently_used(self):
        tree = RadixTree()
        tree.insert([1, 2, 3])          # 较旧
        tree.insert([9, 9, 9])
        tree.match([1, 2, 3])           # 刷新 [1,2,3] 的访问时间
        tree.evict_lru()                # 应逐出 [9,9,9]
        assert tree.match([1, 2, 3]) == 3
        assert tree.match([9, 9, 9]) == 0

    def test_evict_only_removes_leaf_branch(self):
        tree = RadixTree()
        tree.insert(list(range(10)))
        tree.insert(list(range(10)) + [50])
        tree.evict_lru()  # 逐出较长的叶子
        assert tree.match(list(range(10))) == 10
        assert tree.match(list(range(10)) + [50]) == 10

    def test_evict_empty_tree_returns_zero(self):
        tree = RadixTree()
        assert tree.evict_lru() == 0

    def test_match_after_eviction_shrinks(self):
        tree = RadixTree()
        tree.insert(list(range(8)))
        tree.insert([100, 101])
        tree.evict_lru()
        tree.evict_lru()
        assert tree.total_tokens() == 0
        assert tree.match(list(range(8))) == 0
