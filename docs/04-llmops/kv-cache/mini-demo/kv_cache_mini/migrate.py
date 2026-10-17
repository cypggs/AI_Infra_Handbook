"""Prefill/Decode 分离下的 KV 传输调度：流水线重叠模型。

PD 分离（Mooncake / NVIDIA Dynamo / vLLM KV connector / SGLang PD 分离）
把 prefill 与 decode 拆到不同 GPU 池，中间通过高速网络搬运 KV block：

- prefill 节点算出前缀各位置的 KV；
- decode 节点按 token 顺序消费这些 block 产出首 token 并继续 decode；
- 若等全部 KV 传完再开始 decode（串行），TTFT 被整个传输时间拖住；
- 按 block 流水线传输（block i+1 传输与 block i 的 decode 重叠），
  decode 只需等第一个 block 到达即可启动。

本模块用确定性的时间模型对比两种调度，并支持多流（multi-stream /
RDMA 多 QP）传输的建模。
"""

from __future__ import annotations


class TransferEngine:
    """KV block 传输引擎的带宽模型。

    - bandwidth_bytes_per_s: 单条流的有效带宽（RDMA/RoCE/IB 带宽 × 效率）；
    - num_streams: 并发传输流数（对应多 NIC 聚合、多 QP）；
    - overhead_s: 每条流的首包建链等固定开销。
    """

    def __init__(
        self,
        bandwidth_bytes_per_s: float,
        num_streams: int = 1,
        overhead_s: float = 0.0,
    ) -> None:
        if bandwidth_bytes_per_s <= 0:
            raise ValueError("bandwidth must be positive")
        if num_streams <= 0:
            raise ValueError("num_streams must be positive")
        self.bandwidth = bandwidth_bytes_per_s
        self.num_streams = num_streams
        self.overhead_s = overhead_s

    def block_transfer_time(self, block_bytes: float) -> float:
        """单个 block 在一条流上的传输时间（含流固定开销）。"""
        return block_bytes / self.bandwidth + self.overhead_s

    def arrival_times(self, num_blocks: int, block_bytes: float) -> list[float]:
        """block i 到达 decode 端的时刻。

        流 j 串行传输 block j, j+k, j+2k, ...（k = num_streams），
        block i 的到达时刻 = (i // k + 1) * 单块传输时间。
        """
        t = self.block_transfer_time(block_bytes)
        k = self.num_streams
        return [(i // k + 1) * t for i in range(num_blocks)]


class PDScheduler:
    """PD 分离 KV 传输调度：对比串行等待与流水线重叠两种模式。"""

    def __init__(
        self,
        engine: TransferEngine,
        num_blocks: int,
        block_bytes: float,
        decode_time_per_block: float = 0.0,
    ) -> None:
        if num_blocks < 0:
            raise ValueError("num_blocks must be non-negative")
        self.engine = engine
        self.num_blocks = num_blocks
        self.block_bytes = block_bytes
        self.decode_time_per_block = decode_time_per_block

    # ------------------------------------------------------------------
    @property
    def per_block_transfer_s(self) -> float:
        return self.engine.block_transfer_time(self.block_bytes)

    def sequential_ttft_s(self) -> float:
        """串行模式 TTFT：全部 KV 传完才开始 decode 第一个 block。"""
        return self.num_blocks * self.per_block_transfer_s + self.decode_time_per_block

    def simulate_pipelined(self) -> dict:
        """流水线模式：decode 按 block 到达顺序消费。

        返回 dict：
        - ttft_s: 首个 block 解码完成的时刻（首 token 延迟）；
        - makespan_s: 最后一个 block 解码完成的时刻；
        - arrivals: 各 block 到达时刻列表。
        """
        if self.num_blocks == 0:
            return {"ttft_s": 0.0, "makespan_s": 0.0, "arrivals": []}
        arrivals = self.engine.arrival_times(self.num_blocks, self.block_bytes)
        finish = 0.0
        for arrival in arrivals:
            start = max(arrival, finish)
            finish = start + self.decode_time_per_block
        ttft = arrivals[0] + self.decode_time_per_block
        return {"ttft_s": ttft, "makespan_s": finish, "arrivals": arrivals}

    def overlap_gain_s(self) -> float:
        """流水线相对串行的 TTFT 收益。"""
        pipelined = self.simulate_pipelined()["ttft_s"]
        return self.sequential_ttft_s() - pipelined

    def overlap_gain_ratio(self) -> float:
        seq = self.sequential_ttft_s()
        if seq == 0:
            return 0.0
        return self.overlap_gain_s() / seq
