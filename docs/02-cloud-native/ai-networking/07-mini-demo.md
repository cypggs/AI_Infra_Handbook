# 7. 工程实践：Mini Demo

> 一句话理解：**`ai_networking_mini` 用 45 个确定性测试和 6 个端到端场景，把 fat-tree/rail 拓扑、TP/DP/EP/PP 流量矩阵、incast 与 ECN/DCQCN、PFC 死锁、ring/tree all-reduce 全部变成 CPU 上可运行的闭式模型**——没有真实 GPU 和交换机，但保留了所有关键语义与数量级。

## 7.1 为什么需要这个 Mini Demo

AI 集群网络的痛点是"现象在应用层、根因在网络层、验证要动真集群"。Mini Demo 把核心机制压缩成纯 Python 模型，让你可以：

- 亲手验证 fat-tree 的跳数分布（2/4/6）与闭式公式是否一致。
- 用流量矩阵看清"为什么 MoE 的 EP 是网络头号杀手"。
- 观察 DCQCN 在持续拥塞下的降速曲线和恢复过程。
- 理解 PFC 死锁的成环条件，而不是死记"PFC 危险"。
- 用 α-β 模型解释"小消息 tree 胜、大消息 ring 胜"这类面试高频题。

## 7.2 快速开始

```bash
cd docs/02-cloud-native/ai-networking/mini-demo
pip install -e ".[dev]"          # 仅依赖 numpy + pytest
pytest tests/ -v                 # 45 个测试全绿
python -m ai_networking_mini.demo  # 跑六个端到端场景
```

## 7.3 六个端到端场景

| 场景 | 演示的核心机制 | 对应真实世界 |
|---|---|---|
| **1. fat-tree 拓扑与二分带宽** | k=8 fat-tree 生成、BFS 跳数 vs 闭式公式、无阻塞二分带宽 | 三层 Clos fabric 的验收计算 |
| **2. rail-optimized vs leaf-spine** | 同规模下交换机数量对比、跨 rail 绕行代价 | Meta/HPN 的 rail 设计动机 |
| **3. 并行策略流量矩阵** | TP/DP/EP/PP 每 step 字节数与主导者、均匀 vs 倾斜 all-to-all 的 incast 因子 | MoE 训练的网络容量规划 |
| **4. incast 与 ECN/DCQCN** | 32 打 1 的完成时间与队列峰值、ECN 标记概率、DCQCN 速率轨迹 | RoCE 无损域调参的直觉来源 |
| **5. PFC 死锁检测** | 缓冲区依赖图成环检测 vs DAG 对照 | PFC 风暴/死锁的经典反例 |
| **6. ring vs tree 与跨 fabric 对比** | 步数换字节的取舍、NVLink/IB/RoCE/TCP 的数量级鸿沟、Amdahl 定律 | 集合通信算法选择与网络选型论证 |

## 7.4 运行示例（实测输出）

