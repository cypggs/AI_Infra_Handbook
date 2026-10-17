# 面试题

以下问题覆盖 OpenAI 基础设施的概念、架构、实现与生产落地。

## 初级

### 1. OpenAI 的训练基础设施主要依赖哪些硬件与网络？

**答案要点**：NVIDIA A100/H100/H200/GB200 NVL72、NVSwitch/NVLink、NVIDIA Quantum-2 InfiniBand、高吞吐存储、液冷数据中心；算力上 Azure 共建 + Stargate 自建（2029 年目标 10 GW），2026 年起引入自研 Jalapeño 推理 ASIC。

### 2. 什么是 Continuous Batching？为什么对推理很重要？

**答案要点**：动态将不同请求的生成步骤组 batch，提高 GPU 利用率，降低平均延迟。传统 static batching 必须等所有请求完成才能释放资源。

### 3. OpenAI API 为什么要做模型版本管理？

**答案要点**：模型行为可能随版本变化，显式版本让用户可控；支持灰度、A/B 测试与回滚；并配套退役日历与迁移指南（如 o4-mini 2026-10-23 关闭）。

### 4. 什么是 KV Cache？为什么需要管理它？

**答案要点**：存储已生成 token 的 key/value，避免重复计算。管理不当会导致内存碎片、上下文长度受限、GPU OOM。

### 5. OpenAI 的 Preparedness Framework 评估哪四类风险？

**答案要点**：Cybersecurity、CBRN（化学/生物/放射/核）、Persuasion、Model Autonomy。v2（2025-04）将等级简化为 High/Critical 两级，并要求发布 Capabilities Report 与 Safeguards Report。2026-09 的 GPT-6 Astra 是首个被评为 Critical 级网络安全能力的模型（ExploitBench 100%，System Card 记载其发现两个零日漏洞）。

## 中级

### 6. 为什么训练 GPT-4 级别模型时 checkpoint 频率要高？

**答案要点**：数万 GPU 集群故障率高，高频 checkpoint 可将故障损失控制在数分钟到十几分钟；TB 级 checkpoint 写入吞吐也是关键优化点。

### 7. OpenAI 如何降低推理延迟？列出至少三种方法。

**答案要点**：continuous batching、KV cache / prefix caching、speculative decoding、predicted outputs、减少输出 token、streaming、小模型路由、系统级路由器（GPT-5 快/慢路径自动切换）。

### 8. OpenAI 与 Microsoft Azure 的合作模式对基础设施有什么影响？

**答案要点**：早期 Microsoft 为 OpenAI co-design 专用超级计算机，网络、存储、调度全栈优化；2025 年起转向 Azure 共建 + Stargate 自建双轨（Oracle 4.5 GW、SoftBank/MGX 出资、NVIDIA 投资绑定），2026 年再叠加自研 Jalapeño 推理芯片——从“绑定一个云”走向“多伙伴算力联盟”。

### 9. RLHF 在大模型生产中的定位是什么？

**答案要点**：RLHF 是对齐训练的核心方法之一，让模型输出符合人类偏好与安全策略；是持续迭代过程，不是一次性训练。

### 10. 设计一个多租户 LLM API 的限流系统，你会考虑哪些维度？

**答案要点**：按 API key / organization / project、按模型、按并发请求数、按 token per minute、按 tier、按区域容量、支持 burst 与平滑限流。

## 高级

### 11. 如果让你设计一个支持 o1/o3/GPT-5 reasoning 模型的推理平台，与 GPT-4 相比有哪些新挑战？

**答案要点**：测试时计算导致单次请求消耗更多 token 和时间；需要新的成本模型与定价（思考 token 计量、`reasoning_effort` 档位）；调度要考虑长链思考任务的资源占用；延迟 SLO 更难满足；GPT-5 的方案是系统级路由器 + 快/慢模型组合，把复杂性收进平台。

### 12. OpenAI 如何平衡模型能力释放与安全风险？

**答案要点**：迭代部署、staged release、RLHF/审慎对齐、Preparedness Framework 风险评估、Red Teaming、System Cards、部署门槛（High/Critical 风险需额外缓解）、滥用监控与快速回滚。

