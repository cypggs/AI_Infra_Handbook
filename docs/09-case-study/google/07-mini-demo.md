# 7. Mini Demo：3D-torus 集合通信 + NSDI'24 双路径恢复

本章介绍配套的迷你示例 `docs/09-case-study/google/mini-demo/`——一个**确定性、纯 CPU、无需任何 LLM key**的模拟器，用可运行代码验证 Google 基础设施最具新意的两个机制：

1. **3D-torus 分维 ring AllReduce 的延迟优势**——为什么 torus 的延迟项 2·Σ(dᵢ−1) 远低于单一大环的 2·(N−1)。
2. **NSDI'24《Resiliency at Scale》的两条真实恢复路径**——reconfigure（迁移到空闲健康 cube）vs reroute（容错 ICI 路由，持续步时惩罚）的双轴权衡。

> 源码与运行说明详见 [`mini-demo/README.md`](./mini-demo/README.md)。

## 7.1 设计目标

- **讲透两个机制**：用最少的代码把"torus 延迟优势"和"双路径恢复权衡"做成可亲手调整参数、可断言的模型，而非停留在文字描述。
- **公平对比**：三种恢复策略（naive / reconfigure / reroute）面对**完全相同的故障序列**——故障序列用 seed 预抛、与策略无关，保证差异只来自恢复策略本身。
- **忠实于论文术语**：策略名贴合 NSDI'24 的真实机制（reconfigure = "reconfigure jobs to use spare healthy cubes"；reroute = "fault-tolerant ICI routing"），不使用论文中不存在的"cherry-pick"等词作为论文引用。

## 7.2 安装与运行

```bash
cd docs/09-case-study/google/mini-demo
pip install -e ".[dev]"
python -m google_mini.demo        # 打印对比表 + 拓扑洞察 + 恢复路径阈值洞察
pytest tests/ -q                  # 38 个测试
```

## 7.3 核心机制一：3D-torus 分维 AllReduce

`collective.py` 把一次 AllReduce 沿 torus 每个维度拆成一串短 ring（分层 reduce-scatter / allgather）：

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

**延迟项 = 2·Σ(dᵢ−1)**，按边长线性增长；单一大环是 2·(N−1)，按芯片总数指数增长。对 16×16×16 = 4096 芯片：

```
延迟项：torus 2·Σ(d-1) = 90   单环 2·(N-1) = 8190   （torus 约为单环的 1.1%）
大消息 524288 KiB（带宽主导）：torus ≈ 21.56 ms，单环 ≈ 29.66 ms
小消息 1024 B（延迟主导）：torus ≈ 90.0 µs，单环 ≈ 8190 µs
```

**结论**：torus 的结构性收益在**延迟项**——延迟主导的集合通信（频繁小 AllReduce）获益最大，带宽主导时收益收敛。这是 Google 选 torus 而非 fat-tree + 单一集合通信的数学根因。

## 7.4 核心机制二：reconfigure vs reroute（NSDI'24 双路径）

`recovery.py` 把故障后的恢复建模为三种策略，对应论文的两条真实路径 + 一个裸部署基线：

| 策略 | 对应 NSDI'24 | 停机 | 回滚 | fleet 闲置 | 步时惩罚 |
|---|---|---|---|---|---|
| `naive` | 裸部署（无自动化韧性） | 长（人工维修 ×3） | 是 | 无 | 无 |
| `reconfigure` | Path 1：迁移到空闲健康 cube | 中（OCS 重配 + 迁移） | 是（从 checkpoint） | 有（坏 cube 后台修复） | 无 |
| `reroute` | Path 2：容错 ICI 路由 | 短（重载路由表） | **否**（原地继续） | 无 | **有**（每故障 +5%，累积） |

`simulator.py` 的关键设计：故障序列预抛（`roll_failures`），与策略无关；同一故障、不同处理——

- naive/reconfigure：回滚到最近 checkpoint，重跑未提交步（`wasted += step - last_ckpt`），支付停机。
- reroute：**不回滚**，原地重试故障步（`wasted += 1`），支付极短停机 + 此后每步叠加步时惩罚 `tax`。

`useful = 已提交步数 × 基础步时`（不含 tax），`wall` 含 tax/停机/checkpoint。于是 reroute 的 tax 体现为 wall 增长快于 useful → MFU 下降；reconfigure 的代价体现为回滚重跑 + 一次性迁移停机。

### 7.4.1 主对比表（同一 seed = 7，同一故障序列，9 次故障）

```
配置                           有效训练MFU      恢复停机%      步时惩罚%    中断     回滚步%        集群闲置(chip·h)
基线(无故障)                        67.8%       0.0%       0.0%     0     0.0%                 0.0
naive(裸部署)                      4.8%      91.8%       0.0%     9    19.0%                 0.0
reconfigure(P1迁移)              37.4%      36.0%       0.0%     9    19.0%                36.0
reroute(P2容错路由)                54.9%       5.9%      45.0%     9     0.4%                 0.0
```

