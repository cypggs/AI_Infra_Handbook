"""供电容量规划模拟：电网容量 vs 燃气轮机补充 vs 训练功率曲线。

对应 xAI Colossus 案例中的核心权衡：
"超集群的上限不是 GPU 到货速度，而是电——当电网审批不够快时，
先上燃气轮机（哪怕违规），让供电不挡在关键路径上。"

模型刻意简化，只保留教学所需的一阶效应：
- IT 负载 = GPU 数 × 单卡 TDP × 网络/存储开销系数
- 设施负载 = IT 负载 × PUE（液冷显著优于风冷）
- 供电计划 = 恒定电网容量 + 按启用日期的燃气轮机爬坡
- 缺口时间线 = 逐日（容量 - 需求）
"""

from dataclasses import dataclass, field

import numpy as np

# 典型加速卡的 TDP（瓦），来自各厂商公开规格数量级
GPU_TDP_WATTS = {
    "H100-SXM": 700.0,
    "H200-SXM": 700.0,
    "B200-SXM": 1000.0,
    "GB200": 1200.0,  # 含 Grace CPU 分摊的约值
    "MI300X": 750.0,
}

PUE_AIR = 1.40  # 传统风冷数据中心（含输配电损耗）
PUE_DLC = 1.20  # 直接到芯片液冷（现代水平，Colossus 为液冷）
IT_OVERHEAD = 1.20  # CPU/网络/存储/主机开销相对 GPU IT 负载的系数

# 单台工业燃气轮机的典型出力（MW）数量级
TURBINE_MW = 10.0


def it_load_mw(num_gpus: int, gpu_type: str, overhead: float = IT_OVERHEAD) -> float:
    """计算 GPU 集群的 IT 负载（MW）。

    >>> it_load_mw(100_000, "H100-SXM")
    84.0
    """
    if num_gpus < 0:
        raise ValueError("num_gpus must be >= 0")
    watts = GPU_TDP_WATTS[gpu_type] * num_gpus * overhead
    return watts / 1e6


def facility_load_mw(it_mw: float, pue: float = PUE_DLC) -> float:
    """按 PUE 折算设施总负载（MW）。"""
    if pue < 1.0:
        raise ValueError("PUE must be >= 1.0")
    return it_mw * pue


def training_demand_mw(num_gpus: int, gpu_type: str, pue: float = PUE_DLC,
                       overhead: float = IT_OVERHEAD) -> float:
    """一步到位：GPU 数 -> 设施总负载（MW）。"""
    return facility_load_mw(it_load_mw(num_gpus, gpu_type, overhead), pue)


@dataclass
class PowerPlan:
    """供电计划：恒定电网容量 + 按日期启用的燃气轮机。

    turbines 是 (启用日, 台数) 列表，例如 [(30, 20), (90, 15)]
    表示第 30 天启用 20 台、第 90 天再启用 15 台。
    """

    grid_mw: float
    turbines: list[tuple[int, int]] = field(default_factory=list)
    turbine_mw: float = TURBINE_MW
    horizon_days: int = 365

    def __post_init__(self) -> None:
        if self.grid_mw < 0:
            raise ValueError("grid_mw must be >= 0")
        if self.horizon_days <= 0:
            raise ValueError("horizon_days must be > 0")
        for day, count in self.turbines:
            if day < 0 or count < 0:
                raise ValueError("turbine entries must be (day>=0, count>=0)")

    def capacity_timeline(self) -> np.ndarray:
        """返回逐日供电容量（MW），长度 horizon_days。"""
        cap = np.full(self.horizon_days, self.grid_mw, dtype=float)
        for day, count in self.turbines:
            idx = min(day, self.horizon_days)
            cap[idx:] += count * self.turbine_mw
        return cap

    def shortfall_timeline(self, demand_mw: float) -> list[tuple[int, float, float, float]]:
        """返回逐日 (日, 容量, 需求, 缺口)；缺口 = 容量 - 需求，负数即不足。

        demand_mw 为常数（对应"集群满载跑稳态"的简化）。
        """
        cap = self.capacity_timeline()
        demand = np.full(self.horizon_days, demand_mw, dtype=float)
        gap = cap - demand
        return [(d, float(cap[d]), float(demand[d]), float(gap[d]))
                for d in range(self.horizon_days)]

    def max_shortfall_mw(self, demand_mw: float) -> float:
        """全时间窗内最大供电缺口（MW，正数=缺口）。"""
        gap = self.capacity_timeline() - demand_mw
        short = -gap
        return float(short.max(initial=0.0))

    def days_of_shortfall(self, demand_mw: float) -> int:
        """出现供电缺口（容量 < 需求）的天数。"""
        gap = self.capacity_timeline() - demand_mw
        return int((gap < 0).sum())

    def first_day_meeting(self, demand_mw: float) -> int | None:
        """容量首次满足需求的日期；一直不满足返回 None。"""
        gap = self.capacity_timeline() - demand_mw
        ok = np.nonzero(gap >= 0)[0]
        return int(ok[0]) if ok.size else None
