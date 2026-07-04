# 11. 延伸阅读与学习路径

> 本章汇总 Ray 相关的论文、官方文档、工程博客、公开演讲与相邻主题，帮助读者从“会用”走向“能讲清楚设计取舍”。

---

## 11.1 必读论文

| 论文 | 年份 | 核心贡献 | 与本主题关系 |
|---|---|---|---|
| **Ray: A Distributed Framework for Emerging AI Applications** (Moritz et al., SOSP'18) | 2018 | 提出 task/actor/object 三元抽象、全局调度器、GCS | 理解 Ray 最初设计动机与演进起点 |
| **Ownership: A Distributed Futures System for Fine-Grained Tasks** (Wang et al., NSDI'21) | 2021 | 提出 ownership 模型，把任务规格与引用计数从 GCS 下放到 worker | 理解现代 Ray 容错与调度核心 |
| **Spillback Scheduling** (Ray 调度文档/源码) | 2020+ | 分布式 spillback 调度替代全局调度器 | 理解默认 HYBRID 策略的底层实现 |
| **RLlib: Scalable Reinforcement Learning** | 2018+ | 大规模 RL 训练框架 | RLlib 主题源码基础 |

> **注意**：Ray 原始论文发表在 **SOSP'18**，不是 SOSP'17 也不是 OSDI'18；ownership 论文在 **NSDI'21**。引用时不要写错会议名。

---

## 11.2 官方文档与源码

### 核心文档

- [Ray Core Key Concepts](https://docs.ray.io/en/latest/ray-core/key-concepts.html)
- [Ray Tasks](https://docs.ray.io/en/latest/ray-core/tasks.html)
- [Ray Actors](https://docs.ray.io/en/latest/ray-core/actors.html)
- [Ray Objects / ObjectRefs](https://docs.ray.io/en/latest/ray-core/objects.html)
- [Ray Scheduling](https://docs.ray.io/en/latest/ray-core/scheduling/index.html)
- [Placement Groups](https://docs.ray.io/en/latest/ray-core/scheduling/placement-group.html)
- [Handling Dependencies (runtime_env)](https://docs.ray.io/en/latest/ray-core/handling-dependencies.html)
- [Ray Fault Tolerance](https://docs.ray.io/en/latest/ray-core/fault-tolerance.html)

### 库文档

- [Ray Serve](https://docs.ray.io/en/latest/serve/index.html)
- [Ray Serve LLM](https://docs.ray.io/en/latest/serve/llm/index.html)
- [Ray Data](https://docs.ray.io/en/latest/data/data.html)
- [Ray Train](https://docs.ray.io/en/latest/train/train.html)
- [Ray Tune](https://docs.ray.io/en/latest/tune/index.html)
- [RLlib](https://docs.ray.io/en/latest/rllib/index.html)
- [KubeRay](https://docs.ray.io/en/latest/cluster/kubernetes/index.html)

### 源码仓库

- [ray-project/ray](https://github.com/ray-project/ray)
  - `src/ray/core_worker/`：ownership、task manager
  - `src/ray/raylet/scheduling/`：调度策略
  - `src/ray/object_manager/plasma/`：对象存储
  - `python/ray/`：Python API 与库
- [ray-project/kuberay](https://github.com/ray-project/kuberay)

---

## 11.3 工程博客与演讲

### Anyscale / Ray 团队

- [Ray 2.0 and Beyond](https://www.anyscale.com/blog/ray-2-0-and-beyond) — 2.x 架构演进
- [Ownership in Ray](https://www.anyscale.com/blog/ownership-in-ray) — ownership 模型详解
- [Ray Serve LLM Announcement](https://www.anyscale.com/blog/ray-serve-llm) — Serve LLM 定位
- [Ray Data GA](https://www.anyscale.com/blog/ray-data-ga) — Data GA 2.10
- [Ray Train GA](https://www.anyscale.com/blog/ray-train-ga) — Train GA 2.7

### 用户案例

- Ant Group @ Ray Summit（240k cores, 1.37M TPS）
- Coinbase：15× jobs same cost, 50× data
- Shopify Merlin、Pinterest、Uber Michelangelo、Netflix 等公开技术分享

### 基金会与治理

- [Ray Joins PyTorch Foundation](https://pytorch.org/foundation/) — 2025-10-22 加入 Linux Foundation
- [Anyscale](https://www.anyscale.com/) — 商业支持、Anyscale Platform、Ray Summit

---

## 11.4 相关主题交叉引用

| 主题 | 关系 | 推荐阅读 |
|---|---|---|
| **[vLLM](/04-llmops/vllm/)** | Ray Serve LLM 默认后端 | vLLM 连续批处理、PagedAttention |
| **[TensorRT-LLM](/04-llmops/tensorrt-llm/)** | 可作为 Ray Serve backend | NVIDIA 推理优化 |
| **KServe** | 可与 Ray Serve 互补 | K8s 模型服务网关（本手册 LLMOps 篇待补充） |
| **[KubeRay](/03-ai-platform/kuberay/)** | Ray 在 Kubernetes 上的官方 Operator | RayCluster / RayJob / RayService / GCS FT |
| **[Kubernetes](/02-cloud-native/kubernetes/)** | KubeRay 基座 | K8s 调度框架、Operator 模式、GPU/Gang 调度 |
| **[Observability](/07-ai-sre/)** | Ray 生产可观测 | Prometheus/Grafana/OpenTelemetry |
| **[Agent Runtime](/05-agent/agent-runtime/)** | Ray 可用于多 Agent 执行后端 | ReAct、multi-agent 调度 |
| **[Multi-Agent](/05-agent/multi-agent/)** | Ray 可支撑分布式 Agent 集群 | Agent 通信与协调 |

---

## 11.5 推荐学习路径

### 路径 A：从使用到调优（开发者）

1. 本地跑通 `ray.init()` + `@ray.remote` + `ray.get`。
2. 用 Ray Data 完成一个 ETL/批量推理项目。
3. 用 Ray Train 跑一个多 GPU 训练任务。
4. 用 Ray Serve 部署一个模型，配置 autoscaling。
5. 在 KubeRay 上部署上述服务。

### 路径 B：从原理到源码（架构师）

1. 精读 SOSP'18 Ray 论文 + NSDI'21 Ownership 论文。
2. 阅读 `src/ray/core_worker/` 与 `src/ray/raylet/scheduling/` 关键类。
3. 跟踪一个 task 从 `CoreWorker::SubmitTask` 到 worker 执行的完整调用链。
4. 研究 object store spill/restore 在 `LocalObjectManager` 中的状态机。
5. 对比 Ray Serve / KServe / Triton 的架构取舍。

### 路径 C：从落地到生产（平台工程师）

1. 搭建本地 KubeRay 集群（kind/minikube）。
2. 提交一个 `RayJob` 与一个 `RayService`。
3. 配置 Prometheus + Grafana 监控 Ray 指标。
4. 做节点故障演练，验证 task 重试与 actor 重启行为。
5. 调优 autoscaler idle timeout 与 object store 大小。

---

## 11.6 常见问题索引

| 问题 | 答案位置 |
|---|---|
| Ray 默认调度策略是什么？ | [第 2 章](/03-ai-platform/ray/02-core-ideas.html) |
| ownership 模型如何影响容错？ | [第 2 章](/03-ai-platform/ray/02-core-ideas.html)、[第 4 章](/03-ai-platform/ray/04-execution-model.html) |
| object store 容量与溢写阈值 | [第 3 章](/03-ai-platform/ray/03-architecture.html)、[第 7 章 mini-demo](/03-ai-platform/ray/07-mini-demo.html) |
| KubeRay 部署与 GCS FT | [第 8 章](/03-ai-platform/ray/08-production-practice.html) |
| 何时用 Task vs Actor | [第 9 章](/03-ai-platform/ray/09-best-practices.html) |
| 面试题 | [第 10 章](/03-ai-platform/ray/10-interview-questions.html) |

---

## 11.7 版本速查

| 版本 | 时间 | 里程碑 |
|---|---|---|
| Ray 1.0 | 2020-09 | 首个稳定大版本 |
| Ray 1.11 | 2022-03 | GCS 默认内存存储 |
| Ray 2.0 | 2022-08 | 新 API、Ray Train v1 |
| Ray 2.7 | 2023-09 | Ray Train GA；KubeRay GA |
| Ray 2.10 | 2024-03 | Ray Data GA |
| Ray 2.51 | 2025-05 | Ray Train v2 默认开启 |
| Ray 2.55 | 2026-06 | 最新稳定版（截至 2026-07） |

> 当前稳定版本以 [Ray GitHub Releases](https://github.com/ray-project/ray/releases) 为准。

---

## 11.8 小结

- **论文**：SOSP'18 + NSDI'21 是理解 Ray 设计演进的基石。
- **文档**：docs.ray.io 是最权威的 API 与配置来源。
- **源码**：`core_worker`、`raylet/scheduling`、`object_manager/plasma` 是三大核心。
- **相邻主题**：vLLM/TensorRT-LLM/KServe/K8s/Observability 与 Ray 形成生产栈。
- **学习路径**：按开发者、架构师、平台工程师三条路线推进。
