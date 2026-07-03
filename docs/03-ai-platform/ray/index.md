# Ray 详解：统一分布式 AI 计算框架

> 一句话理解：**Ray 用 tasks（无状态函数）+ actors（有状态长进程）+ 共享内存对象存储（Plasma）三大原语，把一段普通 Python 程序扩到成千上万核/GPU，并在同一底座上跑训练、推理、强化学习、超参与数据流水线。**

## 这是什么

Ray 是由 UC Berkeley RISELab 发起、现由 **PyTorch Foundation**（Linux Foundation，2025-10-22 起）托管、Anyscale 商业化的开源分布式计算框架（Apache 2.0）。它的奠基论文是 **SOSP 2018**《Ray: A Distributed Framework for Emerging AI Applications》（Moritz et al.，[arXiv:1712.05889](https://arxiv.org/abs/1712.05889)），实测亚毫秒级任务派发延迟、>1.8M tasks/sec 吞吐。

Ray 的核心赌注是**"分布式 Python"**：不只为某一个 ML 阶段造系统，而是把 Python 本身扩到集群，用同一套运行时同时承载数据预处理（Ray Data）、分布式训练（Ray Train）、超参搜索（Ray Tune）、强化学习（RLlib）、在线推理（Ray Serve）。这正是它区别于 Spark（批/无 actor）、MPI/PyTorch DDP（静态 SPMD、只训练）、Kubernetes（无 ML 语义）的根本所在。

## 学习目标

读完本主题，你应当能：

1. 说清 Ray 的三大原语（task/actor/object）与**所有权模型（ownership）+ 溢回调度（spillback）**如何替代了 SOSP'18 论文里的全局调度器。
2. 画出从 `@ray.remote` → `remote()` → CoreWorker → raylet → worker 执行 → Plasma 落盘的完整调用链。
3. 解释 Plasma 对象存储的大小规则（30% RAM / 200GB 上限 / macOS 2GB）、引用计数五元组、80% 主动溢写、lineage 重建与"小对象随 owner 而亡"。
4. 区分 Ray Core / Serve / Train / Data / Tune / RLlib 各自的边界与成熟度，并给出 KubeRay 上 RayCluster / RayJob / RayService 三种 CRD 的选型。
5. 识别生产八大坑（GCS SPOF、对象存储 OOM、actor 串行化、Dashboard 内存、GIL、序列化、PG 碎片、冷启动）并给出缓解。
6. 用一手数字（Ant Group 24 万核 / 1.37M TPS、Coinbase 15× 同成本、Ray Serve LLM + vLLM 冷启动 10–12 分钟）做容量与架构判断。

## 与相邻主题的关系

| 主题 | 关系 |
|---|---|
| [LLMOps / vLLM](/04-llmops/vllm/) | Ray Serve LLM（原 RayLLM/Aviary）把 vLLM 作为默认推理引擎，提供 OpenAI 兼容 API + 自动伸缩 + prefill/decode 分离。 |
| [LLMOps / SGLang](/04-llmops/sglang/) | SGLang 与 Ray 的集成出现在 2.56 文档；常作为 vLLM 的替代后端。 |
| [Agent Runtime](/05-agent/agent-runtime/) | 大规模 Agent 部署（多副本、有状态、工具并发）天然契合 Ray actors + Serve；Ray 是多 Agent/RL 底座。 |
| [RAG](/06-rag/) | Ray Data + Serve 常用于 RAG 的离线索引流水线与在线检索/生成服务。 |
| [AI SRE](/07-ai-sre/) | Ray Dashboard（8265）、Prometheus metrics、State API、`ray memory` 是 AI SRE 在 Ray 集群上的可观测与排障工具集。 |
| [案例研究](/09-case-study/) | OpenAI（间接）、Uber Michelangelo、Shopify Merlin、Pinterest、Ant Group、Coinbase 都在生产用 Ray。 |

## 本章结构

| 章 | 标题 | 一句话 |
|---|---|---|
| [1. 背景](01-background) | 设计动机与历史 | 为什么 RL 工作负载逼出了 Ray；从 RISELab 到 PyTorch Foundation。 |
| [2. 核心思想](02-core-ideas) | 三大原语 + 所有权模型 | task/actor/object、动态任务图、所有权+溢回调度。 |
| [3. 架构设计](03-architecture) | 分层与组件 | Driver/Worker/Raylet/GCS/Plasma 五件套与控制面/数据面。 |
| [4. 执行模型](04-execution-model) | 一个请求的生命周期 | `@ray.remote` → 派发 → 执行 → 返回 → `ray.get` 的完整时序。 |
| [5. 核心模块](05-core-modules) | 模块速查 | Core/Serve/Train/Data/Tune/RLlib/KubeRay 的职责与参数。 |
| [6. 源码与生态分析](06-source-analysis) | C++ 核 + Python 栈 | raylet、core_worker、plasma、Serve 的真实文件与调用链。 |
| [7. Mini Demo](07-mini-demo) | 可运行的玩具调度器 | ownership + hybrid 调度 + Plasma 引用计数/溢写 + lineage 重建 + 自动扩缩容。 |
| [8. 企业生产实践](08-production-practice) | 部署、可观测、容错、坑 | KubeRay、GCS FT、LLM 服务、八大坑与真实规模数字。 |
| [9. 最佳实践](09-best-practices) | 原则与反模式 | 对象传递、actor 并发、PG 设计、冷启动治理。 |
| [10. 面试题](10-interview-questions) | 初/中/高级 | 紧扣章节的 18 问。 |
| [11. 延伸阅读](11-further-reading) | 论文、仓库、博客 | SOSP'18、ownership NSDI'21、KubeRay、用户案例。 |

## 一句话总结

Ray 的价值不在于"又一个调度器"，而在于**用一套任务/actor/对象三原语 + 所有权模型，把训练-推理-数据-RL 统一到一个分布式 Python 底座上**——这正是 RLHF 时代前沿实验室与互联网公司的基础设施选择，也是它在 2025 年进入 PyTorch Foundation（与 PyTorch、vLLM 并列）的原因。
