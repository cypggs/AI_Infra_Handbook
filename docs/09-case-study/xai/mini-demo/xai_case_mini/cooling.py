"""风冷 vs 液冷的机柜功率密度模型。

对应 xAI Colossus 案例的物理约束：
"100 万卡不是软件问题，是每平方米功率问题——风冷机柜撑死几十 kW，
直接到芯片液冷（DLC）才能把单柜推到 100+ kW，把百万卡塞进一个园区。"

模型（一阶教学近似）：
- 每柜 GPU 数 = min(物理槽位上限, 散热功率上限 // 单卡 TDP)
- 机柜数 = ceil(GPU 总数 / 每柜 GPU 数)
- 年耗电量 = IT 负载 × PUE × 8760h（用于能耗/碳排放估算）
"""

from dataclasses import dataclass

from .power import GPU_TDP_WATTS, PUE_AIR, PUE_DLC, it_load_mw

# 每柜散热功率上限（kW，IT 负载口径）——教学用典型值
RACK_DENSITY_KW = {
    "air": 35.0,    # 传统风冷机柜的实用上限
    "dlc": 130.0,   # 直接到芯片液冷（GB200 NVL72 机柜的数量级）
}

# 每柜物理可装 GPU 数上限（8 卡服务器 × 机柜空间 / NVL72 整柜）
PHYSICAL_SLOTS = {
    "air": 32,   # 4 台 8 卡服务器
    "dlc": 72,   # NVL72 整柜形态
}

HOURS_PER_YEAR = 8760
# 电网平均碳强度（kg CO2/kWh），美国电网数量级，用于教学估算
GRID_CO2_KG_PER_KWH = 0.40


def gpus_per_rack(gpu_type: str, cooling: str) -> int:
    """在给定散热方式下，一个机柜能装多少张卡。

    >>> gpus_per_rack("H100-SXM", "air")
    32
    >>> gpus_per_rack("H100-SXM", "dlc")
    72
    """
    if gpu_type not in GPU_TDP_WATTS:
        raise ValueError(f"unknown gpu_type: {gpu_type}")
    if cooling not in RACK_DENSITY_KW:
        raise ValueError(f"unknown cooling: {cooling}")
    tdp = GPU_TDP_WATTS[gpu_type]
    power_cap = int(RACK_DENSITY_KW[cooling] * 1000 // tdp)
    return min(PHYSICAL_SLOTS[cooling], power_cap)


def racks_needed(num_gpus: int, gpu_type: str, cooling: str) -> int:
    """装下 num_gpus 张卡需要多少个机柜。"""
    if num_gpus <= 0:
        raise ValueError("num_gpus must be > 0")
    per_rack = gpus_per_rack(gpu_type, cooling)
    return -(-num_gpus // per_rack)  # ceil division


def pue(cooling: str) -> float:
    """散热方式对应的 PUE。"""
    if cooling == "air":
        return PUE_AIR
    if cooling == "dlc":
        return PUE_DLC
    raise ValueError(f"unknown cooling: {cooling}")


def annual_energy_mwh(num_gpus: int, gpu_type: str, cooling: str,
                      overhead: float = 1.20) -> float:
    """年耗电量（MWh）= IT 负载 × PUE × 8760。"""
    it = it_load_mw(num_gpus, gpu_type, overhead)
    return it * pue(cooling) * HOURS_PER_YEAR


def annual_co2_tons(num_gpus: int, gpu_type: str, cooling: str,
                    overhead: float = 1.20,
                    co2_kg_per_kwh: float = GRID_CO2_KG_PER_KWH) -> float:
    """年碳排放（吨 CO2）的教学估算。"""
    mwh = annual_energy_mwh(num_gpus, gpu_type, cooling, overhead)
    return mwh * 1000 * co2_kg_per_kwh / 1000.0


@dataclass(frozen=True)
class CoolingComparison:
    cooling: str
    gpus_per_rack: int
    racks: int
    annual_energy_mwh: float
    annual_co2_tons: float


def cooling_comparison(num_gpus: int, gpu_type: str) -> list[CoolingComparison]:
    """同一集群规模下，风冷 vs 液冷的密度/能耗对比。"""
    rows = []
    for cooling in ("air", "dlc"):
        rows.append(CoolingComparison(
            cooling=cooling,
            gpus_per_rack=gpus_per_rack(gpu_type, cooling),
            racks=racks_needed(num_gpus, gpu_type, cooling),
            annual_energy_mwh=annual_energy_mwh(num_gpus, gpu_type, cooling),
            annual_co2_tons=annual_co2_tons(num_gpus, gpu_type, cooling),
        ))
    return rows
