---
layout: home

hero:
  name: "AI Infra Handbook"
  text: "AI 基础设施工程师手册"
  tagline: 从 Kubernetes 到 LLMOps，系统构建生产级 AI 基础设施知识体系
  actions:
    - theme: brand
      text: 开始阅读
      link: /guide
    - theme: alt
      text: 学习路线
      link: /10-roadmap/learning-path
    - theme: alt
      text: vLLM 详解
      link: /04-llmops/vllm/
    - theme: alt
      text: SGLang 详解
      link: /04-llmops/sglang/
    - theme: alt
      text: TensorRT-LLM 详解
      link: /04-llmops/tensorrt-llm/
    - theme: alt
      text: Triton 详解
      link: /04-llmops/triton/
    - theme: alt
      text: LLM Gateway 详解
      link: /04-llmops/llm-gateway/
    - theme: alt
      text: Agent Runtime 详解
      link: /05-agent/agent-runtime/
    - theme: alt
      text: Memory 详解
      link: /05-agent/memory/
    - theme: alt
      text: Multi-Agent 详解
      link: /05-agent/multi-agent/
    - theme: alt
      text: Reflection 详解
      link: /05-agent/reflection/
    - theme: alt
      text: MCP 详解
      link: /05-agent/mcp/
    - theme: alt
      text: Planning 详解
      link: /05-agent/planning/
    - theme: alt
      text: Tool Use 详解
      link: /05-agent/tool-use/
    - theme: alt
      text: Agent OS 详解
      link: /05-agent/agent-os/
    - theme: alt
      text: RAG 详解
      link: /06-rag/
    - theme: alt
      text: AI SRE 详解
      link: /07-ai-sre/
    - theme: alt
      text: 安全详解
      link: /08-security/
    - theme: alt
      text: OpenAI 案例
      link: /09-case-study/openai/
    - theme: alt
      text: Anthropic 案例
      link: /09-case-study/anthropic/
    - theme: alt
      text: Meta 案例
      link: /09-case-study/meta/

features:
  - icon: 📚
    title: 系统化
    details: 覆盖基础、云原生、AI 平台、LLMOps、Agent、RAG、AI SRE、安全、案例、路线十大模块。
  - icon: 🔧
    title: 工程化
    details: 每个主题都包含源码分析、Mini Demo、生产实践、最佳实践与面试题，强调可落地。
  - icon: 🌐
    title: 开源协作
    details: 采用 CC-BY-SA-4.0 协议，欢迎提交 PR、Issue 与改进建议，长期维护。
  - icon: 🧠
    title: 面向实践
    details: 不翻译文档，不堆砌 API，而是讲透设计思想、工程实现与真实踩坑经验。
---

## 一句话理解

> **AI Infra Handbook 不是教程合集，而是一本面向 AI 基础设施工程师的长期维护的工程手册。**

它帮助一名已经具备 Kubernetes / Linux 基础的工程师，成长为能够设计和构建 AI 基础设施的平台工程师、LLMOps Engineer 或 AI SRE。

## 当前进度

- [x] 项目骨架与 VitePress 初始化
- [x] vLLM 主题（LLM 推理引擎）
- [x] SGLang 主题（LLM Program / RadixAttention / 结构化生成）
- [x] TensorRT-LLM 主题（NVIDIA 编译型 LLM 推理引擎）
- [x] Triton Inference Server 主题（多框架推理服务软件）
- [x] LLM Gateway 主题（访问控制与抽象层）
- [x] Agent Runtime 主题（AI Agent 执行容器）
- [x] Memory 主题（AI Agent 记忆系统）
- [x] Multi-Agent 主题（多 Agent 协作系统）
- [x] Reflection 主题（Agent 自我反思与纠错系统）
- [x] MCP 主题（模型上下文协议）
- [x] Planning 主题（Agent 规划系统）
- [x] Tool Use 主题（Agent 工具调用）
- [x] Agent OS 主题（Agent 运行时操作系统）
- [x] RAG 主题（检索增强生成）
- [x] AI SRE 主题（可观测性、可靠性、AIOps）
- [x] 安全主题（IAM、Secrets、Zero Trust、合规）
- [x] OpenAI 案例研究（训练/推理基础设施、安全与对齐）
- [x] Anthropic 案例研究（宪法对齐、可解释性、异构算力、prompt caching）
- [x] Meta 案例研究（开放权重、硬件协同设计、双网络织物、SDC 治理、MTIA 自研硅）
- [ ] 更多主题持续建设中……

## 如何阅读

1. 如果你是新手，建议从 [学习路线](/10-roadmap/learning-path) 开始。
2. 如果你想快速了解一个主题，先看 [阅读指南](/guide)。
3. 如果你关注当前最热门的 LLM 推理引擎，直接阅读 [vLLM 详解](/04-llmops/vllm/)、[SGLang 详解](/04-llmops/sglang/)、[TensorRT-LLM 详解](/04-llmops/tensorrt-llm/)、[Triton 详解](/04-llmops/triton/)、[LLM Gateway 详解](/04-llmops/llm-gateway/)、[Agent Runtime 详解](/05-agent/agent-runtime/)、[Memory 详解](/05-agent/memory/)、[Multi-Agent 详解](/05-agent/multi-agent/)、[Reflection 详解](/05-agent/reflection/)、[MCP 详解](/05-agent/mcp/)、[Planning 详解](/05-agent/planning/)、[Tool Use 详解](/05-agent/tool-use/)、[Agent OS 详解](/05-agent/agent-os/)、[RAG 详解](/06-rag/)、[AI SRE 详解](/07-ai-sre/)、[安全详解](/08-security/) 或 [OpenAI 案例研究](/09-case-study/openai/)、[Anthropic 案例研究](/09-case-study/anthropic/)、[Meta 案例研究](/09-case-study/meta/)。

## 贡献

欢迎通过 GitHub 提交 Issue 和 PR。所有内容采用 CC-BY-SA-4.0 协议授权。

## License

[CC-BY-SA-4.0](https://creativecommons.org/licenses/by-sa/4.0/)
