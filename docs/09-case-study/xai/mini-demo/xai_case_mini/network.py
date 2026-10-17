"""单一大集群 vs 多园区拓扑的通信模型，及 RoCE vs IB 的效率假设对比。

对应 xAI Colossus 案例的核心赌注：
"把 10 万卡放进同一个园区、同一个训练域（single training domain），
AllReduce 全部走园区内部高带宽 fabric；而不是跨园区用 DCI 链路做
同步训练。"

模型（ring AllReduce，一阶近似）：
- 单集群：N 张卡一个 ring，步数 2*(N-1)，每步传 message/N 字节。
- 双园区：层次化——先做本地 reduce-scatter + all-gather（每 GPU 本地
  字节量 ≈ 2·msg，与单集群 ring 同量级，用同一个 ring 模型近似），
  再付出跨园区段的固定代价：msg 字节过 DCI 链路 + 2×WAN RTT。
  关键结论：惩罚随消息（=模型）大小线性增长，而 DCI 带宽不随模型增长，
  所以"模型越大，跨园区同步越痛"——这正是单训练域赌注的依据。

效率假设来自 NVIDIA 官方数字（Spectrum-X 新闻稿）：
- Spectrum-X（RoCE 增强）：Grok 训练实测 95% 吞吐、零丢包
- 传统以太网 RoCE：约 60% 吞吐（官方对比口径）
- InfiniBand：约 95%（行业经验值）
"""

from dataclasses import dataclass

# fabric 效率（有效带宽 / 标称带宽）——教学用假设，出处见模块 docstring
FABRIC_EFFICIENCY = {
    "infiniband": 0.95,
    "spectrum-x": 0.95,
    "ethernet-legacy": 0.60,
}

# 典型注入带宽假设（bit/s，每 GPU 摊到的 scale-out 网络带宽）
DEFAULT_PER_GPU_BPS = 400e9  # 800Gb/s 端口对分 8 卡服务器的数量级
DEFAULT_RTT_LOCAL = 20e-6    # 园区内部 RTT（秒）
DEFAULT_DCI_BPS = 1.6e12     # 园区间 DCI 链路 1.6 Tbps
DEFAULT_WAN_RTT = 5e-3       # 跨园区 RTT（毫秒级）


def ring_allreduce_time(n_gpus: int, message_bytes: float, per_gpu_bps: float,
                        efficiency: float = 0.95, rtt_s: float = DEFAULT_RTT_LOCAL) -> float:
    """Ring AllReduce 耗时（秒），一阶模型。

    步数 = 2*(N-1)；每步传输 message/N 字节；每步耗时 = 传输时 + RTT。
    """
    if n_gpus < 2:
        return 0.0
    if message_bytes <= 0 or per_gpu_bps <= 0:
        raise ValueError("message_bytes and per_gpu_bps must be > 0")
    steps = 2 * (n_gpus - 1)
    bytes_per_step = message_bytes / n_gpus
    return steps * (bytes_per_step / (per_gpu_bps * efficiency) + rtt_s)


def cross_site_penalty(message_bytes: float, dci_bps: float = DEFAULT_DCI_BPS,
                       wan_rtt_s: float = DEFAULT_WAN_RTT,
                       efficiency: float = 0.95) -> float:
    """跨园区段的固定代价（秒）：msg 字节过 DCI + 2×WAN RTT。

    与 GPU 数无关、与消息大小线性——这是"单训练域"赌注的量化依据。
    """
    if message_bytes <= 0 or dci_bps <= 0:
        raise ValueError("message_bytes and dci_bps must be > 0")
    return message_bytes / (dci_bps * efficiency) + 2 * wan_rtt_s


def dual_campus_allreduce_time(n_gpus: int, message_bytes: float, per_gpu_bps: float,
                               dci_bps: float = DEFAULT_DCI_BPS,
                               wan_rtt_s: float = DEFAULT_WAN_RTT,
                               efficiency: float = 0.95,
                               rtt_local_s: float = DEFAULT_RTT_LOCAL) -> float:
    """双园区层次化 AllReduce 耗时（秒），一阶模型。

    本地段：reduce-scatter + all-gather 的每 GPU 字节量 ≈ 2·msg，
    与单集群 ring 同量级，故复用 ring 模型。
    跨园区段：见 cross_site_penalty。
    """
    if n_gpus < 2:
        raise ValueError("n_gpus must be >= 2")
    local = ring_allreduce_time(n_gpus, message_bytes, per_gpu_bps,
                                efficiency, rtt_local_s)
    return local + cross_site_penalty(message_bytes, dci_bps, wan_rtt_s, efficiency)


@dataclass(frozen=True)
class StepTimeResult:
    """一次训练迭代的耗时分解（秒）。"""

    compute_s: float
    comm_s: float
    step_s: float
    mfu: float


def step_time(comm_s: float, compute_s: float) -> StepTimeResult:
    """把通信开销折算进步时间与 MFU（通信占比越高 MFU 越低）。

    MFU 这里用"理想计算时间 / 实际步时间"的简化口径。
    """
    if compute_s <= 0:
        raise ValueError("compute_s must be > 0")
    step = compute_s + comm_s
    return StepTimeResult(compute_s=compute_s, comm_s=comm_s, step_s=step,
                          mfu=compute_s / step)


def fabric_comparison(message_bytes: float, n_gpus: int = 100_000,
                      per_gpu_bps: float = DEFAULT_PER_GPU_BPS) -> dict[str, float]:
    """同一拓扑下三种 fabric 的 AllReduce 耗时对比（秒）。"""
    return {
        name: ring_allreduce_time(n_gpus, message_bytes, per_gpu_bps, eff)
        for name, eff in FABRIC_EFFICIENCY.items()
    }


def campus_comparison(n_gpus: int = 100_000,
                      message_sizes_gb: tuple[float, ...] = (256.0, 1024.0, 4096.0, 16384.0),
                      per_gpu_bps: float = DEFAULT_PER_GPU_BPS,
                      dci_bps: float = DEFAULT_DCI_BPS,
                      wan_rtt_s: float = DEFAULT_WAN_RTT,
                      compute_s: float = 20.0,
                      efficiency: float = FABRIC_EFFICIENCY["spectrum-x"]
                      ) -> list[dict[str, float]]:
    """单集群 vs 双园区在不同梯度消息大小下的对比表。

    附 throughput_loss：假设计算耗时固定 compute_s 时，跨园区导致的
    训练吞吐损失比例 = (dual - single) / (single + compute_s)。
    """
    rows = []
    for gb in message_sizes_gb:
        msg = gb * 1024 ** 3
        single = ring_allreduce_time(n_gpus, msg, per_gpu_bps, efficiency)
        dual = dual_campus_allreduce_time(n_gpus, msg, per_gpu_bps,
                                          dci_bps=dci_bps, wan_rtt_s=wan_rtt_s,
                                          efficiency=efficiency)
        rows.append({
            "message_gb": gb,
            "single_s": single,
            "dual_s": dual,
            "penalty_s": dual - single,
            "throughput_loss": (dual - single) / (single + compute_s),
        })
    return rows
