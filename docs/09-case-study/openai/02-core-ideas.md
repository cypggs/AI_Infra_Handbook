# 核心思想

OpenAI 的工程体系建立在几个贯穿始终的思想上。理解这些思想，比记住具体技术选型更重要。

## 1. Scale is All You Need（规模化是一切的答案）

OpenAI 坚信：当模型、数据、计算三者同时规模化时，能力会涌现。

- **参数规模**：GPT-3 175B → GPT-4 估算万亿级 MoE → GPT-5 起不再公开参数细节。
- **数据规模**：训练 token 从千亿级增长到万亿级。
- **计算规模**：训练集群从数千 A100 到数万 H100/H200，再到 GB200 NVL72 机柜与 Stargate 规划的 10 GW 级数据中心网络。

这直接决定了基础设施目标：**让训练任务能够高效地吃掉更多 GPU 和更多数据**。2025 年后这个命题进一步扩展为：能不能吃掉更多电力（Stargate）、更多异构算力（NVIDIA + 自研 Jalapeño 推理芯片）。

## 2. API-First 与产品化优先

OpenAI 很早就把 API 作为核心产品，而不是只做研究发布。

- **统一接口**：OpenAI-compatible API 成为行业标准。
- **多租户与计费**：按 token、按模型、按 tier 计费；reasoning 模型还要对“思考 token”单独计量与定价。
- **灰度与版本**：模型版本透明暴露（`gpt-4-1106-preview`、`gpt-4o`），开发者可自由选择；2025 年后升级为明确的退役日历（如 o4-mini 于 2026-10-23 关闭）。
- **从补全到 Agent 原语**：2025-03 发布 Responses API 与 Agents SDK，把工具调用循环（web search、file search、computer use）做成 API 内建能力；2025-10 DevDay 推出 AgentKit 与 Apps SDK；2026-09 DevDay 再进一步推出 **Agents API 公测**（基于 Codex harness 的托管 Agent 运行时，内建 computer use、tool search 与多 Agent 协调）与常驻 Agent 产品 Dots。值得注意的是，hosted Agent Builder / Evals 平台于 2026-06 宣布弃用、计划 2026-11-30 关停，Agent 编排能力回归开源 Agents SDK——"平台化"与"开源 SDK"之间在做再平衡（报道口径）。

API-first 意味着基础设施必须支持：限流、路由、降级、多区域、可观测。

## 3. 迭代部署（Iterative Deployment）

OpenAI 不追求一次性发布完美模型，而是通过渐进式部署收集反馈、降低风险。

- **Staged Release**：GPT-2 从 small 到 full；GPT-4 先 API 后 ChatGPT。
- **Research Preview**：ChatGPT 最初就是 research preview。
- **模型版本管理**：用日期/代号区分版本，支持回滚。
- **系统级灰度**：GPT-5（2025-08）把”选模型”改成系统内置实时路由器——简单问题走快模型、复杂问题自动切推理模型，流量比例与路由策略由平台侧灰度控制，而不是让用户先选模型。
- **门槛访问（Gated Access）作为新灰度形态**：对高能力模型不再只是”按比例放量”，而是按用户资质放行。GPT-6 Astra 的 Critical 级网络安全能力被置于 **Daybreak** 计划之下——只有通过审查的防御性安全伙伴才能访问完整能力，普通用户与默认 API 走能力受限路径。
- **有终点的生命周期**：新模型上线同时公布旧模型退役日期；2026 年下半年进入退役高峰——2026-10-14 GPT-5.5 从 ChatGPT/Codex 退役，2026-10-23 o1/o3-mini/o4-mini/gpt-4/gpt-3.5-turbo 等大批旧模型 API 关闭，2026-12-11 gpt-5 系列与 o3 的 API 关闭且 Custom GPTs 全线下线，2027-01-14 GPT-4o/4.1 快照退役（推荐替代 gpt-6-luna）。迭代部署的另一半是”有序下线”。

基础设施必须支持快速切换模型版本、流量比例与路由策略。

## 4. 安全与对齐是基础设施的一部分

OpenAI 把 RLHF、Red Teaming、Preparedness Framework 嵌入模型开发生命周期，而不是事后补丁。

