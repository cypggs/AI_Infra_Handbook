# 企业生产实践

把 Claude 接入企业生产环境，不是"调通 API"这么简单——它涉及多云选型、成本治理、缓存策略、智能体后端、安全合规（RSP/ASL）与容量规划。本章从 Anthropic 公开资料与平台文档中提炼落地经验。

## 1. 三云托管：选哪一朵？

Claude 是目前唯一在三朵最大云（AWS Bedrock、Google Cloud Vertex AI、Microsoft Azure Foundry）以及官方 Claude API 上都可用的前沿模型。选型不只是"哪个便宜"，而是特性矩阵差异：

| 维度 | Claude API | Bedrock | Vertex AI | Azure Foundry |
|---|---|---|---|---|
| 自动缓存（automatic caching） | ✅ | 仅新模型（旧版 Opus 4.6 及更早 ❌） | ❌ | ✅ |
| Prompt Cache 隔离粒度 | workspace | org | org | workspace |
| 区域/数据驻留 | 全球 | 强（AWS 区域） | 强（GCP 区域） | 强（Azure 区域） |
| 企业治理/计费整合 | 独立（2026-10 起 Max/Team 含月度 API 额度） | 与 AWS 账户一体化 | 与 GCP 一体化 | 与 Azure 一体化 |
| 最新模型/特性首发 | 通常首发 | 滞后 | 滞后 | 滞后 |

> 经验：要最低延迟与最新特性（automatic caching、mid-conversation system messages、inline tools 等），用官方 API；要最强数据驻留与企业治理整合，用对应云的托管；要 workspace 级 cache 隔离，避开 Bedrock/Vertex（它们仍是 org 级）。2026-09/10 发布的 5.5 系列（Opus 5.5 / Sonnet 5.5 / Haiku 5.5）在四个入口同步上线，多云选型不受新模型首发限制。

## 2. Prompt Caching：把成本打下来的核心手段

prompt caching 是 Anthropic 推理成本优化的旗舰。生产落地要点：

### 结构化你的 prompt

- **顺序**：`tools → system → messages`，缓存按此层级失效。
- **静态前置**：把不变的 system 指令、工具定义、长文档放在前缀，把每请求变化的字段（时间戳、用户输入）放在断点之后。
- **断点位置**：放在"最后一个跨请求相同的块"上。常见陷阱是把 `cache_control` 放在含时间戳/用户输入的块上——结果每请求 hash 不同，零命中。

### 多断点策略

- 最多 4 个断点。建议：1 个给 tools、1 个给 system、1–2 个给"会增长但前缀稳定"的对话历史。
- 当对话增长超过最后一个写入点 20 个 block 时，回看窗口够不到，需要补一个靠近当前位置的断点。

### TTL 选择

- **5 分钟（默认）**：高频对话、agent 多步循环——每次命中即刷新，不额外收费。
- **1 小时**：用户响应间隔可能超过 5 分钟（如 side-agent 长任务、客服系统），或要改善限流额度利用率（命中不计限流）。

### 预热（pre-warm）

- 用 `max_tokens=0` 在低峰期把 system/tools 写入缓存，消除首个真实请求的 TTFT 惩罚（2026 起为官方正式用法，替代旧的 `max_tokens=1` 技巧）。
- 注意：`max_tokens=0` 不能与 `stream:true`、extended thinking、structured output、`tool_choice` 同时使用。

### 监控 usage 三段式

```
total_input = cache_read_input_tokens + cache_creation_input_tokens + input_tokens
```

- 命中率 = `cache_read / total_input`；目标通常 > 80%。
- 若 `cache_creation` 持续高而 `cache_read` 低，说明断点放在了变化块上，或请求间隔超过 TTL。

### 真实成本量级（以官方倍率估算）

- 缓存读 = base input 的 **0.1x**（Opus 5.5 / Sonnet 5.5 为 **0.05x**，Fable/Mythos 5.1 为 **0.025x**；Haiku 5.5 基础价已低约一个数量级，仍为 0.1x 但分 ≤100k / >100k 两档计价）；5m 写 = **1.25x**；1h 写 = **2x**。
- 一个 10 万 token 的稳定前缀，若每 3 分钟复用一次：首写 1.25x，之后每次仅 0.1x（5.5 系列 0.05x）——相对无缓存可节省约 **90%+** 的前缀处理成本。
- 2026 Q3 的降价节奏值得纳入成本模型：Fable 5.1 缓存读直降 75%（→0.025x）、Sonnet 5.5 缓存读 $0.20→$0.10 /MTok（典型 agentic 负载约 -20%）、Opus 5.5 以低 40% 成本达到 Fable 5.1 水平（旗舰能力下放）。选型时"用上一代旗舰还是新一代 Opus"要按新价格重新算。
- 配合 **Batch API**（离线批处理折扣）可进一步叠加节省（倍率可叠加）；2026-10 起 Max/Team 订阅包含月度 API 额度，订阅与按量计费的边界进一步模糊。

## 3. Extended Thinking 与智能体后端

