# 7. Mini Demo：超集群建设核心权衡模拟

本主题的 Mini Demo 是一个纯 Python + numpy、CPU 可运行、完全确定性的模拟包 `xai_case_mini`，位于本主题的 `mini-demo/` 目录（代码路径引用：`docs/09-case-study/xai/mini-demo/`）。它把 xAI 案例里最值得动手验证的四个权衡做成可运行的模型：

| 模块 | 模拟的权衡 | 对应章节 |
|---|---|---|
| `power.py` | 供电容量规划：电网 vs 燃气轮机 vs 训练功率曲线 | [3.2 供电层](03-architecture)、[5.1](05-core-modules) |
| `network.py` | 单一大集群 vs 多园区拓扑的 AllReduce 通信模型 | [2.2 单训练域](02-core-ideas) |
| `build.py` | 集群建设排程：并行工作流 + 关键路径分析 | [4.2 建设排程](04-build-and-train) |
| `cooling.py` | 风冷 vs 液冷的机柜功率密度模型 | [3.3 散热层](03-architecture) |
| `demo.py` | 5 个端到端场景 | 本章 |

## 运行方式

```bash
cd docs/09-case-study/xai/mini-demo
pip install -e ".[dev]"
pytest tests/ -v        # 58 个确定性测试
python -m xai_case_mini.demo
```

下文所有数字均来自 demo 的实际输出（确定性，可复现）。

## 场景 1：建设排程——122 天是怎么排出来的

核心代码（`build.py`）：任务图 + 最早开始调度 + 关键路径回溯。

```python
@dataclass(frozen=True)
class Task:
    name: str
    duration_days: int
    deps: tuple[str, ...] = ()

# Colossus 式重排的关键三步：
# 1. 移动燃气轮机 25 天 -> "电"不再等电网扩容（后者退居后台 120 天）
# 2. 5 个网络 pod 并行铺设，不等机房全部装修完
# 3. 服务器 10 个波次两两并行交付，边到货边上架
tasks = [
    Task("mobilize", 5),
    Task("temp_turbines", 25, ("mobilize",)),
    Task("grid_upgrade", 120, ("mobilize",)),      # 后台任务
    Task("pod0_network", 12, ("temp_turbines",)),  # pod1-4 同
    Task("wave0_delivery", 8, ("mobilize",)),      # 波次两两并行
    Task("rack0", 4, ("wave0_delivery", "pod0_network", "temp_turbines")),
    # ... rack1-9 滚动上架 -> cluster_integration -> burn_in
]
```

实测输出：

```text
教科书串行流程 makespan : 425 天
Colossus 式流程集群就绪 : 122 天（全部任务收尾 125 天，电网扩容在后台）
压缩倍数                : 3.48x
首次训练开始            : 第 61 天
电网扩容完工（后台）    : 第 125 天
压缩流程关键路径        : mobilize -> temp_turbines -> pod0_network
                          -> rack0 -> ... -> rack9
                          -> cluster_integration -> burn_in
```

三个读数的方法论意义：**没有任何单环节工期被压缩，425 → 122 全部来自并行化与依赖重排**；关键路径上换成了"临时供电 → 网络 pod → 上架"，电网扩容（第 125 天完工）完全不挡路；首次训练在第 61 天（仅约一成算力上线时）就开始——训练是建设过程的一部分，不是建成后的庆典。

## 场景 2：供电缺口时间线——35 台燃气轮机的工程理由

核心代码（`power.py`）：

```python
def training_demand_mw(num_gpus, gpu_type, pue=PUE_DLC, overhead=IT_OVERHEAD):
    # 10 万卡 H100: 100k * 700W * 1.2 * 1.2 = 100.8 MW
    return facility_load_mw(it_load_mw(num_gpus, gpu_type, overhead), pue)

plan_a = PowerPlan(grid_mw=150.0)                        # 纯等电网扩容
plan_b = PowerPlan(grid_mw=150.0, turbines=[(45, 35)])   # 第 45 天 35 台轮机
```

实测输出：

```text
10 万卡 H100 设施负载   : 100.8 MW（电网 150 MW 够用）
20 万卡 H100 设施负载   : 201.6 MW（超出电网批准 150 MW）
计划 A（纯等电网扩容）: 缺口 180 天，最大缺口 51.6 MW，首次满足需求第 180 天
计划 B（第 45 天起 35 台燃气轮机）: 缺口 45 天，最大缺口 51.6 MW，
         首次满足需求第 45 天
```

20 万卡需求超出电网 51.6 MW，恰是 35 台 × 10 MW 轮机能覆盖的量级：计划 B 把供电缺口从 180 天压到 45 天——**这就是"先上线后合规"的量化动机**。注意模型只算工程账，不算合规成本（第 8 章对账：诉讼、DOJ 介入、2027 拆机承诺）。

