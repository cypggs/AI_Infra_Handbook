# 11. 延伸阅读

## 一手来源（官方博客 / 文档 / 技术报告）

- Cursor 官方博客：[instant-apply](https://cursor.com/blog/instant-apply)（Fast Apply 与 Speculative Edits，~1000 tok/s、13x/9x 口径）；[tab-rl](https://cursor.com/blog/tab-rl)（online RL：+0.75/−0.25 奖励、1.5-2h checkpoint、-21%/+28%）；[composer](https://cursor.com/blog/composer)（自研 MoE agent 模型、PyTorch+Ray RL 栈、数十万并发沙箱）；[composer-2-5](https://cursor.com/blog/composer-2-5) 与 [self-summarization](https://cursor.com/blog/self-summarization)（长程训练）；[router](https://cursor.com/blog/router)（Router：AFC/keep rate、cost per commit）；[june-2025-pricing](https://cursor.com/blog/june-2025-pricing)（定价复盘与退款）；[self-hosted-machines](https://cursor.com/blog/self-hosted-machines)（工具执行下沉）。
- 官方文档：[Cloud Agents](https://cursor.com/docs/cloud-agent)（云端沙箱）；代码库索引与 Instant Grep（cursor.com/docs，含"不为搜索存储嵌入"的明示）；隐私/安全说明（索引不存明文、zero data retention）。
- 技术报告：[Composer 2 Technical Report](https://arxiv.org/html/2603.24477v2)（基座 Kimi K2.5、1.04T/32B-active MoE、Terminal-Bench 2.0 61.7%、$0.50/$2.50 每 M token）。
- 访谈：Lex Fridman Podcast #447 —— [Cursor Team 完整文字稿](https://lexfridman.com/cursor-team-transcript/)（Tab 小模型/MoE、消除低熵动作、缓存预热、multi-query 注意力）。

## 媒体报道（商业数字全部出自此类来源）

- TechCrunch：[2025-06-05：$900M / $9.9B 估值 / $500M ARR](https://techcrunch.com/2025/06/05/cursors-anysphere-nabs-9-9b-valuation-soars-past-500m-arr/)；[2025-04-17：OpenAI 曾洽购 Anysphere](https://techcrunch.com/2025/04/17/openai-pursued-cursor-maker-before-entering-into-talks-to-buy-windsurf-for-3b/)；[2026-04-21：SpaceX 期权协议](https://techcrunch.com/2026/04/21/spacex-is-working-with-cursor-and-has-an-option-to-buy-the-startup-for-60-billion/)；[2026-04-22：如何截胡 $2B 融资](https://techcrunch.com/2026/04/22/how-spacex-preempted-a-2b-fundraise-with-a-60b-buyout-offer/)；[2026-06-16：$60B 全股票收购](https://techcrunch.com/2026/06/16/spacex-to-acquire-cursor-for-60b-in-stock-days-after-blockbuster-ipo/)；[2026-08-15：交易交割](https://techcrunch.com/2026/08/15/spacex-officially-closes-its-cursor-acquisition/)。
- Fortune：[OpenAI-Windsurf $3B 交易崩塌与 Google 接盘](https://fortune.com/2025/07/11/the-exclusivity-on-openais-3-billion-acquisition-for-coding-startup-windsfurf-has-expired/)（AI 编程工具成本结构的公开注脚）。
- Bloomberg（经 TechCrunch 等转引）：ARR 各节点数字；SpaceX 收购后 OpenAI 断供决定（报道口径，截至知识截止无一手公告）。

## 社区分析（机制可参考，规模数字不可引用）

- Engineer's Codex：[How Cursor Indexes Codebases Fast](https://read.engineerscodex.com/p/how-cursor-indexes-codebases-fast)（Merkle 增量、Turbopuffer 指认、路径混淆、10 分钟同步周期）。
- [cereblab/cursor-indexing-capture](https://github.com/cereblab/cursor-indexing-capture)（索引流量抓包，证实上传存在、载荷不可判定）。
- Copilot contextual filter 复现（Parth Thakkar 2022，被 Cursor 官方博客引用）。

## 合作方一手材料

- Cloudflare 官方新闻稿：[Cursor Cloud Agents on Cloudflare Sandboxes](https://www.cloudflare.com/press/press-releases/2026/cloudflare-expands-support-for-ai-coding-agents-with-cursor-cloud-agents-on-cloudflare-sandboxes/)（2026-09-02）。
- Fireworks：[Cursor Fast Apply 案例](https://fireworks.ai/case-study/cursor)（定制投机解码的推理引擎合作口径）。

## 手册内交叉引用

- [OpenAI 案例研究](/09-case-study/openai/)：模型供应商视角；洽购与断供博弈的对照。
- [Perplexity 案例研究](/09-case-study/perplexity/)：同为"不训基础模型起家"的推理经济学案例；tail latency 哲学同源。
- [xAI 案例研究](/09-case-study/xai/)：SpaceX/xAI 合并后收购 Cursor；Colossus 算力接入口径。
- [LLM Gateway](/04-llmops/llm-gateway/)：Router 是学习系统形态的多模型网关案例。
- [vLLM](/04-llmops/vllm/)：开源推理引擎对照系；理解 Fireworks 商业栈的坐标。
- [向量数据库与 Embedding 基础设施](/06-rag/vector-db/)：嵌入索引 vs 即时词法索引的产品化裁决。
- [Personal AI Agent](/05-agent/personal-agent/)：编程 agent 的个人化产品形态。
- [Agent Runtime](/05-agent/agent-runtime/)：云端沙箱与 VM 调度器的规模化样本。
- [AI 编译器](/04-llmops/ai-compiler/)：MXFP8 MoE kernel 与混合并行落到自研训练栈。

## 信息核实声明

1. 技术机制（Tab 小模型/MoE、Speculative Edits、online RL 奖励与 checkpoint 节奏、Router 指标与 cost per commit、Composer 训练栈、索引 Merkle 增量与混淆）均有一手官方来源，正文中以【一手】标注。
2. 所有商业数字（融资额、估值、ARR、用户数、收购结构与时间线）来自 TechCrunch/Bloomberg/Fortune 等媒体报道，公司未发布经审计的对应口径，正文中以【报道】标注。
3. "OpenAI 将于 2026-11-12 对 Cursor 断供"截至知识截止（2026-10-17）无双方一手公告，仅按媒体报道转述。
4. Turbopuffer 作为索引向量库、Copilot 过滤器特征数等细节来自社区分析，Cursor 未确认，正文以【社区】标注。
5. 文中所有延迟分解、命中率曲线、毛利率计算如注明"教学模型"则为本主题 Mini Demo 的合成值，仅用于演示量级关系。
