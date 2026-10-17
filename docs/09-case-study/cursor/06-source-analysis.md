# 6. 生态与实现分析

Cursor 客户端闭源、服务端不开放，"源码分析"在这里变成**可观测面 + 社区逆向 + 官方披露三角互证**。本章盘点三个信息源，并给出与竞品的路线对照。

## 6.1 可观测面：产品行为即接口

Cursor 客户端虽是闭源桌面应用，但其网络行为、协议形状与文档承诺构成稳定的可观测接口【社区观察汇总】：

- 协议形状：Tab/Chat 走 HTTPS + SSE/流式响应；索引同步有独立的同步端点（社区抓包观察到 Merkle 子树同步与文件更新两类请求）；模型选择随版本与账号档位变化——均为客户端可抓包验证的事实。
- 本地痕迹：客户端本地存在索引与缓存目录、扩展宿主进程、终端代理配置——Agent 工具调用经由本地编排再到云端沙箱的证据链完整【社区】。
- 文档承诺：隐私模式（zero data retention 协议）、索引不存明文、Self-Hosted Machines 的出站长连接架构——这些是一手承诺，配合抓包可做合规审计【一手 + 社区】。

## 6.2 社区逆向分析盘点（机制可信，规模不可信）

| 分析 | 结论要点 | 证据等级 |
|---|---|---|
| Engineer's Codex：索引管线分析 | Merkle 树增量（约 10 分钟周期）、服务端切块嵌入、远端向量库（指认 Turbopuffer）、路径段加密混淆、git 仓库用 commit 哈希派生密钥 | 【社区】机制与官方文档互证；Turbopuffer 指认未经 Cursor 确认 |
| cereblab 抓包项目 | 索引期间向 Cursor 域名上传文件衍生数据（SyncMerkleSubtree / FastUpdateFile 类请求），载荷编码无法判定 | 【社区】证实"有上传"，不证实"存明文" |
| 论坛与逆向汇总（"How Cursor Actually Works"类长文） | Tab 小模型 + 缓存预热 + 投机解码的整体图景；Apply 服务独立部署 | 【社区】与官方博客一致的部分可信；具体参数不可信 |
| Copilot contextual filter 复现（Parth Thakkar 2022） | 补全过滤可用 11 特征逻辑回归达到约 15% 阈值 | 【社区，被 Cursor 官方博客引用】 |

使用纪律：**社区分析用于理解机制（流程、协议形状、算法选择），不用于引用规模数字**（QPS、模型参数量、集群大小）。

## 6.3 开源生态关系

Cursor 本体闭源，但与开源生态的互动清晰可见【一手 + 报道】：

- **技术底座**：编辑器内核长期跟踪 VS Code（MIT 协议），扩展生态兼容是其增长飞轮的一部分；云端沙箱执行端积极拥抱开源/第三方（E2B、Modal、Daytona、Cloudflare Sandboxes 等），2026-09 自我托管方案把"沙箱供应商"做成了可插拔市场。
- **模型底座**：早期 Tab/Apply 微调基于开源权重（Llama 3 70B 口径、DeepSeek Coder 口径）；Composer 2 技术报告披露基座为 Kimi K2.5（1.04T 参数、32B 激活 MoE），经 continued pretraining + RL + self-summarization 改造【一手：arXiv 技术报告】——自研 ≠ 从头预训练，"开源基座 + 场景 RL"是 2025-2026 年的主流路线（参见 [LLM 从零训练](/01-foundation/llm-from-zero/) 主题的讨论）。
- **数据与评测**：Cursor Bench 使用内部真实请求 + 手工标注最优解，官方承认"Best Frontier"（GPT-5/Sonnet 4.5 口径）仍强于 Composer【一手】——评测透明度高于行业均值，但有明显的自家基准偏向。

## 6.4 与竞品路线的对照

| 维度 | Cursor | GitHub Copilot | Claude Code / Codex 类 CLI | Windsurf（已易主） |
|---|---|---|---|---|
| 形态 | AI 原生 IDE | 插件生态（IDE 内） | 终端/编辑器 agent | IDE |
| 补全模型 | 自研 MoE 小模型 + online RL | 多模型（供应商合作） | 不适用（无行内补全主打） | 自研 + 供应商 |
| Apply 落盘 | 整文件重写 + Speculative Edits（官方 ~1000 tok/s） | 差异应用（传统 diff） | 补丁/diff | 流式 diff |
| 编排 | Router（学习系统）+ 云端沙箱 agent | 无自有网关（直连供应商） | 供应商自有模型闭环 | 云端 agent |
| 沙箱 | 自有 VM 池 + 可插拔执行端市场 | 依赖 Copilot coding agent 云服务 | 云端任务执行 | 云端 |
| 商业模式 | 订阅 + 额度池 + 企业席位 | 席位订阅 | 订阅/按量 | 席位订阅（并入 Cognition 后调整） |

三条路线差异的本质是**对"延迟—质量—成本"三角的切法不同**：Cursor 用自有小模型切延迟、用 Router 切成本；Copilot 用渠道与生态切规模；CLI agent 用供应商闭环切质量。Windsurf 的出售则提示：没有自有数据回流与成本对冲的纯 IDE 形态，在 frontier API 成本面前最难独立存活【报道 + 推断】。

## 6.5 本章小结

Cursor 的"源码"在很大程度上是它的官方博客与文档——这在 AI 产品里是难得的透明度。社区逆向补上了协议与客户端的细节，但规模数字永远缺位；本主题 mini-demo 中的数量关系因此全部以教学模型呈现，并在每处对齐可引用的官方口径。
