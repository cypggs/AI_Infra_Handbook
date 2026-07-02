# SGLang

[SGLang](https://github.com/sgl-project/sglang) 是由 LMSYS 团队开发的开源大语言模型推理引擎，主打 **LLM Program 的高效执行**、**RadixAttention 自动前缀缓存** 与 **结构化生成（Structured Generation）**。截至 2026 年 7 月，SGLang 已发展到 [v0.5.14](https://github.com/sgl-project/sglang/releases)，在 Agent、多轮对话、JSON / Function Calling 等场景中具有显著优势。

## 一句话理解

> SGLang 把一次 LLM 调用看作一段可以编译、调度、缓存、约束的程序，让复杂交互场景下的推理既快又可控。

如果说 vLLM 的核心命题是“让通用 LLM 推理更高吞吐”，那么 SGLang 的核心命题是“让 LLM **程序**（多轮、结构化、带控制流）执行得更高效”。

## 本主题结构

1. [背景](01-background)
2. [核心思想](02-core-ideas)
3. [架构设计](03-architecture)
4. [Runtime 工作流程](04-runtime-workflow)
5. [核心模块](05-core-modules)
6. [源码分析](06-source-analysis)
7. [工程实践：Mini Demo](07-mini-demo)
8. [企业生产实践](08-production-practice)
9. [最佳实践](09-best-practices)
10. [面试题](10-interview-questions)
11. [延伸阅读](11-further-reading)

## 学习目标

阅读完本主题后，你应该能够：

- 解释 SGLang 与 vLLM 在设计哲学上的差异
- 说明 RadixAttention 如何利用 Radix Tree 自动复用前缀
- 描述结构化生成（regex / JSON schema / EBNF）的基本原理
- 画出 SGLang Runtime 的核心架构
- 定位 SGLang 源码中的关键模块与调用链
- 实现一个简化的 Radix Tree + FSM 约束采样 Demo
- 在生产环境中判断何时选择 SGLang，以及如何调优

## 与 vLLM 的关系

SGLang 与 vLLM 同源（都来自 LMSYS / Berkeley），但在工程目标上互补：

| 维度 | vLLM | SGLang |
|---|---|---|
| 核心问题 | 通用高吞吐 LLM 推理 | 复杂 LLM 程序的高效执行 |
| 缓存机制 | PagedAttention（Block Table） | RadixAttention（Radix Tree） |
| 结构化生成 | 通过第三方后端支持 | 原生深度集成（xgrammar / FSM） |
| 编程模型 | 单次 completion | `gen` / `select` / `fork` / `run` 等程序原语 |
| 适用场景 | 通用在线推理 | Agent、多轮对话、JSON/Function Calling |

建议先阅读 [vLLM 详解](/04-llmops/vllm/)，再学习 SGLang，会更容易理解二者在 KV cache 管理、调度、约束解码上的异同。
