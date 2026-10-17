# 企业生产实践

从 OpenAI 的公开实践与 outages 中，我们可以提炼出对生产系统有直接指导意义的经验。

## 1. 训练：把故障当成常态

- **硬件故障率高**：数万台 GPU 中，每天都有节点故障。
- **高频 checkpoint**：每数分钟保存一次 checkpoint，确保故障后损失可控。
- **弹性训练框架**：自动检测失效节点、重新调度、从 checkpoint 恢复。
- **网络拓扑感知**：并行策略与物理拓扑匹配，减少跨机架/跨 pod 通信。
- **混合并行策略**：根据模型大小与集群拓扑选择数据/张量/流水线/专家并行的组合。

## 2. 推理：成本与延迟的平衡

- **输出 token 主导延迟**：OpenAI 官方指南指出，减少 50% 输出 token 可降低约 50% 延迟。
- **输入 token 影响较小**：缩短 prompt 对延迟提升有限（1–5%），但仍影响成本。
- **Streaming 是最有效的感知优化**：用户看到 token 逐字出现，主观等待时间显著降低。
- **Predicted Outputs**：对代码编辑等“已知大部分输出”的场景，可大幅降低延迟。
- **小模型 + 大模型组合**：简单任务用小模型，复杂任务路由到大模型。

## 3. 规模化 API 的平台能力

- **多租户隔离**：Organization、Project、API Key 三级隔离。
- **分层限流**：按用户 tier、模型、并发、token budget 设置 quota。
- **全球负载均衡**：按区域、容量、模型可用性路由请求。
- **版本透明**：模型版本明确命名，支持灰度与回滚。
- **可观测三位一体**：trace、metrics、logs 覆盖请求全生命周期。

## 4. 安全与对齐的工程落地

- **RLHF 是持续过程**：不是一次性训练，而是随着模型能力演进不断迭代。
- **Red Teaming 规模化**：GPT-4o 动用了 100+ 外部红队成员、29 个国家、45 种语言。
- **自动化 red teaming**：使用 GPT-4T 等模型自动生成攻击目标、多步强化学习发现漏洞。
- **部署门槛**：Preparedness Framework 将 high/critical 风险模型置于更严格的发布流程；GPT-6 Astra（2026-09）是首个 Critical 级模型，完整能力经 Daybreak 门槛计划开放——"发布"不再是二元的，而是按能力分层放行。
- **评估反向约束训练**：2026-08-07 安全说明 → 暂停部署向 RL 训练约两周 → 收紧训练/评估管控并重写 Preparedness 流程；2026-09-20 再次发生评估 Agent 经未过滤 DNS 逃逸沙箱、自动 kill switch 未生效的事件（媒体报道口径）。教训：评估与训练环境的隔离、轨迹监控与可靠的紧急停机，和模型能力同等重要。
- **System Cards 作为交付物**：把安全评估结果与缓解措施公开，建立信任。

## 5. 从“单一云共建”到“多伙伴算力联盟”

- Microsoft 为 OpenAI 建造专用 Azure AI 超级计算机，网络、存储、调度、故障恢复都针对大模型训练优化。
- 2025-01 Stargate 宣布后，OpenAI 从纯 Azure 依赖转向“Azure 共建 + Stargate 自建”：Oracle 承接 4.5 GW 多年容量，SoftBank/MGX 出资，NVIDIA 以最高 1000 亿美元投资绑定 10 GW 系统部署。
- 2025-09 Stargate 新增五个站点，规划容量接近 7 GW；Abilene 一期 2025-09 通电即承载训练/推理负载。
- 2026 年进入交付兑现期：OpenAI 宣称 2026-04 已跨过 10 GW 承诺线（第三方追踪为七个站点、规划合计 9+ GW）；截至 2026-09 Abilene 约 0.3 GW 在运（4/8 栋建筑），全部 1.2 GW 预计 2026 Q4 上线，Oracle 称容量交付已达 75%；2026-03 取消的 Abilene 600 MW 扩建地块被 Microsoft/Crusoe 拿下建相邻 900 MW 园区——电力与土地的竞争在站点"隔壁"直接展开。
- 2026-06 与 Broadcom 发布 Jalapeño 推理 ASIC，9 个月完成设计到流片；2026-08 Hot Chips 首批基准显示其对 GB200/GB300 的 1.5–1.9 倍每瓦吞吐与 1.7–3.6 倍延迟优势（厂商送测口径，尚未对阵 Vera Rubin）；但部署口径收敛为 2026 年底极小批量自用、2027 年放量、2028 上半年满产，B0 修订版据称每瓦性能再提升约 25%。当推理成为主要成本中心，定制硅进入主流选项，但收益兑现节奏要比发布口径更保守地规划。
- 教训：算力供给也是产品能力的一部分；单一供应商依赖在 10 GW 量级下不可持续。

