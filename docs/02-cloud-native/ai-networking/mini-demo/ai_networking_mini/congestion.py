"""incast 与 ECN/DCQCN 速率调整简化模型、PFC 死锁示意。

对应真实世界：
- incast：EP all-to-all / 参数同步时多打一，瞬时队列冲垮端口缓冲
- ECN：交换机按队列长度打标记，Kmin/Kmax 分段线性概率
- DCQCN：网卡收到 CNP（拥塞通知包）按 alpha 乘性降速，空闲时字节计数器/
  定时器加性升速——RoCE 无损以太网的事实标准（SIGCOMM'15）
- PFC 死锁：基于优先级流控的无损网络中，缓冲区依赖成环即死锁
  （SIGCOMM'16 "Deadlocks in Datacenter Networks" 的经典反例）

全部为确定性模型，不依赖随机数。
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# 基础延迟模型
# ---------------------------------------------------------------------------

def serialization_delay(payload_bytes: float, bw_bps: float) -> float:
    """发送时延 = 报文大小 / 链路带宽。"""
    if bw_bps <= 0:
        raise ValueError("bw must be positive")
    return payload_bytes * 8 / bw_bps


def incast_completion_time(n_senders: int, msg_bytes: float,
                           egress_bw_bps: float, fabric_latency_s: float) -> float:
    """n 个发送者同时向同一接收者发 msg 的完成时间（确定性流体模型）。

    出口链路串行服务：最后一个报文在 n * serialization 时刻被服务完。
    """
    if n_senders < 1:
        raise ValueError("n_senders must be >= 1")
    return fabric_latency_s + n_senders * serialization_delay(msg_bytes, egress_bw_bps)


def incast_queue_peak(n_senders: int, msg_bytes: float) -> float:
    """同步到达时出口队列的瞬时峰值字节数（需被交换机缓冲吸收，否则丢包/触发 PFC）。"""
    if n_senders < 1:
        return 0.0
    return (n_senders - 1) * msg_bytes


# ---------------------------------------------------------------------------
# ECN 标记
# ---------------------------------------------------------------------------

def ecn_mark_probability(queue_bytes: float, kmin: float, kmax: float,
                         pmax: float = 1.0) -> float:
    """RED/ECN 式分段线性标记概率：q<Kmin -> 0；Kmin..Kmax 线性升到 pmax；>Kmax -> pmax。"""
    if kmin < 0 or kmax <= kmin:
        raise ValueError("need 0 <= Kmin < Kmax")
    if queue_bytes <= kmin:
        return 0.0
    if queue_bytes >= kmax:
        return pmax
    return pmax * (queue_bytes - kmin) / (kmax - kmin)


# ---------------------------------------------------------------------------
# 简化 DCQCN
# ---------------------------------------------------------------------------

DEFAULT_DCQCN = {
    "g": 1.0 / 256,        # alpha 平滑因子
    "ai_fraction": 0.05,   # 加性升速：每步 +5% 线速（简化，真实实现按字节计数器/定时器）
    "fr_period": 8,        # 快速恢复周期（步）
}


def dcqcn_simulate(n_steps: int, cnp_schedule: list, line_rate_bps: float,
                   init_rate_bps: float, params: dict | None = None) -> dict:
    """确定性 DCQCN 速率轨迹模拟。

    每步（对应一个控制间隔）：
    - alpha <- (1-g)*alpha + g*1（收到 CNP）或 +0（未收到）
    - 收到 CNP：rate <- rate * (1 - alpha/2)；target_rate <- min(target, rate)
    - 未收到且 rate < target_rate：每 fr_period 步做一次快速恢复
      rate <- (rate + target_rate) / 2
    - 未收到且 rate >= target_rate：加性升速 rate <- rate + ai_fraction * line_rate

    返回 {"rates": [...], "alphas": [...]}，长度为 n_steps+1（含初始值）。
    """
    p = dict(DEFAULT_DCQCN)
    if params:
        p.update(params)
    if n_steps != len(cnp_schedule):
        raise ValueError("cnp_schedule length must equal n_steps")
    if not 0 < init_rate_bps <= line_rate_bps:
        raise ValueError("init_rate must be in (0, line_rate]")

    rates = [init_rate_bps]
    alphas = [0.0]
    rate = init_rate_bps
    target = line_rate_bps
    alpha = 0.0
    for step, cnp in enumerate(cnp_schedule, start=1):
        alpha = (1 - p["g"]) * alpha + p["g"] * (1.0 if cnp else 0.0)
        if cnp:
            rate = rate * (1 - alpha / 2)
            target = min(target, rate)
        else:
            if rate < target and step % p["fr_period"] == 0:
                rate = (rate + target) / 2
            else:
                rate = min(rate + p["ai_fraction"] * line_rate_bps, line_rate_bps)
        rates.append(rate)
        alphas.append(alpha)
    return {"rates": rates, "alphas": alphas}


# ---------------------------------------------------------------------------
# PFC 死锁
# ---------------------------------------------------------------------------

def detect_deadlock(buffer_dependencies: dict) -> tuple:
    """缓冲区依赖图死锁检测（迭代三色 DFS）。

    buffer_dependencies: {节点: 它阻塞等待的节点集合}
    存在环 <=> 可能死锁。返回 (is_deadlock, cycle_path)。
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in buffer_dependencies}
    stack: list = []
    cycle: list = []

    def dfs(node: str) -> bool:
        color[node] = GRAY
        stack.append(node)
        for nxt in sorted(buffer_dependencies.get(node, ())):
            if nxt not in color:
                continue
            if color[nxt] == GRAY:
                idx = stack.index(nxt)
                cycle.extend(stack[idx:] + [nxt])
                return True
            if color[nxt] == WHITE and dfs(nxt):
                return True
        stack.pop()
        color[node] = BLACK
        return False

    for node in sorted(buffer_dependencies):
        if color[node] == WHITE and dfs(node):
            return True, cycle
    return False, []


def classic_pfc_deadlock() -> dict:
    """教科书式 PFC 死锁：四台交换机做 "上-下" 路由，四条流首尾相接成环。

        A ---- B
        |      |
        D ---- C
    流 1: A->C（经 B 上行）  流 2: B->D（经 C 上行）
    流 3: C->A（经 D 上行）  流 4: D->B（经 A 上行）
    每条流都占满下游交换机的入口缓冲并向上游发 Pause，形成循环等待。
    """
    deps = {"A": {"B"}, "B": {"C"}, "C": {"D"}, "D": {"A"}}
    return deps


def deadlock_free_updown() -> dict:
    """对比组：DAG 式依赖（如所有流只向编号更大的交换机转发）无环，不会死锁。"""
    return {"A": {"B"}, "B": {"C"}, "C": {"D"}, "D": set()}


def pfc_pause_storm_time(n_hops_paused: int, pause_duration_s: float) -> float:
    """PFC 暂停沿环传播一周的时间上界（示意）：每跳传播 pause_duration。"""
    if n_hops_paused < 1 or pause_duration_s <= 0:
        raise ValueError("invalid args")
    return n_hops_paused * pause_duration_s
