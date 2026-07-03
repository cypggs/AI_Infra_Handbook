# 企业生产实践

把 Claude 接入企业生产环境，不是"调通 API"这么简单——它涉及多云选型、成本治理、缓存策略、智能体后端、安全合规（RSP/ASL）与容量规划。本章从 Anthropic 公开资料与平台文档中提炼落地经验。

## 1. 三云托管：选哪一朵？

Claude 是目前唯一在三朵最大云（AWS Bedrock、Google Cloud Vertex AI、Microsoft Azure Foundry）以及官方 Claude API 上都可用的前沿模型。选型不只是"哪个便宜"，而是特性矩阵差异：

| 维度 | Claude API | Bedrock | Vertex AI | Azure Foundry |
|---|---|---|---|---|
| 自动缓存（automatic caching） | ✅ | ❌ | ❌ | ✅ |
| Prompt Cache 隔离粒度 | workspace | org | org | workspace |
| 区域/数据驻留 | 全球 | 强（AWS 区域） | 强（GCP 区域） | 强（Azure 区域） |
| 企业治理/计费整合 | 独立 | 与 AWS 账户一体化 | 与 GCP 一体化 | 与 Azure 一体化 |
| 最新模型/特性首发 | 通常首发 | 滞后 | 滞后 | 滞后 |

> 经验：要最低延迟与最新特性（automatic caching、mid-conversation system messages 等），用官方 API；要最强数据驻留与企业治理整合，用对应云的托管；要 workspace 级 cache 隔离，避开 Bedrock/Vertex（它们仍是 org 级）。

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

- 用 `max_tokens=0` 在低峰期把 system/tools 写入缓存，消除首个真实请求的 TTFT 惩罚。
- 注意：`max_tokens=0` 不能与 `stream:true`、extended thinking、structured output、`tool_choice` 同时使用。

### 监控 usage 三段式

```
total_input = cache_read_input_tokens + cache_creation_input_tokens + input_tokens
```

- 命中率 = `cache_read / total_input`；目标通常 > 80%。
- 若 `cache_creation` 持续高而 `cache_read` 低，说明断点放在了变化块上，或请求间隔超过 TTL。

### 真实成本量级（以官方倍率估算）

- 缓存读 = base input 的 **0.1x**；5m 写 = **1.25x**；1h 写 = **2x**。
- 一个 10 万 token 的稳定前缀，若每 3 分钟复用一次：首写 1.25x，之后每次仅 0.1x——相对无缓存可节省约 **90%** 的前缀处理成本。
- 配合 **Batch API**（离线批处理折扣）可进一步叠加节省（倍率可叠加）。

## 3. Extended Thinking 与智能体后端

- **Thinking budget**：为复杂推理分配 token 预算；budget 过大会拖高延迟与成本，需按任务难度动态设置。
- **Thinking block 保留**：在 Opus 4.5+/Sonnet 4.6+ 默认保留 thinking block，且可被缓存复用——工具循环中把 thinking 块原样回传能显著降低重复推理成本。
- **Computer / Tool Use 沙箱**：智能体的工具执行必须放在受限沙箱（文件系统、网络、权限边界），与 [Tool Use 详解](/05-agent/tool-use/) 的安全实践一致。
- **多步循环 + 缓存**：Agent 每一步都重放 system/tools/历史，prompt caching 几乎是必需，否则成本不可控。

## 4. RSP/ASL 作为企业合规框架

Anthropic 的 RSP 不只约束 Anthropic 自己，也给了企业一个**可借鉴的安全发布框架**：

- **借鉴 if-then 承诺**：企业内部模型发布也可定义"达到 X 能力必须先满足 Y 防护"的门禁。
- **借鉴 Risk Report**：把模型能力、威胁模型、缓解措施、残余风险结构化记录，供合规与审计使用。
- **分类器即基础设施**：ASL-3 的输入/输出分类器思路，可落地为企业自建的 guardrails 服务（参见 [安全详解](/08-security/)）。
- **第三方审查**：对高风险用例引入外部专家评审，提升可信度。
- **政策映射**：RSP 已与 SB 53（加州）、RAISE Act（纽约）、EU AI Act Codes of Practice 对齐，企业可参照同类法规设计合规流程。

## 5. 容量与可靠性治理

Anthropic 公开承认：run-rate 收入从 ~$9B（2025 年底）飙升至 >$30B（2026），消费级增长在峰值时段冲击了 Free/Pro/Max/Team 的可靠性。这给企业两点启示：

- **容量前置规划**：训练/推理算力扩张有长交付周期（Colossus 19 天建成是特例，5GW 数据中心以年计），需求预测必须领先产能 6–12 个月。
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
| cache_read 一直为 0 | 断点放在每请求变化的块上；或低于最小可缓存长度 | 断点移到稳定前缀末尾；确认达到模型最小 token 阈值 |
| Bedrock 上无自动缓存 | Bedrock/Vertex 不支持 automatic caching | 改用显式断点，或切到支持的平台 |
| 跨 workspace 缓存不共享 | 2026-02 起 Claude API/Foundry 按 workspace 隔离 | 同一会话保持同一 workspace |
| 1h cache 反而更贵 | 使用频率高于 5 分钟却选了 1h | 高频用 5m（命中即免费刷新） |
| 工具调用 key 顺序变化导致缓存失效 | 部分语言 JSON key 顺序不确定 | 固化 key 顺序或用稳定序列化 |

## 小结

企业落地 Claude 的关键不是"能不能调通"，而是**把 prompt caching 用到极致、按用例选对云、用 RSP 思想搭安全门禁、用多源算力对冲容量风险**。下一章把这些经验提炼为可复用的最佳实践。