## 场景 3：单集群 vs 双园区——"模型越大，单园区越值"的定量验证

核心代码（`network.py`）：ring AllReduce 一阶模型 + 跨园区固定惩罚。

```python
def cross_site_penalty(message_bytes, dci_bps=1.6e12, wan_rtt_s=5e-3, efficiency=0.95):
    # 与 GPU 数无关、与梯度消息（=模型大小）线性
    return message_bytes / (dci_bps * efficiency) + 2 * wan_rtt_s

def dual_campus_allreduce_time(n_gpus, msg, per_gpu_bps, ...):
    local = ring_allreduce_time(n_gpus, msg, per_gpu_bps, ...)  # 本地段同单集群
    return local + cross_site_penalty(msg, ...)                  # + 跨园区固定惩罚
```

实测输出（10 万卡，DCI 1.6 Tbps，跨园区 RTT 5 ms，假设计算 20 s/步）：

```text
  梯度(GB)     单集群(s)     双园区(s)     惩罚(s)     吞吐损失
     256       5.45       5.64      0.19    0.7%
    1024       9.79      10.52      0.73    2.5%
    4096      27.15      30.05      2.90    6.2%
   16384      96.59     108.17     11.58    9.9%
```

惩罚 = 消息大小 ÷ DCI 带宽 + 2×RTT：**分子随模型线性增长，分母是固定资产**。256 GB → 16 TB（64 倍），惩罚从 0.19 s 涨到 11.58 s（带宽项严格 64 倍），吞吐损失从 0.7% 扩大到 9.9%。这就是 xAI 在 [第 2 章](02-core-ideas) 下的赌注的数学形式。

## 场景 4：Spectrum-X 赌注——fabric 效率的端到端影响

实测输出（10 万卡，1 TB 梯度消息）：

```text
      infiniband: AllReduce   9.79 s（相对 IB 1.00x），假设计算 20 s/步时 MFU=0.671
      spectrum-x: AllReduce   9.79 s（相对 IB 1.00x），假设计算 20 s/步时 MFU=0.671
 ethernet-legacy: AllReduce  13.16 s（相对 IB 1.34x），假设计算 20 s/步时 MFU=0.603
```

效率假设直接取自 NVIDIA 官方口径（Spectrum-X 95% / 传统以太网约 60%）。读数：fabric 效率从 95% 掉到 60%，单次 AllReduce 慢 34%，端到端 MFU 掉约 7 个点——**放到数月训练周期就是数周的时间差**。xAI 选 Spectrum-X 的合理性取决于"增强以太网能否稳定做到 95%"，Colossus 的公开实测口径（零丢包、95% 吞吐）是它赌赢的证据。

## 场景 5：风冷 vs 液冷——密度与能耗的双重账

实测输出（10 万卡集群）：

```text
-- H100-SXM 10 万张 --
   air: 每柜 32 卡，需  3125 柜，年耗电 1,030,176 MWh，CO2 ~412,070 吨/年
   dlc: 每柜 72 卡，需  1389 柜，年耗电   883,008 MWh，CO2 ~353,203 吨/年
-- GB200 10 万张 --
   air: 每柜 29 卡，需  3449 柜，年耗电 1,766,016 MWh，CO2 ~706,406 吨/年
   dlc: 每柜 72 卡，需  1389 柜，年耗电 1,513,728 MWh，CO2 ~605,491 吨/年
```

两个读数：液冷把机柜数压缩到约 1/2.2–1/2.5（机房面积与工程量同步下降）；PUE 从 1.4 到 1.2 再省约 14% 电量（10 万卡 H100 一年省约 14.7 万 MWh）。而 GB200 在风冷下每柜只能装 29 卡（1200 W × 29 ≈ 35 kW 封顶）——**功耗越涨，液冷从"优化"变成"唯一选项"**。

## 测试

`pytest tests/ -v`：**58 个测试全部通过**（power 17、network 13、build 10、cooling 11、demo 7）。所有测试断言具体数值（如 `it_load_mw(100_000, "H100-SXM") == 84.0`、关键路径不含 `grid_upgrade`、跨园区惩罚在 RTT 为零时严格随消息 64 倍放大），保证模型行为与本文数字一致。

## 小结

- 场景 1 证明：122 天 = 关键路径重排（3.48 倍压缩），不是单点加速。
- 场景 2 证明：燃气轮机把供电缺口从 180 天压到 45 天——"先上线"的动机可量化。
- 场景 3 证明：跨园区惩罚随模型大小线性增长——单训练域赌注的数学形式。
- 场景 4 证明：fabric 效率 95% vs 60% 在数月训练尺度上是数周的时间差。
- 场景 5 证明：液冷是密度与能耗的双重必选项，且随芯片功耗上涨而加剧。
