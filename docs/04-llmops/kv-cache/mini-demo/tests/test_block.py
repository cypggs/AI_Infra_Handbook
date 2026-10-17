import pytest

from kv_cache_mini.block import BlockAllocator, BlockTable, OutOfBlocksError


class TestBlockAllocator:
    def test_alloc_returns_unique_blocks(self):
        alloc = BlockAllocator(num_blocks=4)
        assert alloc.alloc() != alloc.alloc()

    def test_alloc_sets_refcount_one(self):
        alloc = BlockAllocator(num_blocks=4)
        bid = alloc.alloc()
        assert alloc.refcount(bid) == 1

    def test_free_zero_refcount_keeps_block_cached(self):
        alloc = BlockAllocator(num_blocks=2)
        bid = alloc.alloc()
        alloc.free(bid)
        assert alloc.refcount(bid) == 0
        assert alloc.num_free == 1  # 归还空闲池前保持可逐出状态
        assert alloc.num_cached == 1

    def test_free_invalid_block_raises(self):
        alloc = BlockAllocator(num_blocks=2)
        with pytest.raises(KeyError):
            alloc.free(99)

    def test_double_free_raises(self):
        alloc = BlockAllocator(num_blocks=2)
        bid = alloc.alloc()
        alloc.free(bid)
        with pytest.raises(ValueError):
            alloc.free(bid)  # refcount 已为 0，再 free 应报错而非变负

    def test_share_increments_refcount(self):
        alloc = BlockAllocator(num_blocks=2)
        bid = alloc.alloc()
        alloc.share(bid)
        assert alloc.refcount(bid) == 2

    def test_cow_on_shared_block_copies(self):
        alloc = BlockAllocator(num_blocks=4)
        bid = alloc.alloc()
        alloc.share(bid)
        new = alloc.cow(bid)
        assert new != bid
        assert alloc.refcount(bid) == 1
        assert alloc.refcount(new) == 1
        assert alloc.copies == 1

    def test_cow_on_exclusive_block_returns_same(self):
        alloc = BlockAllocator(num_blocks=4)
        bid = alloc.alloc()
        assert alloc.cow(bid) == bid
        assert alloc.copies == 0

    def test_eviction_picks_lru_zero_refcount(self):
        alloc = BlockAllocator(num_blocks=2)
        a = alloc.alloc()
        x = alloc.alloc()
        alloc.free(a)   # a: refcount 0，touched 较早
        alloc.free(x)   # x: refcount 0，touched 较晚 → a 是 LRU
        victim = alloc.alloc()
        assert victim == a
        assert alloc.evictions == 1

    def test_out_of_blocks_when_all_referenced(self):
        alloc = BlockAllocator(num_blocks=1)
        alloc.alloc()
        with pytest.raises(OutOfBlocksError):
            alloc.alloc()

    def test_lru_touched_order_respected(self):
        alloc = BlockAllocator(num_blocks=2)
        a = alloc.alloc()
        b = alloc.alloc()
        alloc.free(a)
        alloc.free(b)
        alloc.share(a)  # a 重新被引用 → b 成为 LRU
        alloc.cow(a)    # 独占，原地返回并触碰 a
        victim = alloc.alloc()
        assert victim == b
        assert alloc.evictions == 1


class TestBlockTable:
    def test_append_spans_multiple_blocks(self):
        alloc = BlockAllocator(num_blocks=4, block_size=16)
        table = BlockTable(alloc)
        table.append_tokens(33)
        assert len(table.blocks) == 3
        assert table.capacity == 48

    def test_position_mapping(self):
        alloc = BlockAllocator(num_blocks=4, block_size=16)
        table = BlockTable(alloc)
        table.append_tokens(32)
        assert table.block_for_position(0) == table.block_for_position(15)
        assert table.block_for_position(16) == table.block_for_position(31)
        assert table.block_for_position(0) != table.block_for_position(16)

    def test_position_out_of_range(self):
        alloc = BlockAllocator(num_blocks=4, block_size=16)
        table = BlockTable(alloc)
        with pytest.raises(IndexError):
            table.block_for_position(0)

    def test_fork_shares_all_blocks(self):
        alloc = BlockAllocator(num_blocks=4, block_size=16)
        table = BlockTable(alloc)
        table.append_tokens(32)
        child = table.fork()
        assert child.blocks == table.blocks
        assert all(alloc.refcount(b) == 2 for b in table.blocks)

    def test_write_after_fork_cows_only_that_block(self):
        alloc = BlockAllocator(num_blocks=8, block_size=16)
        table = BlockTable(alloc)
        table.append_tokens(32)
        child = table.fork()
        new_bid = table.write(0)
        assert new_bid != child.blocks[0]
        assert table.blocks[1] == child.blocks[1]
        assert alloc.refcount(child.blocks[0]) == 1

    def test_release_drops_all_references(self):
        alloc = BlockAllocator(num_blocks=8, block_size=16)
        table = BlockTable(alloc)
        table.append_tokens(32)
        blocks = list(table.blocks)
        table.release()
        assert table.blocks == []
        assert all(alloc.refcount(b) == 0 for b in blocks)

    def test_write_auto_grows_table(self):
        alloc = BlockAllocator(num_blocks=8, block_size=16)
        table = BlockTable(alloc)
        table.write(40)  # 越过当前容量自动申请
        assert table.capacity >= 48
