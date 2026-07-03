# 1. 背景：为什么会有 Ray

> 本章回答：Ray 解决什么问题？为什么 Spark/MPI/TensorFlow 分布式不够用？它从哪里来，现在归谁管？

---

## 1.1 设计动机：RL 工作负载逼出的统一框架

Ray 诞生于 **UC Berkeley RISELab**（2017），最初目标很具体：服务**新兴 AI 应用**，尤其是**强化学习（RL）**。论文标题就是《Ray: A Distributed Framework for **Emerging AI** Applications》（[OSDI'18](https://www.usenix.org/system/files/osdi18-moritz.pdf)，[arXiv:1712.05889](https://arxiv.org/abs/1712.05889)）。

RL 之所以"逼出新系统"，是因为它的**工作负载结构**与 2017 年主流系统假设完全不符。一个 RL 训练循环在**同一个程序里**交织四类计算：

| 子任务 | 特征 | 对系统的要求 |
|---|---|---|
| **仿真（simulation）** | 海量短任务、有状态（环境）、可能不均匀 | 亚毫秒派发、有状态长进程 |
| **训练（training）** | 迭代式梯度更新 | 高吞吐集合通信 |
| **推理/服务（serving）** | 策略评估、低延迟 | 在线、与训练共享状态 |
| **持久状态（durable state）** | 策略、replay buffer、环境 | 跨任务可寻址的共享内存 |

> 论文作者自述（Berkeley 技术报告 [EECS-2019-124](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2019/EECS-2019-124.pdf)）：*"我们在 Spark、MPI、TensorFlow 上实现 ML 与 RL 应用的亲身经历，凸显了这些挑战，从而催生了 Ray。"*

### 为什么现有系统不够用

| 系统 | 为何不够 | 出处 |
|---|---|---|
| **Spark** | 批/微批 RDD、粗粒度静态 lineage 图；**无原生有状态 actor**；不适合低延迟 RL 仿真/服务 | [OSDI'18 §2.1](https://www.usenix.org/system/files/osdi18-moritz.pdf) |
| **MPI** | 低层、静态、SPMD；适合紧耦合训练，但无动态任务图、无长作业容错、无训练+服务统一 | [EECS-2019-124](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2019/EECS-2019-124.pdf) |
| **TensorFlow 分布式 / Torch DDP** | 训练专用计算图；不处理仿真与服务 | [OSDI'18 §2.1](https://www.usenix.org/system/files/osdi18-moritz.pdf) |
| **共同缺口** | 都不能干净地建模"长寿命、可变、可寻址"的 worker（一个仿真器、一个环境、一个策略服务器）——RL 的刚需 | 同上 |

### Ray 的论点（thesis）

> Ray 是一个**通用集群计算框架，让一段普通 Python 程序跨集群运行**，靠三个统一原语：**无状态任务（task）**、**有状态 actor**、**共享内存对象存储**，全部表达为**动态任务图（dynamic task graph）**。([OSDI'18 摘要](https://www.usenix.org/system/files/osdi18-moritz.pdf)；[RISELab 项目页](https://rise.cs.berkeley.edu/projects/ray/))

这就是"**分布式 Python**"论点：不是为某个 ML 阶段造系统，而是把 Python 本身扩到集群。

---

## 1.2 历史与论文贡献

### 关键论文与数字

Ray 的奠基论文是 **OSDI 2018**（**注意：不是 SOSP'18**——OSDI 与 SOSP 隔年交替，2018 年没有 SOSP；常见误写须纠正）：

- **Moritz, Nishihara, Wang, Tumanov, Liaw, Liang, Elibol, Yang, Paul, Jordan, Stoica**, *"Ray: A Distributed Framework for Emerging AI Applications"*, **OSDI 2018**。
  - [USENIX 官方 PDF](https://www.usenix.org/system/files/osdi18-moritz.pdf) ｜ [arXiv:1712.05889](https://arxiv.org/abs/1712.05889) ｜ [会议页](https://www.usenix.org/conference/osdi18/presentation/moritz)

> **重要区分**：论文描述的是 **2018 年的原架构**（全局调度器 + GCS 持有 lineage 表）。当前生产架构已被 **Ray v2 架构白皮书**取代（[docs.ray.io/.../whitepaper](https://docs.ray.io/en/latest/ray-contribute/whitepaper.html)，官方明确说白皮书"取代学术论文"）。本主题第 3、4、6 章以白皮书为准，论文仅用于历史对比与吞吐/延迟基准。

论文四大贡献：

1. **统一编程模型**：task-parallel（无状态）与 actor-based（有状态）在同一 API 下，表达为**动态任务图**（运行时构建/修改，区别于 Spark 的静态 lineage）。
2. **两级调度器**：全局调度器（在 GCS 内）+ 每节点本地调度器（raylet），兼顾吞吐与灵活性。**（注：此设计已在 v2 白皮书中被"所有权 + 溢回"取代，见 [第 3 章](03-architecture)。）**
3. **task + actor + object store 三原语**：三者一等公民。
4. **分布式内存对象存储**（Plasma，基于 Apache Arrow 列式格式，零拷贝读）。

论文实测（原文）：*"sub-millisecond remote task latencies and linear throughput scaling beyond 1.8 million tasks per second."*（[USENIX PDF](https://www.usenix.org/system/files/osdi18-moritz.pdf)）。

### 演进时间线

| 库/事件 | 引入 | GA/稳定 | 出处 |
|---|---|---|---|
| **Ray Core**（task/actor/object/调度） | 2017-12（[arXiv:1712.05889](https://arxiv.org/abs/1712.05889)） | **1.0 — 2020-09**（稳定 API） | [Announcing Ray 1.0](https://www.anyscale.com/blog/announcing-ray-1-0) |
| **Ray Tune**（分布式超参搜索） | 2018（[arXiv:1807.05118](https://arxiv.org/abs/1807.05118)） | 1.0 起 | 同上 |
| **Ray RLlib**（分布式 RL） | 2018（[Liang et al., ICML'18](https://proceedings.mlr.press/v80/liang18b.html)） | 1.0 起 | 同上 |
| **Ray Serve**（模型服务） | **1.0（2020-09）** | 1.0；2.7（2023-09）稳定性增强 | [Ray 1.0 blog](https://www.anyscale.com/blog/announcing-ray-1-0) |
| **Ray Workflows** | 1.7 alpha | **从未 GA，2025 弃用** | [弃用公告](https://discuss.ray.io/t/ray-workflows-deprecated/22132) |
| **Ray Datasets → Ray Data** | 1.9（2021-12） | **2.10（2024-03）GA** | [Ray 2.10 releases](https://github.com/ray-project/ray/releases) |
| **Ray Train**（分布式训练） | 1.9 beta | **2.7（2023-09）GA**（**非 2022**） | [Ray 2.7 blog](https://www.anyscale.com/blog/ray-2-7-features-major-stability-stability) |
| **KubeRay**（K8s operator） | 2.0 beta（2022-09） | **2.7（2023-09）GA** | [Ray 2.0 blog](https://www.anyscale.com/blog/announcing-ray-2-0) |
| **Ray AIR**（统一运行时层） | 2.0 beta | **从未 GA，2023-09 随 2.7 下线**，概念并入各库 | 同上 |
| **Redis 解除默认依赖** | **1.11** | — | [Redis in Ray](https://www.anyscale.com/blog/redis-in-ray-past-and-future) |
| **Compiled Graph（编译图）** | 2.32 可用 | **2.44 beta** | [Announcing Compiled Graphs](https://www.anyscale.com/blog/announcing-compiled-graphs) |
| **加入 PyTorch Foundation** | — | **2025-10-22** | [Anyscale blog](https://www.anyscale.com/blog/ray-by-anyscale-joins-pytorch-foundation) |

### 当前版本

Ray 2.x 维持**每周发布**节奏。截至 2026-07，活跃系列在 **2.5x** 区间（文档跟踪 2.55.1；**2.53.0 于 2025-12-20 发布**）。具体最新 patch 请查 [releases](https://github.com/ray-project/ray/releases)。

> **Ray 3.0**：目前**无公开 RFC 或发布**。Compiled Graph 是最"3.0 形态"的工作，但仍属 2.x beta。任何"Ray 3.0"说法在核验前都应视为未确认。

---

## 1.3 治理与商业：进入 PyTorch Foundation

### 重大治理里程碑（2025-10-22）

**Ray 加入 PyTorch Foundation**（Linux Foundation 旗下），与 **PyTorch** 和 **vLLM** 并列。这意味着 Ray 的托管方从单一商业公司（Anyscale）转为基金会治理、多方共担。来源：[Anyscale 博客](https://www.anyscale.com/blog/ray-by-anyscale-joins-pytorch-foundation) ｜ [Linux Foundation 新闻稿](https://www.linuxfoundation.org/press/pytorch-foundation-welcomes-ray-to-deliver-a-unified-open-source-ai-compute-stack) ｜ [The New Stack](https://thenewstack.io/ray-comes-to-the-pytorch-foundation/)。

这**取代**了早先"KubeRay 是否进 CNCF Sandbox"的疑问——Ray 的家在 PyTorch Foundation，而非 CNCF。

### 开源与许可证

- **许可证**：**Apache License 2.0**（[ray/LICENSE](https://github.com/ray-project/ray/blob/master/LICENSE)）。
- **仓库**：[github.com/ray-project/ray](https://github.com/ray-project/ray)。
- **RFC 机制**：[Ray Enhancement Proposals (REPs)](https://github.com/ray-project/enhancements)。

### Anyscale：商业层

Anyscale（2019 成立，创立者 **Ion Stoica / Robert Nishihara / Philipp Moritz**）是 Ray 的商业化主体，提供托管 Ray（Anyscale Cloud）、Anyscale Endpoints/Jobs、企业支持。Ray 本体始终完全开源。

**融资（已核验）**：

| 轮次 | 金额 | 领投 | 时间 | 出处 |
|---|---|---|---|---|
| A 轮 | **$20.6M** | a16z | 2019–2020 | [RISELab blog](https://rise.cs.berkeley.edu/blog/riselab-students-startup-anyscale-raises-20-6-million-in-series-a-funding-led-by-andreessen-horowitz/) |
| B 轮 | **$40M** | NEA | 2020-12 | [Anyscale press](https://www.anyscale.com/press/anyscale-announces-usd40m-in-series-b-funding-led-by-nea) |
| C 轮 | **$100M**（**$1B 估值**独角兽） | a16z + Addition 共投，Intel Capital | 2021-12 | [Fenwick](https://www.fenwick.com/insights/experience/fenwick-represents-anyscale-in-100-million-series-c-financing) ｜ [SiliconANGLE](https://siliconangle.com/2021/12/07/anyscale-raises-100m-launches-distributed-multicloud-application-development-platform/) |
| C 轮追加 | **$99M** | a16z | 2022-08 | [WSJ](https://www.wsj.com/articles/ai-startup-anyscale-adds-99-million-to-andressen-horowitz-led-funding-round-11661254200) |

> **常见误传纠正**：网上流传的"2024 NEA 领投 $1B 轮"**找不到一手来源**，几乎肯定是把 2021-12 的 $1B C 轮估值错记。本主题不引用任何"2024 轮"。"$1B"是 **2021 C 轮估值**，领投是 a16z（NEA 领的是更早的 B 轮）。累计融资约 $281M / 4 轮（[Tracxn](https://tracxn.com)，[总数字未完全核验]）。

---

## 1.4 为什么它对 AI 基础设施重要

1. **统一底座**：数据预处理（Ray Data）+ 分布式训练（Ray Train）+ 超参（Tune）+ RL（RLlib）+ 在线服务（Serve）跑在**同一集群运行时**，省去 Spark+Kubeflow+TorchServe+Airflow 的胶水代码。([Ray 2.0 blog](https://www.anyscale.com/blog/announcing-ray-2-0))
2. **RLHF/前沿实验室底座**：Ray 的 task/actor/object 模型与 RLHF 循环几乎一一对应——rollout worker（actor）产经验、trainer 更新策略、Serve 部署奖励/回复模型，全部内存共享。Ray 被反复引用为 ChatGPT 时代训练/服务栈的一部分（[The New Stack](https://thenewstack.io/how-ray-a-distributed-ai-framework-helps-power-chatgpt/)）。**注意**：任何前沿实验室内部"Ray 具体跑多少 GPU"的数字，都缺乏一手工程博客佐证，本主题只引用间接关联。
3. **LLM 服务的事实栈**：**Ray Serve + vLLM** 已是开源 LLM 服务的标准组合，Ray 2.44 起一等公民集成 vLLM，vLLM 也进入 PyTorch Foundation 与 Ray 并列。
4. **真实规模背书**：Ant Group 用 Ray 跑 24 万核 / 双 11 峰值 1.37M TPS（[Anyscale 案例](https://www.anyscale.com/blog/how-ant-group-uses-ray-to-build-a-large-scale-online-serverless-platform)）；Coinbase 15× 同成本、50× 数据量（[Coinbase 案例](https://www.anyscale.com/resources/case-study/coinbase-ml-infrastructure)）。详见 [第 8 章](08-production-practice)。

---

下一章 [核心思想](02-core-ideas) 拆解 Ray 的三大原语与所有权模型。