读这张表的方式：naive 停机最长、MFU 最低；reconfigure 用一次性迁移停机 + fleet 闲置换较高 job MFU，但回滚重跑 19% 步；reroute 几乎不停机、几乎不回滚（0.4%），但每步承受累积到 45% 的步时惩罚。**同一组故障，三种代价结构一目了然。**

### 7.4.2 阈值洞察：reroute 的步时惩罚要多大，reconfigure 才反超？

```
reconfigure MFU（恒定基准）= 37.4%
reroute MFU 随每次故障叠加的步时惩罚下降：
    惩罚  1%→61.2%  2%→59.5%  3%→57.9%  5%→54.9%  8%→51.0%
    12%→46.5%  16%→42.8%  20%→39.6%  30%→33.4%  ← reconfigure 反超
临界惩罚 ≈ 30%
```

**结论**：只要 reroute 的单次步时惩罚低于临界值（本配置约 30%），其"不停机、不回滚"就压倒 reconfigure。NSDI'24 实测单次 reroute 步时惩罚仅 **0.5%–8.6%**（远低于临界），故 reroute 是默认路径（95% 作业 opt-in）；Google 对 OCS 故障**优先修复**，正是为了把 tax 控制在临界以内、缩短 reroute 时长。这个洞察把"为什么 reroute 是默认"从直觉变成了可量化的阈值。

## 7.5 模块与测试

| 模块 | 职责 | 测试 |
|---|---|---|
| `model.py` | `JobConfig`/`SimResult` | — |
| `topology.py` | `Torus3D`（节点、6 邻居环绕、健康状态） | test_topology（规模、环绕邻居、索引往返、fail/heal） |
| `collective.py` | ring/torus 分维 AllReduce 延迟模型 | test_collective（延迟项 90/8190、两种消息规模 regime、分解核算） |
| `failures.py` | 每步集群风险 + 预抛故障序列 | test_failures（公式、随规模增长、零率、确定性、roll_failures） |
| `recovery.py` | naive/reconfigure/reroute 三策略 | test_recovery（停机顺序、rollback、tax、fleet idle） |
| `simulator.py` | 主循环 | test_simulator（同 seed 同故障序列、wall/MFU 顺序、fleet idle、tax、预算熔断） |
| `metrics.py` | MFU/开销/闲置/步时惩罚 | — |
| `demo.py` | 四配置对比 + 两类洞察 | test_demo（四键、MFU 排序、阈值扫描单调性、crossover） |

**38 个测试全部通过**，且全确定性（`random.Random(seed)`）。

## 7.6 与生产系统的差异

本 Demo 是教学抽象，与真实 TPU v4 生产系统有重要差异：

| 维度 | 本 Demo | 生产 TPU v4（NSDI'24） |
|---|---|---|
| 规模 | 4×4×4 = 64 芯片抽象 | 4096 芯片 Pod，9216 芯片（Ironwood） |
| 拓扑 | 抽象 3D-torus | 真实 3D-torus + 48×128 端口 OCS 光路重配 |
| 故障模型 | 故障序列预抛（与策略/挂钟无关） | 与挂钟时间相关的随机过程；按组件分（机器 0.08%/天、ICI 缆 0.005%、OCS 0.04%） |
| 故障率 | 放大（0.35/芯片·小时）以短模拟内观察多次故障 | 远低；靠 fleet 规模把 MTBF 压到小时/分钟级 |
| 恢复 | 停机 + 集群闲置 + 步时惩罚三个标量 | reconfigure 真实含 OCS xconnect + 重调度 + preflight + 重编译 + checkpoint 载入；reroute 含 wild-first routing ILP 离线路径优化 |
| 步时惩罚 | 固定 +5%/故障，线性累积 | 实测 0.5%–8.6%/故障（Table 3），随 workload/拓扑变 |
| 传输 | 无 | Falcon 硬件传输（200 Gbps/120 Mops，Swift 拥塞） |
| 调度 | 无 | Borg + Borg Prime + borglet + healthd + Pod Manager 协同 |
| checkpoint | 固定间隔 + 固定耗时 | Orbax（OCDBT + Zarr3，异步），间隔/耗时随模型变 |
| reroute 触发 | 每次故障都 reroute | 仅 OCS 故障 reroute；机器/ICI 故障 reconfigure；95% opt-in、<2% 任意时刻活跃 |

**读 Demo 的正确姿势**：把它当作"两个核心机制的玩具验证"——torus 延迟项的数学、双路径代价结构的对比——而非生产仿真。生产细节见 [第 8 章 企业生产实践](08-production-practice)。

下一章 [企业生产实践](08-production-practice) 把这些机制放回真实 fleet 规模。
