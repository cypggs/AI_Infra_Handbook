import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'
import { sidebar } from './sidebar'

// https://vitepress.dev/reference/site-config
export default withMermaid(
  defineConfig({
    lang: 'zh-CN',
    title: 'AI Infra Handbook',
    description: '面向 AI Infrastructure 工程师的开源中文知识库',

    lastUpdated: true,
    cleanUrls: true,

    markdown: {
      lineNumbers: true,
      config: (md) => {
        // 可在此注册自定义 markdown-it 插件
      },
    },

    themeConfig: {
      // https://vitepress.dev/reference/default-theme-config
      nav: [
        { text: '首页', link: '/' },
        { text: '阅读指南', link: '/guide' },
        { text: '学习路线', link: '/10-roadmap/learning-path' },
        {
          text: 'LLMOps',
          items: [
            { text: 'vLLM', link: '/04-llmops/vllm/' },
            { text: 'SGLang', link: '/04-llmops/sglang/' },
            { text: 'TensorRT-LLM', link: '/04-llmops/tensorrt-llm/' },
            { text: 'Triton Inference Server', link: '/04-llmops/triton/' },
            { text: 'LLM Gateway', link: '/04-llmops/llm-gateway/' },
          ],
        },
        {
          text: 'Agent',
          items: [
            { text: 'Agent Runtime', link: '/05-agent/agent-runtime/' },
            { text: 'Memory', link: '/05-agent/memory/' },
            { text: 'Multi-Agent', link: '/05-agent/multi-agent/' },
            { text: 'Reflection', link: '/05-agent/reflection/' },
            { text: 'MCP', link: '/05-agent/mcp/' },
            { text: 'Planning', link: '/05-agent/planning/' },
            { text: 'Tool Use', link: '/05-agent/tool-use/' },
            { text: 'Agent OS', link: '/05-agent/agent-os/' },
          ],
        },
        {
          text: 'RAG',
          items: [
            { text: '概述', link: '/06-rag/' },
            { text: '1. 背景', link: '/06-rag/01-background' },
            { text: '2. 核心概念', link: '/06-rag/02-core-ideas' },
            { text: '3. 架构设计', link: '/06-rag/03-architecture' },
            { text: '4. RAG 流水线', link: '/06-rag/04-rag-pipeline' },
            { text: '5. 核心模块', link: '/06-rag/05-core-modules' },
            { text: '6. 源码与生态分析', link: '/06-rag/06-source-analysis' },
            { text: '7. Mini Demo', link: '/06-rag/07-mini-demo' },
            { text: '8. 企业生产实践', link: '/06-rag/08-production-practice' },
            { text: '9. 最佳实践', link: '/06-rag/09-best-practices' },
          ],
        },
        {
          text: 'AI SRE',
          items: [
            { text: '概述', link: '/07-ai-sre/' },
            { text: '1. 背景', link: '/07-ai-sre/01-background' },
            { text: '2. 核心概念', link: '/07-ai-sre/02-core-ideas' },
            { text: '3. 架构设计', link: '/07-ai-sre/03-architecture' },
            { text: '4. AI SRE 工作流程', link: '/07-ai-sre/04-ai-sre-workflow' },
            { text: '5. 核心模块', link: '/07-ai-sre/05-core-modules' },
            { text: '6. 源码与生态分析', link: '/07-ai-sre/06-source-analysis' },
            { text: '7. Mini Demo', link: '/07-ai-sre/07-mini-demo' },
            { text: '8. 企业生产实践', link: '/07-ai-sre/08-production-practice' },
            { text: '9. 最佳实践', link: '/07-ai-sre/09-best-practices' },
          ],
        },
        {
          text: '安全',
          items: [
            { text: '概述', link: '/08-security/' },
            { text: '1. 背景', link: '/08-security/01-background' },
            { text: '2. 核心思想', link: '/08-security/02-core-ideas' },
            { text: '3. 架构设计', link: '/08-security/03-architecture' },
            { text: '4. AI 安全生命周期', link: '/08-security/04-security-lifecycle' },
            { text: '5. 核心模块', link: '/08-security/05-core-modules' },
            { text: '6. 源码与生态分析', link: '/08-security/06-source-analysis' },
            { text: '7. Mini Demo', link: '/08-security/07-mini-demo' },
            { text: '8. 企业生产实践', link: '/08-security/08-production-practice' },
            { text: '9. 最佳实践', link: '/08-security/09-best-practices' },
          ],
        },
        {
          text: '案例研究',
          items: [
            { text: '概述', link: '/09-case-study/' },
            { text: 'OpenAI 总览', link: '/09-case-study/openai/' },
            { text: '1. 背景', link: '/09-case-study/openai/01-background' },
            { text: '2. 核心思想', link: '/09-case-study/openai/02-core-ideas' },
            { text: '3. 架构设计', link: '/09-case-study/openai/03-architecture' },
            { text: '4. 训练与推理', link: '/09-case-study/openai/04-training-and-inference' },
            { text: '5. 核心模块', link: '/09-case-study/openai/05-core-modules' },
            { text: '6. 源码与生态分析', link: '/09-case-study/openai/06-source-analysis' },
            { text: '7. Mini Demo', link: '/09-case-study/openai/07-mini-demo' },
            { text: '8. 企业生产实践', link: '/09-case-study/openai/08-production-practice' },
            { text: '9. 最佳实践', link: '/09-case-study/openai/09-best-practices' },
          ],
        },
      ],

      sidebar,

      editLink: {
        pattern: 'https://github.com/case/ai-infra-handbook/edit/main/docs/:path',
        text: '在 GitHub 上编辑此页',
      },

      socialLinks: [
        { icon: 'github', link: 'https://github.com/case/ai-infra-handbook' },
      ],

      footer: {
        message: 'Released under CC-BY-SA-4.0 License.',
        copyright: 'Copyright © 2026-present AI Infra Handbook Contributors',
      },

      search: {
        provider: 'local',
      },

      outline: {
        level: [2, 3],
        label: '目录',
      },

      docFooter: {
        prev: '上一篇',
        next: '下一篇',
      },

      lastUpdatedText: '最后更新',
      returnToTopLabel: '回到顶部',
      sidebarMenuLabel: '菜单',
      darkModeSwitchLabel: '主题',
    },

    sitemap: {
      hostname: 'https://ai-infra-handbook.vercel.app',
    },
  })
)