- **Thinking budget**：为复杂推理分配 token 预算；budget 过大会拖高延迟与成本，需按任务难度动态设置。
- **Thinking block 保留**：在 Opus 4.5+/Sonnet 4.6+ 默认保留 thinking block，且可被缓存复用——工具循环中把 thinking 块原样回传能显著降低重复推理成本。
- **Computer / Tool Use 沙箱**：智能体的工具执行必须放在受限沙箱（文件系统、网络、权限边界），与 [Tool Use 详解](/05-agent/tool-use/) 的安全实践一致。
- **多步循环 + 缓存**：Agent 每一步都重放 system/tools/历史，prompt caching 几乎是必需，否则成本不可控。
- **托管智能体运行时（2026）**：Claude Managed Agents（2026-04 public beta）把沙箱执行、OAuth 凭据、会话 checkpoint、审计追踪托管给 Anthropic，按会话时长（约 $0.08/会话小时）+ token 计费；配套能力包括 **Dreaming**（空闲时复盘历史会话、更新记忆实现跨会话自我改进）、**Outcomes**（独立评估智能体按 rubric 自动打分）、**多智能体编排**（主 agent 派单、并行子 agent、共享文件系统、可审计 trace）。客户端从"驱动 agent 循环"简化为"定义目标与验收标准"。

## 4. RSP/ASL 作为企业合规框架

Anthropic 的 RSP 不只约束 Anthropic 自己，也给了企业一个**可借鉴的安全发布框架**：

- **借鉴 if-then 承诺**：企业内部模型发布也可定义"达到 X 能力必须先满足 Y 防护"的门禁。
- **借鉴 Risk Report**：把模型能力、威胁模型、缓解措施、残余风险结构化记录，供合规与审计使用。
- **分类器即基础设施**：ASL-3 的输入/输出分类器思路，可落地为企业自建的 guardrails 服务（参见 [安全详解](/08-security/)）。
- **第三方审查**：对高风险用例引入外部专家评审，提升可信度。
- **政策映射**：RSP 已与 SB 53（加州）、RAISE Act（纽约）、EU AI Act Codes of Practice 对齐，企业可参照同类法规设计合规流程。
- **跟踪 2026 演进**：RSP v3.0（2026-02）拆分公司承诺与行业建议；RSP v3.4（2026-07-08 生效）引入 CB-1/CB-2 阈值，配套 2026-08-14 Risk Report（覆盖至 7-15）披露"接近 CB-2 边界"；2026-10 再进一步——启动**独立评估者计划**（METR 获近似员工级内部访问、可独立发表）并把 Project Glasswing 并入扩展版 **Cyber Verification Program**（对防御方安全团队开放前沿模型能力，配套 Defender Advantage Fund）。对前沿模型（Fable/Mythos 级），Anthropic 采用"分类器路由"（可疑请求降级到 Opus 4.8）+ 30 天数据保留 + 定向开放（Glasswing / Cyber Verification Program）的组合拳——这是"高能力模型如何安全放量"的最新公开范式。

## 5. 容量与可靠性治理

据 NYT/Bloomberg 报道，run-rate 收入从 2025 年底 ~$9B 升至 2026-04 ~$30B、2026 年中 ~$65B，2026-09 已报道超 $100B（增长主力是企业 API + Claude Code + 消费级订阅三头并进，Claude Code run-rate 2026-02 报道达 $2.5B）。这给企业三点启示：

- **容量前置规划**：训练/推理算力扩张有长交付周期（Colossus 19 天建成是特例，5GW 数据中心以年计），需求预测必须领先产能 6–12 个月。
- **增长会反噬产品**：2026-06 Fable 5 上线两周即因容量不足从 Pro/Max/Team 套餐移除（7-01 恢复）；2026-05 大会靠 Colossus 独家算力才把 Claude Code 限流翻倍——前沿实验室也会"算力不够砍产品"，容量就是产品特性。
- **多源算力**：芯片多元化（Trainium + GPU）与多云托管是对冲单一供应链与单点容量风险的现实选择。

## 6. 典型生产架构（企业参考）

```text
用户 → CDN/WAF → LLM Gateway（鉴权/限流/路由/计费）
                  ├─ Claude API（最新特性、automatic caching）
                  ├─ Bedrock（强数据驻留、AWS 治理整合）
                  └─ Foundry/Vertex（多云冗余）
       Gateway 侧：
         - prompt 模板化 + 断点注入（cache_control）
         - usage 三段式采集 → 成本/命中率仪表板
         - extended thinking budget 策略
         - tool/computer use 沙箱执行
         - ASL 风格输入/输出 guardrails
       监控：TTFT、ITL、cache hit rate、成本/请求、安全事件
```

## 7. 常见踩坑

| 现象 | 原因 | 对策 |
|---|---|---|
| cache_read 一直为 0 | 断点放在每请求变化的块上；或低于模型最小可缓存长度 | 断点移到稳定前缀末尾；按模型确认最小 token 阈值（512–4096 分档，低于阈值静默不缓存） |
| Bedrock 上无自动缓存 | 旧版 Bedrock（Opus 4.6 及更早）不支持 automatic caching | 改用显式断点，或切到支持的平台 |
| 跨 workspace 缓存不共享 | Claude API / Foundry / Claude Platform on AWS 按 workspace 隔离 | 同一会话保持同一 workspace |
| 1h cache 反而更贵 | 使用频率高于 5 分钟却选了 1h | 高频用 5m（命中即免费刷新） |
| 工具调用 key 顺序变化导致缓存失效 | 部分语言 JSON key 顺序不确定 | 固化 key 顺序或用稳定序列化 |
| 对话中途加 system 消息缓存失效 | 旧模型不支持 mid-conversation system | 换新型号（Fable 5.1 / 5.5 系列等），其支持中途插入 system 不破坏缓存 |

## 小结

企业落地 Claude 的关键不是"能不能调通"，而是**把 prompt caching 用到极致、按用例选对云、用 RSP 思想搭安全门禁、用多源算力对冲容量风险、并把智能体后端托管化/沙箱化**。下一章把这些经验提炼为可复用的最佳实践。
