# LLM 推理缓存与 KV Cache 管理 总览

> 一句话理解：**KV Cache 正在从「推理引擎的私有内部状态」演变成一种可共享、可迁移、可卸载的新兴存储对象**，围绕它长出了一层跨进程、跨节点的缓存基础设施——这是 2024-2026 年 LLM  serving 领域最重要的架构变化之一。

## 学习目标

阅读完本主题后，你应该能够：

1. 用公式手算任意模型的每 token KV 占用，并解释 GQA/MLA 等架构演进为什么都在「砍 KV」。
2. 说清楚 KV Cache 管理的三大核心思想：**复用（Sharing）、迁移（Migration）、分层（Tiering）**。
3. 画出「prefix 缓存 → PD 分离 → 分层卸载」的完整缓存架构，并标注控制面与数据面。
4. 讲清一个请求从进网关到返回的 KV 生命周期：路由亲和、前缀命中、block 调度、跨节点传输、逐出降级。
5. 对比 Mooncake、LMCache、NVIDIA NIXL/Dynamo、vLLM KV connector、SGLang HiCache 的定位与集成方式。
6. 理解迁移成本模型：什么情况下「慢层命中」是赚的，什么情况下不如重新 prefill。
7. 跑通并扩展本主题的 Mini Demo（paged block、radix 前缀树、三层缓存、PD 传输调度）。
8. 回答 KV 经济学、prefix 共享率、PD 分离、KV 量化相关的面试问题。

## 与 LLMOps 其他主题的关系

| 主题 | 解决的核心问题 | 与本主题的关系 |
|---|---|---|
| [vLLM](/04-llmops/vllm/) | 单引擎高吞吐 serving | vLLM v1 的 PagedAttention 是 block 化 KV 管理的起点；KV connector 把缓存层做成插件 |
| [SGLang](/04-llmops/sglang/) | LLM Program 与结构化生成 | RadixAttention 与本主题的 prefix 复用直接对应；HiCache 是本主题分层思想的产品化 |
| [TensorRT-LLM](/04-llmops/tensorrt-llm/) | NVIDIA 编译型推理引擎 | 通过 NIXL/Dynamo 接入跨节点 KV 传输与卸载 |
| [Triton Inference Server](/04-llmops/triton/) | 多框架统一推理服务 | 部署形态参考；KV 缓存层位于其上的编排面 |
| [LLM Gateway](/04-llmops/llm-gateway/) | 多引擎统一接入与治理 | Gateway 的 cache-aware 路由是 KV 复用率的第一道放大器 |
| [AI 编译器与 Kernel 生成](/04-llmops/ai-compiler/) | 算子与 Kernel 优化 | KV 量化（FP8/INT4）需要 kernel 层配合；MLA 等架构压缩改变 KV 布局 |
| [存储系统](/01-foundation/storage-systems/) | 文件系统、块存储、NVMe | SSD/3FS 层的 KV 卸载建立在存储系统之上 |
| [分布式系统](/01-foundation/distributed-systems/) | 一致性、容错、调度 | 分布式 KV Store（Mooncake Store）是典型分布式系统问题 |
| [计算机网络](/01-foundation/computer-networks/) | RDMA、拥塞控制、带宽 | 跨节点 KV 直传的性能上限由网络决定 |
| [DeepSeek 案例](/09-case-study/deepseek/) | 训练与推理全栈实践 | 3FS 的 KVCache 客户端是本主题 SSD 卸载层的代表 |

## 本章结构

1. [背景](01-background) — KV 为什么成为一种新的存储对象。
2. [核心思想](02-core-ideas) — 复用、迁移、分层三大思想与成本模型。
3. [架构设计](03-architecture) — 分层缓存架构与数据面/控制面划分。
4. [工作流程](04-runtime-workflow) — 请求的 KV 生命周期详解。
5. [核心模块](05-core-modules) — block manager、radix tree、transfer engine、router、tier manager。
6. [生态与源码分析](06-source-analysis) — Mooncake / LMCache / NIXL / vLLM connector / HiCache 对比。
7. [Mini Demo](07-mini-demo) — 纯 Python 可运行的四类机制模拟。
8. [企业生产实践](08-production-practice) — Mooncake、3FS、Dynamo 的落地形态。
9. [最佳实践](09-best-practices) — 前缀设计、路由、量化、容量规划、SLO。
10. [面试题](10-interview-questions) — 初级/中级/高级面试题。
11. [延伸阅读](11-further-reading) — 论文、官方文档与手册内回链。

## 一句话总结

KV Cache 管理把「注意力状态」当作一等存储对象来经营：**能复用的不重复算（复用）、能搬走的不占显存（迁移）、能下沉的不挤 GPU（分层）**——它处在推理引擎、网络与存储三个领域的交汇处，是 LLM 基础设施工程师必须理解的新的系统层。