- **对齐训练**：RLHF、基于规则的奖励（Rule-Based Rewards, RBR）、拒绝训练；o 系列起引入**审慎对齐（Deliberative Alignment）**——训练模型在思维链中显式推理安全规范后再作答（o1 在 StrongREJECT 越狱基准上从 GPT-4o 的 0.37 提升到 0.88）。
- **行为规格**：约 2.8 万词的公开 [Model Spec](https://model-spec.openai.com/) 定义模型目标、硬性规则与默认行为，作为对齐训练的目标规格（2024-05 首发，2025 年多次修订）。
- **评估体系**：Preparedness Framework 四类风险（cybersecurity、CBRN、persuasion、autonomy），2025-04 发布 v2：风险等级简化为 High/Critical 两级，并要求每个模型发布 Capabilities Report 与 Safeguards Report 两份公开报告。
- **Critical 成为现实**：2026-09-03 发布的 GPT-6 Astra 是首个按该框架被评为 **Critical 级网络安全能力**的模型（System Card 报告其 ExploitBench 得分 100%，对比 GPT-5.6 Sol 的 78.5%，并在授权测试中发现两个零日漏洞；对越狱尝试的网络攻击拒绝率约 91.5%）。发布前 OpenAI 于 2026-08-07 公开安全说明，承认"无法排除 Critical 级网络能力"，随即暂停部署向 RL 训练约两周并收紧训练/评估管控（加密 checkpoint、执行隔离、全轨迹监控），同时重写 2023 版 Preparedness 框架——安全评估首次实质性地**反向约束了训练计划**。
- **红队**：数百名外部红队成员、多语言、多模态测试，并用模型自动生成攻击目标 + 多步 RL 做自动化红队。
- **System Cards**：发布时附带安全评估与缓解措施（如 [GPT-5 System Card](https://cdn.openai.com/pdf/8124a3ce-ab78-4f06-96eb-49ea29ffb52f/gpt5-system-card-aug7.pdf)）。

## 5. 成本意识贯穿设计与运营

OpenAI 多次公开提到推理成本优化。

- **模型蒸馏**：用小模型处理简单任务。
- **KV cache 优化**：减少重复计算。
- **Batching**：continuous batching 提高 GPU 利用率。
- **Predicted Outputs**：对已知输出结构提前生成，降低延迟。
- **推理路由**：GPT-5 的系统内置路由器按问题复杂度在快模型与推理模型间切换，把“选对模型”的省钱逻辑下沉到平台侧；`reasoning_effort`（low/medium/high）等参数让用户用质量换成本。
- **自适应推理与分层计费**：GPT-5.1 引入 adaptive reasoning，模型自行决定思考多久；GPT-5.6 起用 Sol/Terra/Luna 能力分层命名，把”该花多少钱”变成显式产品档位；GPT-6 家族（2026-09）延续并简化为三档——旗舰 Astra（$10/$50 每百万 token）、中档 Sol（$2/$10）、入门 Luna（$0.10/$0.50），Sol/Luna 发布即宣布”永久性降价”而非促销价；DevDay 2026 还新增 **Ultrafast** 推理档位，用更低延迟换取更高单价。
- **定制硅**：2026-06 与 Broadcom 发布 Jalapeño 推理 ASIC，目标用更高每瓦性能降低长期推理成本；2026-08 Hot Chips 公布首批基准（SemiAnalysis InferenceX：对 GB200/GB300 的 1.5–1.9 倍每瓦吞吐、1.7–3.6 倍端到端延迟优势，厂商送测口径），但部署节奏收敛为 2026 年底极小批量自用、2027 年放量、2028 上半年满产——定制硅的收益兑现比发布时更谨慎。

## 6. 研究工程一体化

OpenAI 的研究与工程团队紧密协作：

- 研究者提出新架构，工程师负责 scale。
- 训练基础设施的改进（如更好的并行策略）直接转化为研究能力。
- 产品反馈（ChatGPT 用户行为）反过来指导模型改进。

## 7. 从“单一云伙伴”到“多伙伴算力联盟”

早期 OpenAI 自己不运营数据中心，与 Microsoft 深度 co-design：

- Microsoft 为 OpenAI 建造专用 Azure AI 超级计算机。
- OpenAI 的需求驱动 Azure ND H100 v5、InfiniBand 网络等基础设施演进。
- Azure OpenAI Service 让 Microsoft 企业客户也能使用 OpenAI 模型。

2025 年起格局变化：Stargate 引入 SoftBank、Oracle、MGX 等多方资本与建设方；Oracle 拿下 4.5 GW、超 3000 亿美元的多年容量合同；NVIDIA 宣布最高 1000 亿美元投资 OpenAI 并部署至少 10 GW NVIDIA 系统；2026 年 OpenAI 自有推理芯片 Jalapeño 流片。基础设施战略从”绑定一个云”变成**”Azure 深度共建 + Stargate 自建 + 多芯算力”的组合**。到 2026 年下半年，Stargate 进入”交付兑现”阶段：OpenAI 宣称 2026-04 已提前跨过 10 GW 承诺线（第三方追踪口径为七个在建/在运站点、规划合计 9+ GW）；旗舰 Abilene 站点截至 2026-09 约 0.3 GW 在运（8 栋建筑中的 4 栋），全部 1.2 GW 预计 2026 Q4 上线，Oracle 称其容量交付已达 75%；原计划 2026-03 取消的 Abilene 600 MW 扩建地块由 Microsoft 联手 Crusoe 拿下建设相邻 900 MW 园区——电力与土地争夺进入”邻居拼速度”阶段。

来源：[Stargate 新增五座数据中心](https://openai.com/index/five-new-stargate-sites/)、[OpenAI × Broadcom Jalapeño](https://openai.com/index/openai-broadcom-jalapeno-inference-chip/)、[TechCrunch: Jalapeño 基准](https://techcrunch.com/2026/08/25/openais-jalapeno-chip-is-built-for-fast-inference-at-scale-benchmarks-show/)、[Epoch AI: Stargate 各站点现状](https://epoch.ai/publications/openai-stargate-where-the-us-sites-stand)、[Axios: DevDay 2026](https://www.axios.com/2026/09/29/openai-dev-day-2026-dots-space-sol)。

## 小结

OpenAI 的核心思想可以概括为：**用规模化驱动能力，用 API 产品化能力，用迭代部署降低风险，用对齐与安全治理责任，用成本优化支撑可持续性**。下一章把这些思想映射到具体架构。
