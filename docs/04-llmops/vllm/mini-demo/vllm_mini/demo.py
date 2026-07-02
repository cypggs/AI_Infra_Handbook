"""Interactive demo of Mini vLLM."""

from __future__ import annotations

import time
from typing import List

import torch

from vllm_mini.paged_attention import BlockManager
from vllm_mini.scheduler import Scheduler, Sequence, SequenceGroup
from vllm_mini.worker import Worker


def run_demo():
    device = torch.device("cpu")
    vocab_size = 64
    hidden_size = 32
    block_size = 4
    num_blocks = 32
    max_output_len = 8

    block_manager = BlockManager(
        num_blocks=num_blocks,
        block_size=block_size,
        num_heads=4,
        head_size=hidden_size // 4,
        device=device,
    )
    scheduler = Scheduler(
        block_manager=block_manager,
        max_num_seqs=4,
        max_model_len=64,
    )
    worker = Worker(
        block_manager=block_manager,
        vocab_size=vocab_size,
        hidden_size=hidden_size,
        device=device,
    )

    # Simulate arriving requests.
    requests = [
        ("seq_0", [1, 2, 3, 4, 5]),
        ("seq_1", [10, 11, 12]),
        ("seq_2", [20, 21, 22, 23, 24, 25]),
        ("seq_3", [30, 31]),
    ]

    # Add first two immediately, delay the rest.
    all_groups: List[SequenceGroup] = []
    for i, (seq_id, prompt) in enumerate(requests[:2]):
        seq = Sequence(seq_id=seq_id, prompt_tokens=prompt, max_output_len=max_output_len)
        sg = SequenceGroup(group_id=f"g_{seq_id}", sequences=[seq])
        scheduler.add_seq_group(sg)
        all_groups.append(sg)

    iteration = 0
    while scheduler.has_unfinished_seqs():
        # Simulate later requests arriving at iteration 2 and 4.
        if iteration == 2:
            seq_id, prompt = requests[2]
            seq = Sequence(seq_id=seq_id, prompt_tokens=prompt, max_output_len=max_output_len)
            sg = SequenceGroup(group_id=f"g_{seq_id}", sequences=[seq])
            scheduler.add_seq_group(sg)
            all_groups.append(sg)
        if iteration == 4:
            seq_id, prompt = requests[3]
            seq = Sequence(seq_id=seq_id, prompt_tokens=prompt, max_output_len=max_output_len)
            sg = SequenceGroup(group_id=f"g_{seq_id}", sequences=[seq])
            scheduler.add_seq_group(sg)
            all_groups.append(sg)

        outputs = scheduler.schedule()
        if not outputs.scheduled_seq_groups:
            print(f"[Iter {iteration}] No sequences can be scheduled.")
            break

        # Run model.
        model_outputs = worker.execute_model(outputs.scheduled_seq_groups)
        scheduler.update_model_outputs(model_outputs)

        # Report.
        running_ids = [
            seq.seq_id
            for sg in outputs.scheduled_seq_groups
            for seq in sg.sequences
            if not seq.is_finished()
        ]
        finished_now = [
            seq.seq_id
            for sg in outputs.scheduled_seq_groups
            for seq in sg.sequences
            if seq.is_finished()
        ]
        used, total = block_manager.block_usage()
        print(
            f"[Iter {iteration}] running={running_ids}, "
            f"finished={finished_now}, blocks={used}/{total}"
        )

        iteration += 1
        time.sleep(0.05)

    print("\n=== Final outputs ===")
    for sg in all_groups:
        for seq in sg.sequences:
            print(f"{seq.seq_id}: prompt={seq.prompt_tokens} output={seq.output_tokens}")


if __name__ == "__main__":
    run_demo()
