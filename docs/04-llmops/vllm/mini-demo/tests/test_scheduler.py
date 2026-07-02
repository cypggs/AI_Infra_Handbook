"""Tests for Mini vLLM scheduler and block manager."""

import torch

from vllm_mini.paged_attention import BlockManager
from vllm_mini.scheduler import Scheduler, Sequence, SequenceGroup, SequenceStatus


def test_block_manager_allocation():
    bm = BlockManager(
        num_blocks=8,
        block_size=4,
        num_heads=2,
        head_size=8,
        device=torch.device("cpu"),
    )
    assert bm.num_free_blocks() == 8

    block_table = bm.allocate("seq_0", 5)
    assert len(block_table) == 2  # ceil(5 / 4)
    assert bm.num_free_blocks() == 6

    bm.append_slot("seq_0", 8)
    assert len(bm.get_block_table("seq_0")) == 3  # position 8 is in third block (0-indexed)

    bm.append_slot("seq_0", 9)
    assert len(bm.get_block_table("seq_0")) == 3

    bm.free("seq_0")
    assert bm.num_free_blocks() == 8


def test_scheduler_admission():
    bm = BlockManager(
        num_blocks=16,
        block_size=4,
        num_heads=2,
        head_size=8,
        device=torch.device("cpu"),
    )
    scheduler = Scheduler(block_manager=bm, max_num_seqs=2)

    seq = Sequence(seq_id="s0", prompt_tokens=[1, 2, 3, 4, 5], max_output_len=3)
    sg = SequenceGroup(group_id="g0", sequences=[seq])
    scheduler.add_seq_group(sg)

    outputs = scheduler.schedule()
    assert len(outputs.scheduled_seq_groups) == 1
    assert seq.status == SequenceStatus.RUNNING
    assert bm.num_free_blocks() == 14  # 2 blocks used


def test_continuous_batching():
    bm = BlockManager(
        num_blocks=64,
        block_size=4,
        num_heads=2,
        head_size=8,
        device=torch.device("cpu"),
    )
    scheduler = Scheduler(block_manager=bm, max_num_seqs=4)

    seq0 = Sequence(seq_id="s0", prompt_tokens=[1, 2, 3], max_output_len=2)
    seq1 = Sequence(seq_id="s1", prompt_tokens=[4, 5, 6, 7, 8], max_output_len=2)
    scheduler.add_seq_group(SequenceGroup(group_id="g0", sequences=[seq0]))
    scheduler.add_seq_group(SequenceGroup(group_id="g1", sequences=[seq1]))

    outputs = scheduler.schedule()
    assert len(outputs.scheduled_seq_groups) == 2

    # Simulate model generating token 9 for both sequences.
    scheduler.update_model_outputs({"s0": 9, "s1": 9})
    assert seq0.num_computed_tokens() == 4
    assert seq1.num_computed_tokens() == 6

    outputs = scheduler.schedule()
    assert len(outputs.scheduled_seq_groups) == 2

    # Finish both.
    scheduler.update_model_outputs({"s0": 10, "s1": 10})
    outputs = scheduler.schedule()
    assert len(outputs.scheduled_seq_groups) == 0