```text
=== 场景 1：fat-tree 拓扑与二分带宽 ===
k=8 fat-tree: 128 台主机, 80 台交换机, 384 条链路
二分带宽 25.6 Tb/s, 收敛比 1.0
跳数分布(跳数:主机对数): {2: 192, 4: 768, 6: 7168}

=== 场景 2：rail-optimized vs leaf-spine ===
64 台主机 × 8 网卡：
  leaf-spine 需交换机 48 台 (32 leaf + 16 spine)
  rail-only   需交换机 8 台 (每 rail 一台)
  节省 40 台（83%），代价：跨 rail 流量要绕行 scale-up 域（fabric 4 跳）

=== 场景 3：一次训练 step 的并行策略流量 ===
  DP 梯度同步: 12.99 GiB/rank/step, 模式 reduce-scatter + all-gather
  TP 张量并行: 70.00 GiB/rank/step, 模式 allreduce (ring, 节点内 NVLink 域)
  EP 专家并行: 157.50 GiB/rank/step, 模式 all-to-all (跨节点 scale-out 域)
  PP 流水并行: 1.00 GiB/rank/step, 模式 p2p send/recv (相邻 stage)
  -> 每 step 流量主导者: EP 专家并行
  all-to-all 均匀: hotspot=1.00, incast=1.00
  all-to-all 倾斜(MoE 热 expert): hotspot=1.00, incast=3.82

=== 场景 4：incast 与 ECN/DCQCN ===
32 个 sender 同时向一个 400G 端口各发 4MiB：
  完成时间 2686.4 µs，队列瞬时峰值 124 MiB
  ECN 标记概率: Kmin=64KiB Kmax=1MiB 时 q=130023424 -> 1.00
  DCQCN：线速 400G 起步，前 16 步每步收 CNP，后 16 步空闲
    16 步后速率 307.4 Gbps（降至 77%）
    32 步后速率 400.0 Gbps

=== 场景 5：PFC 缓冲区依赖死锁 ===
  经典 up-down 路由四流成环: 死锁=True, 环路 A -> B -> C -> D -> A
  DAG 式单向依赖(对照组): 死锁=False

=== 场景 6：ring vs tree all-reduce（128 rank）===
  4MiB 小消息: ring 0.67 ms (254 步) vs tree 0.32 ms (14 步) -> tree 胜（时延主导（小消息），tree 步数更少）
  4GiB 大消息: ring 170.96 ms (254 步) vs tree 300.68 ms (14 步) -> ring 胜（带宽主导（大消息），ring 流水线更充分）
  同一 all-reduce 在不同 fabric（4GiB 大消息）：
    NVLink5 (GB200)               37.96 ms
    NVLink4 (H100)                75.89 ms
    PCIe5 x16                    135.54 ms
    InfiniBand NDR 400G          170.96 ms
    RoCE/以太网 400G                171.22 ms
    以太网 100G TCP                 685.64 ms
  通信占 step 29% 时，通信提速 4x 只换来 step 加速 1.27x（Amdahl）

✅ 全部 6 个 AI 集群网络场景通过
```

读数的三个要点：

1. **场景 2 的 83% 交换机节省**是 rail-only 思想的极端演示（单 rail 单交换机、无 spine）；真实 HPN/Meta 设计没有这么激进，但方向一致。
2. **场景 3 的 EP 主导**依赖配置（7B 模型、64-way EP、topk=8）：换更大的 DP 维度，梯度同步会重新主导——先用流量矩阵算账再定并行策略。
3. **场景 6 的 37.96ms vs 170.96ms**（NVLink5 vs IB NDR）就是"TP 必须留在机柜内"的数量级论据；而 Amdahl 数字提醒：通信占比降到 30% 以下后，网络再快收益也有限——**网络优化要与并行策略优化一起做**。

## 7.5 目录结构与模块对照

```text
ai_networking_mini/
├── __init__.py     # 模块导出
├── topology.py     # Leaf-Spine / k-ary fat-tree / rail-optimized 生成；
│                   # BFS 跳数、二分带宽、收敛比、rail 节省测算
├── traffic.py      # ring 边/all-to-all/PP 链式流量矩阵；
│                   # all-reduce/all-to-all 闭式字节数；热点与 incast 因子
├── congestion.py   # incast 完成时间与队列峰值；ECN 分段线性标记；
│                   # 简化 DCQCN 速率轨迹；PFC 缓冲区依赖死锁检测
├── collective.py   # ring/tree all-reduce、all-to-all 的 α-β 模型；
│                   # 跨 fabric 对比；BDP；Amdahl 加速比
└── demo.py         # 6 个端到端场景入口
```

## 7.6 模型假设与取舍（诚实声明）

- 所有时延模型是 α-β 闭式模型，忽略排队动态与协议开销，**用于教学与数量级判断，不用于容量规划的最终数字**。
- DCQCN 是简化版（每步一个控制间隔、加性升速按线速百分比），真实实现按字节计数器与定时器；曲线形状一致，参数数值不可直接套用。
- PFC 死锁用静态缓冲区依赖图检测，演示"成环条件"而非运行时复现。
- fabric 常量（带宽/时延）为公开规格的示意值；PCIe5 x16 按 504Gbps 双向计。

**参考来源**：本章所有数字均出自 `ai_networking_mini` 的实测输出（45 tests passed，Python 3.14 + numpy 2.5）。
