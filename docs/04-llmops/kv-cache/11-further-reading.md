# 11. 延伸阅读

> 一句话理解：KV Cache 管理的知识分布在论文（思想源头）、开源代码（工程真相）与相邻主题（网络、存储、分布式）三处——按「先论文建立直觉，再源码验证细节」的顺序读。

## 论文

- **Mooncake: A KVCache-centric Disaggregated Architecture for LLM Serving**（OSDI'24）：PD 分离 + KV 池化的奠基论文，75% 请求增量与 525 tokens/s 数字的出处。
- **Efficient Memory Management for Large Language Model Serving with PagedAttention**（SOSP'23，vLLM）：PagedAttention 与 block 化管理的基础。
- **SGLang / RadixAttention 技术报告**：RadixAttention 与结构化生成负载的缓存复用分析。
- **CacheBlend**（MLSys'24，LMCache 非前缀复用的基础）：任意位置缓存复用 + 选择性重算。
- **DistServe / Splitwise**（OSDI'24 等）：PD 分离的早期系统研究，与 Mooncake 互为印证。

## 官方文档与开源项目

- Mooncake：<https://github.com/kvcache-ai/Mooncake>（Transfer Engine + Store，最新 v0.3.13.post1）
- LMCache：<https://github.com/LMCache/LMCache>（分层缓存与 SERDE，最新 v0.5.6）
- NVIDIA Dynamo：<https://github.com/ai-dynamo/dynamo>（编排层，1.5.1）与 NIXL（传输抽象）
- vLLM KV connector 文档与 `vllm/distributed/kv_transfer/` 源码（v0.31.0）
- SGLang HiCache 文档与 `python/sglang/srt/mem_cache/` 源码（v0.5.21）
- DeepSeek 3FS：<https://github.com/deepseek-ai/3FS>（SSD 级 KV 后端）

## 手册内回链

### 引擎层（缓存机制住在这些引擎里）

- [vLLM](/04-llmops/vllm/) — PagedAttention 与 KV connector 插件体系
- [SGLang](/04-llmops/sglang/) — RadixAttention 与 HiCache 分层
- [TensorRT-LLM](/04-llmops/tensorrt-llm/) — 编译型引擎经 NIXL/Dynamo 接入
- [Triton Inference Server](/04-llmops/triton/) — 部署形态参考

### 平台层（缓存层的上下游）

- [AI 编译器与 Kernel 生成](/04-llmops/ai-compiler/) — FP8 KV 量化与注意力 kernel
- [LLM Gateway](/04-llmops/llm-gateway/) — cache-aware 路由的落地位置

### 基础层（缓存层建立在它们之上）

- [存储系统](/01-foundation/storage-systems/) — SSD/NVMe 与文件系统是分层缓存的底座
- [分布式系统](/01-foundation/distributed-systems/) — 分布式 KV Store 的一致性、容错与调度
- [计算机网络](/01-foundation/computer-networks/) — RDMA 带宽决定跨节点搬运的上限

### 案例层（生产实践出处）

- [DeepSeek 案例](/09-case-study/deepseek/) — 3FS 的 KVCache 设计与全栈实践