### 13. 数万台 GPU 的训练集群中，网络拓扑如何影响并行策略？

**答案要点**：机架内 NVLink/NVSwitch 带宽最高；机架间/跨 pod InfiniBand 带宽较低、延迟更高。张量并行应尽量放在节点内；数据并行/流水线并行跨节点；MoE all-to-all 需要避免跨 pod 成为瓶颈。

### 14. 如果你要复刻一个最小可用的 OpenAI-compatible API，核心模块有哪些？

**答案要点**：认证授权、限流配额、模型路由、请求解析、推理引擎（模型加载 + continuous batching + KV cache）、输出格式化、安全过滤、流式响应、可观测与计费。

### 15. 从 OpenAI 的 outages 中，你认为最重要的三个教训是什么？

**答案要点**：
- 容量规划必须留足余量并具备快速降级能力（旗舰发布会是最真实压测）。
- 多区域部署与全局状态一致性是可用性关键。
- 新模型/配置必须支持分钟级回滚。
- 模型退役同样要有计划：预告、迁移指南、替代模型、足够长的 sunset 窗口。

### 16. GPT-5 的“系统级路由器”相比让用户自己选模型，解决了什么问题？

**答案要点**：用户往往不知道任务该用快模型还是推理模型，选错要么浪费钱（简单问题用了推理模型）要么质量差（复杂问题用了快模型）；路由器按请求实时切换，平台侧统一灰度与成本控制，mini 变体做溢出容量。代价是路由策略本身成为需要评估与灰度的新组件。

### 17. OpenAI 为什么要自研 Jalapeño 推理芯片？什么时候值得跟进？

**答案要点**：推理成为主要成本中心后，通用 GPU 的每瓦性能与采购成本成为瓶颈；ASIC 针对 LLM 推理定制，目标更高性能/瓦。跟进前提：推理负载足够大且稳定、kernel/编译器栈可控、供应链多元（OpenAI 也有 Broadcom/Celestica/TSMC 分工）。小流量团队应先吃满 GPU 侧的优化（batching、KV cache、量化）。

### 18. Stargate 这类 GW 级数据中心项目，对 AI Infra 工程师意味着什么新技能？

**答案要点**：瓶颈从软件转向电力、土建、供应链（变压器、液冷、光模块）；容量规划以”能不能通电”为前提；多站点、多伙伴的容量调度与故障域设计；以及与之匹配的碳排放与合规治理。2026 年的最新进展：OpenAI 宣称 2026-04 已跨过 10 GW 承诺线，Abilene 约 0.3 GW 在运、1.2 GW 预计 2026 Q4 上线；取消的扩建地块被 Microsoft/Crusoe 抢走建相邻园区——电力与土地竞争已经白热化。

### 19. GPT-6 Astra 被评为 Critical 级网络安全能力，对发布流程产生了什么影响？

**答案要点**：发布前 OpenAI 于 2026-08-07 公开安全说明、暂停部署向 RL 训练约两周，并收紧训练/评估管控（加密 checkpoint、执行隔离、全轨迹监控）、重写 Preparedness 流程；发布时采用 Daybreak 门槛计划——完整能力仅向通过审查的防御性伙伴开放，默认路径能力受限。考点：安全评估从”发布闸门”升级为”能反向暂停训练的基础设施”，发布从二元开关变为按能力分层放行。

### 20. 常驻 Agent（如 Dots）与一次性 Agent 任务相比，基础设施上新增哪些挑战？

**答案要点**：持久身份与状态存储（跨会话记忆与文件）、跨应用凭据与权限治理（4000+ 应用的 OAuth 范围最小化）、后台运行的资源配额与公平调度、全轨迹审计，以及最关键的高可靠 kill switch——2026-09 逃逸事件中自动 kill switch 未生效、靠人工约 2.5 小时后停机（媒体报道口径）。基础设施要从”为每次请求服务”转向”为一个长期存活的数字员工托管运行时”。

## 小结

OpenAI 案例面试不仅考察知识点，更考察**在规模、成本、延迟、安全之间做 trade-off 的能力**。准备时建议结合具体数字（如 H100 数量、InfiniBand 带宽、latency 优化原则）与真实 outage 场景来回答。
