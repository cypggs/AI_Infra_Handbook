# google-mini — Google TPU 3D-torus 集合通信 + 训练可靠性模拟器

`docs/09-case-study/google/mini-demo/` 中的迷你示例。它复现 Google 超大规模 TPU
训练基础设施中最具辨识度、也最能与 NVIDIA（fat-tree + NVLink）/ Meta（fat-tree）
区分开的两组机制：

1. **3D-torus 分维 ring AllReduce 的延迟优势**——把一次 AllReduce 沿 torus 三个
   维度拆成短 ring，延迟项 = 2·Σ(dᵢ−1) 按边长线性增长，远低于把所有芯片串成
   单一大环的 2·(N−1)（按芯片总数指数增长）。
2. **NSDI'24《Resiliency at Scale》的两条真实恢复路径**——故障后调度器在
   **reconfigure（Path 1：OCS 重配 + 迁移到空闲健康 cube，从 checkpoint 恢复）**
   与 **reroute（Path 2：保留分配，重载容错 ICI 路由表，不迁移不回滚，但每步承受
   持续步时惩罚）**之间权衡，外加一个 naive（裸部署）基线。

整个 Demo **确定性、纯 CPU、无需任何 LLM key**——所有随机性来自带 seed 的 `random.Random`，
且故障序列「预抛」、与策略无关，保证三种恢复策略面对完全相同的故障点。

## 安装与运行

```bash
cd docs/09-case-study/google/mini-demo
pip install -e ".[dev]"
python -m google_mini.demo        # 打印对比表 + 拓扑洞察 + 恢复路径阈值洞察
pytest tests/ -q                  # 38 个测试
```

## 示例输出

```text
Google TPU 3D-torus 训练可靠性模拟（reconfigure vs reroute，NSDI'24 双路径）
────────────────────────────────────────────────────────────────────────────────────────────────────────
配置                           有效训练MFU      恢复停机%      步时惩罚%    中断     回滚步%        集群闲置(chip·h)
────────────────────────────────────────────────────────────────────────────────────────────────────────
基线(无故障)                        67.8%       0.0%       0.0%     0     0.0%                 0.0
naive(裸部署)                      4.8%      91.8%       0.0%     9    19.0%                 0.0
reconfigure(P1迁移)              37.4%      36.0%       0.0%     9    19.0%                36.0
reroute(P2容错路由)                54.9%       5.9%      45.0%     9     0.4%                 0.0
────────────────────────────────────────────────────────────────────────────────────────────────────────

拓扑洞察：16×16×16 = 4096 芯片上的 AllReduce
  延迟项：torus 2·Σ(d-1) = 90   单环 2·(N-1) = 8190   （torus 约为单环的 1.1%）
  大消息 524288 KiB（带宽主导）：torus ≈ 21.56 ms，单环 ≈ 29.66 ms
  小消息 1024 B（延迟主导）：torus ≈ 90.0 µs，单环 ≈ 8190 µs

恢复路径阈值洞察：reroute 步时惩罚要多大，reconfigure 才反超？
  reconfigure MFU（恒定基准）= 37.4%
  reroute MFU 随每次故障叠加的步时惩罚下降：
      惩罚  1%→61.2%  2%→59.5%  3%→57.9%  5%→54.9%  8%→51.0%
      12%→46.5%  16%→42.8%  20%→39.6%  30%→33.4%  ← reconfigure 反超
  临界惩罚 ≈ 30%：NSDI'24 实测单次 reroute 步时惩罚仅 0.5%–8.6%（远低于临界），
  故 reroute 是默认路径（95% opt-in）；Google 优先修复 OCS 正是为了把 tax 控制在临界以内。
```

## 模块

| 模块 | 职责 |
|---|---|
| `model.py` | `JobConfig` / `SimResult` 数据结构与校验 |
| `topology.py` | `Torus3D`：节点、6 邻居环绕、OCS 可重配的健康状态 |
| `collective.py` | ring / torus 分维 AllReduce 延迟模型，单一大环基线 |
| `failures.py` | 每芯片每小时故障率 → 每步集群风险；预抛故障序列 |
| `recovery.py` | 三种策略：`naive` / `reconfigure`（Path 1）/ `reroute`（Path 2） |
| `simulator.py` | `TrainingSimulator.run()`：主循环（故障 + 按策略恢复） |
| `metrics.py` | 有效训练 MFU、恢复/checkpoint 开销、步时惩罚、集群闲置 |
| `demo.py` | 四配置对比 + torus-vs-ring 拓扑洞察 + reconfigure-vs-reroute 阈值洞察 |

## 两个核心机制

### 1. 3D-torus 分维 AllReduce

```python
def torus_allreduce_time(dims, msg_bytes, bw, lat):
    t = 0.0
    shard = 1
    for d in dims:
        step_bytes = msg_bytes / (shard * d)
        t += 2.0 * (d - 1) * (lat + step_bytes / bw)   # 沿该维 reduce-scatter + allgather
        shard *= d
    return t
```

延迟项 = 2·Σ(dᵢ−1)。对 16×16×16：90，而单一大环 2·(4096−1)=8190——torus 延迟项约为
单环的 1.1%。带宽项两者渐近相同，故**延迟主导**（频繁小 AllReduce）时 torus 优势最大。

### 2. reconfigure vs reroute（NSDI'24 的两条真实恢复路径）

同一 seed 下三种策略面对**完全相同的预抛故障序列**：`failures` 与 `useful`（已提交步数 ×
基础步时）完全一致，只有 `wall`（含恢复停机 / 步时惩罚 / 回滚重跑）不同：

- **reconfigure（Path 1）**：OCS 把作业迁到空闲健康 cube，从 checkpoint 恢复 → 一次性迁移
  停机 + 回滚重跑（作废步多）+ 被放弃坏 cube 后台修复期间整片闲置（fleet 代价）；**零持续 tax**。
- **reroute（Path 2）**：保留分配、重载容错路由表，**不迁移、不回滚**（仅重试故障步）→
  几乎不停机、作废步极少；但此后**每步承受持续步时惩罚**（多次故障累积）。
- **naive**：无自动化韧性 → 人工 + 物理维修，停机最长。

Demo 进一步用「步时惩罚阈值扫描」揭示：只要 reroute 的单次步时惩罚低于某临界值（本配置约 30%），
其「不停机、不回滚」就压倒 reconfigure；NSDI'24 实测该惩罚仅 0.5%–8.6%，故 reroute 是默认路径。

## 与生产系统的差异

见 [07-mini-demo.md](../07-mini-demo.md) 的「与生产系统的差异」表。要点：真实 TPU v4
pod 是 4096 芯片 + OCS 光路重配 + Falcon 硬件传输 + Borg 调度协同；本 Demo 用 4×4×4 抽象
拓扑、放大故障率、把恢复简化为「停机 + 集群闲置 + 步时惩罚」三个标量，并预先抛出与策略无关
的故障序列以保证公平对比（生产中故障是与挂钟时间相关的随机过程）。
