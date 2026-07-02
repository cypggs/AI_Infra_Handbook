import type { DefaultTheme } from 'vitepress'

export const sidebar: DefaultTheme.Sidebar = [
  {
    text: '开始',
    items: [
      { text: '首页', link: '/' },
      { text: '阅读指南', link: '/guide' },
    ],
  },
  {
    text: '01. 基础',
    collapsed: false,
    items: [{ text: '概述', link: '/01-foundation/' }],
  },
  {
    text: '02. 云原生',
    collapsed: false,
    items: [{ text: '概述', link: '/02-cloud-native/' }],
  },
  {
    text: '03. AI 平台',
    collapsed: false,
    items: [{ text: '概述', link: '/03-ai-platform/' }],
  },
  {
    text: '04. LLMOps',
    collapsed: false,
    items: [
      { text: '概述', link: '/04-llmops/' },
      {
        text: 'vLLM',
        collapsed: false,
        items: [
          { text: '总览', link: '/04-llmops/vllm/' },
          { text: '1. 背景', link: '/04-llmops/vllm/01-background' },
          { text: '2. 核心思想', link: '/04-llmops/vllm/02-core-ideas' },
          { text: '3. 架构设计', link: '/04-llmops/vllm/03-architecture' },
          { text: '4. Runtime 工作流程', link: '/04-llmops/vllm/04-runtime-workflow' },
          { text: '5. 核心模块', link: '/04-llmops/vllm/05-core-modules' },
          { text: '6. 源码分析', link: '/04-llmops/vllm/06-source-analysis' },
          { text: '7. 工程实践', link: '/04-llmops/vllm/07-mini-demo' },
          { text: '8. 企业生产实践', link: '/04-llmops/vllm/08-production-practice' },
          { text: '9. 最佳实践', link: '/04-llmops/vllm/09-best-practices' },
          { text: '10. 面试题', link: '/04-llmops/vllm/10-interview-questions' },
          { text: '11. 延伸阅读', link: '/04-llmops/vllm/11-further-reading' },
        ],
      },
      {
        text: 'SGLang',
        collapsed: false,
        items: [
          { text: '总览', link: '/04-llmops/sglang/' },
          { text: '1. 背景', link: '/04-llmops/sglang/01-background' },
          { text: '2. 核心思想', link: '/04-llmops/sglang/02-core-ideas' },
          { text: '3. 架构设计', link: '/04-llmops/sglang/03-architecture' },
          { text: '4. Runtime 工作流程', link: '/04-llmops/sglang/04-runtime-workflow' },
          { text: '5. 核心模块', link: '/04-llmops/sglang/05-core-modules' },
          { text: '6. 源码分析', link: '/04-llmops/sglang/06-source-analysis' },
          { text: '7. 工程实践', link: '/04-llmops/sglang/07-mini-demo' },
          { text: '8. 企业生产实践', link: '/04-llmops/sglang/08-production-practice' },
          { text: '9. 最佳实践', link: '/04-llmops/sglang/09-best-practices' },
          { text: '10. 面试题', link: '/04-llmops/sglang/10-interview-questions' },
          { text: '11. 延伸阅读', link: '/04-llmops/sglang/11-further-reading' },
        ],
      },
      {
        text: 'TensorRT-LLM',
        collapsed: false,
        items: [
          { text: '总览', link: '/04-llmops/tensorrt-llm/' },
          { text: '1. 背景', link: '/04-llmops/tensorrt-llm/01-background' },
          { text: '2. 核心思想', link: '/04-llmops/tensorrt-llm/02-core-ideas' },
          { text: '3. 架构设计', link: '/04-llmops/tensorrt-llm/03-architecture' },
          { text: '4. Runtime 工作流程', link: '/04-llmops/tensorrt-llm/04-runtime-workflow' },
          { text: '5. 核心模块', link: '/04-llmops/tensorrt-llm/05-core-modules' },
          { text: '6. 源码分析', link: '/04-llmops/tensorrt-llm/06-source-analysis' },
          { text: '7. 工程实践', link: '/04-llmops/tensorrt-llm/07-mini-demo' },
          { text: '8. 企业生产实践', link: '/04-llmops/tensorrt-llm/08-production-practice' },
          { text: '9. 最佳实践', link: '/04-llmops/tensorrt-llm/09-best-practices' },
          { text: '10. 面试题', link: '/04-llmops/tensorrt-llm/10-interview-questions' },
          { text: '11. 延伸阅读', link: '/04-llmops/tensorrt-llm/11-further-reading' },
        ],
      },
    ],
  },
  {
    text: '05. Agent',
    collapsed: false,
    items: [{ text: '概述', link: '/05-agent/' }],
  },
  {
    text: '06. RAG',
    collapsed: false,
    items: [{ text: '概述', link: '/06-rag/' }],
  },
  {
    text: '07. AI SRE',
    collapsed: false,
    items: [{ text: '概述', link: '/07-ai-sre/' }],
  },
  {
    text: '08. 安全',
    collapsed: false,
    items: [{ text: '概述', link: '/08-security/' }],
  },
  {
    text: '09. 案例研究',
    collapsed: false,
    items: [{ text: '概述', link: '/09-case-study/' }],
  },
  {
    text: '10. 路线与资源',
    collapsed: false,
    items: [
      { text: '概述', link: '/10-roadmap/' },
      { text: '学习路线', link: '/10-roadmap/learning-path' },
      { text: '面试指南', link: '/10-roadmap/interview-guide' },
    ],
  },
]
