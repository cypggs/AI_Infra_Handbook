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
