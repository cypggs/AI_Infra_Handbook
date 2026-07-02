# 面试指南

本指南整理 AI Infrastructure 面试的常见考察方向与准备建议。

## 面试方向

### 1. 基础能力

- Linux 内核、进程、内存、IO
- 计算机网络（TCP/UDP、HTTP/gRPC、RDMA）
- 存储（文件系统、对象存储、缓存）
- 分布式系统（CAP、一致性协议、消息队列）

### 2. 云原生

- Kubernetes 架构与调度
- 控制器模式、Operator
- 容器网络与存储
- GPU 在 Kubernetes 上的管理与调度

### 3. AI 平台与 LLMOps

- 模型训练流水线
- 模型服务与推理优化
- vLLM / TensorRT-LLM / SGLang 对比
- LLM Gateway 设计

### 4. Agent 与 RAG

- MCP 协议与架构
- Agent Runtime 设计
- RAG 检索与评估

### 5. AI SRE

- 可观测性三大支柱
- SLO / Error Budget
- 故障排查与事件响应

## 面试题来源

本手册每个主题的 **面试题** 章节都提供了分层题目：

- 初级
- 中级
- 高级
- Staff
- Architect

例如：

- [vLLM 面试题](/04-llmops/vllm/10-interview-questions)

## 准备建议

1. 先按 [学习路线](/10-roadmap/learning-path) 系统学习
2. 每个主题阅读后，先自己回答面试题，再对照参考答案
3. 结合实际项目经验，准备具体的生产踩坑案例
4. 多画图：架构图、流程图、时序图是面试加分项

## 持续更新

本指南会随着手册内容扩展而持续更新。