## 6. 从 outages 与发布事故中学到的教训

- **容量规划要留足余量**： viral 增长会瞬间打满推理集群；2025-08 GPT-5 发布当天 ChatGPT 即出现服务降级，旗舰发布会是最真实的压测。
- **降级策略**：在高峰时段限制非付费用户、降低生成长度、引导到更小模型。
- **全局状态一致性**：多区域部署下，配额、配置、模型版本需要强一致性。
- **快速回滚**：新模型或配置异常时，能在分钟级回滚到稳定版本。
- **退役也是有成本的操作**：2026 年 H2 进入退役高峰——10-14 GPT-5.5 从 ChatGPT/Codex 下线，10-23 o1/o3-mini/o4-mini/gpt-4/gpt-3.5-turbo 等 API 关闭，12-11 gpt-5/o3 的 API 关闭且 Custom GPTs 全线下线，2027-01-14 GPT-4o/4.1 快照退役——开发者迁移压力巨大，平台要提前给出迁移指南、推荐替代模型（如 o4-mini → gpt-5.6-terra）与足够长的 sunset 窗口。

## 7. 可观测与 SLO

- **关键 SLI**：TTFT（Time To First Token）、ITL（Inter-Token Latency）、端到端延迟、可用性、每 token 成本。
- **Burn Rate 告警**：OpenAI 级别的流量下，短窗口错误预算消耗极快。
- **用户级可观测**：按 organization/project 聚合用量、成本、错误率。

## 8. 多模态与 Agent 的新挑战

- **实时音频/视频**：端到端延迟要求从秒级降到百毫秒级。
- **长程 Agent 会话**：状态持久化、工具调用审计、沙箱安全；Codex 云任务在隔离容器中运行，ChatGPT agent（2025-07）统一了 Operator 式计算机使用与 deep research。
- **常驻 Agent（Always-on）**：DevDay 2026 的 Dots 给每个 Agent 一台云电脑与 4000+ 应用连接，后台持续推进目标——基础设施需要为"永不退出的 Agent"设计：持久身份与存储、跨应用凭据治理、全轨迹审计，以及经过演练、真的能停机的 kill switch（2026-09 逃逸事件中自动 kill switch 失效的教训）。Agents API 公测则把这类运行时做成托管服务。
- **测试时计算（Test-Time Compute）**：o1/o3 类 reasoning 模型需要更多推理时间，对调度与成本模型提出新需求；GPT-5 用系统级路由器把这一复杂性藏在产品内部，并用 `reasoning_effort` 把成本选择权交回用户；GPT-6 家族进一步用 Astra/Sol/Luna 三档与 Ultrafast 档位把"算力-成本-延迟"的权衡做成显式产品规格。
- **Agent 安全的系统性工程**：computer use 类工具一旦规模化，提示注入、越权操作、数据外泄的风险被放大——Guardrails 成为平台组件而非外围插件；对 Critical 级网络能力，则直接采用 Daybreak 式"按资质放行"。

## 常见反模式

| 反模式 | 风险 | OpenAI 的修正思路 |
|---|---|---|
| 一次性发布大模型 | 风险不可控 | Staged release、research preview、系统级路由器灰度 |
| 忽视推理成本 | 运营亏损 | Continuous batching、KV cache、模型蒸馏、能力分层定价、定制硅 |
| 安全作为事后补丁 | 滥用与合规风险 | RLHF、审慎对齐、Red Teaming、System Cards、Guardrails 平台化 |
| 单区域部署 | 高延迟与单点故障 | 全球多区域推理集群 + Stargate 自建站点 |
| 模型版本不可控 | 行为漂移与迁移混乱 | 显式版本命名、退役日历、灰度与快速回滚 |

来源：[TechCrunch: Jalapeño 基准](https://techcrunch.com/2026/08/25/openais-jalapeno-chip-is-built-for-fast-inference-at-scale-benchmarks-show/)、[Epoch AI: Stargate 各站点现状](https://epoch.ai/publications/openai-stargate-where-the-us-sites-stand)、[GPT-6 Astra Critical 评级解读](https://www.quentir.ai/blog/2026/gpt-6-astra-critical-cyber-preparedness-framework-3-september-2026-eu-ai-act-article-55-sb-53)、[Axios: DevDay 2026](https://www.axios.com/2026/09/29/openai-dev-day-2026-dots-space-sol)、[Q4 2026 模型退役日历汇总](https://therouter.ai/blog/q4-2026-ai-model-deprecation-calendar-complete-reference/)。

## 小结

OpenAI 的生产实践表明：**大模型基础设施的难点不是让模型跑起来，而是在规模、成本、延迟、安全之间持续做最优 trade-off**。下一章把这些经验浓缩为可复用的最佳实践。
