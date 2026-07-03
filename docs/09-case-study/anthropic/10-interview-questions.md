# 面试题

本章按初 / 中 / 高级组织 Anthropic 案例相关面试题，附要点提示。适合 AI Infra / LLMOps / AI 安全方向候选人自测。

## 初级（概念与定位）

### Q1. Anthropic 与 OpenAI 在对齐路线上最核心的区别是什么？

> 要点：RLHF（人类偏好标注）vs Constitutional AI / RLAIF（AI 对照宪法的偏好）。人类角色从"标偏好"上移到"写宪法"。两阶段：Constitutional SL（critique-revise）+ RLAIF（偏好模型 + RL）。

### Q2. 什么是 HHH？

> 要点：Helpful、Honest、Harmless——Anthropic 把对齐目标形式化的三角；三者边缘会冲突，对齐即在三角间找稳健权衡。

### Q3. Claude 的模型分档（Haiku/Sonnet/Opus）对基础设施意味着什么？

> 要点：不同档位对应不同延迟/成本/能力区间，决定部署形态——Haiku 偏吞吐与成本，Opus 偏显存与算力；推理路由需按请求复杂度分流。

### Q4. Anthropic 为什么是"三云同款模型"？这对企业有什么好处？

> 要点：Claude 在 Bedrock/Vertex/Foundry + 官方 API 均可用；好处是可用性、数据驻留、议价权、企业治理整合。

### Q5. prompt caching 的基本收益是什么？

> 要点：重复前缀（system/tools/长文档）的 KV 复用，读成本仅 base input 的 10%，显著降低延迟与成本；命中不计限流额度。

## 中级（机制与工程）

### Q6. 详细解释 prompt caching 的命中模型：写入、读取、回看窗口。

> 要点：写入只在断点（写一个到此为止的 prefix hash）；读取在断点处算 hash，不命中则向前逐 block 回看之前写过的条目；回看窗口 20 个 block；最多 4 个断点；5m/1h 双 TTL。

### Q7. "把 cache_control 放在含时间戳的块上"为什么零命中？怎么修？

> 要点：写入只发生在断点，hash 含时间戳 → 每请求 hash 不同；回看寻找的是"之前写过的条目"，而稳定块上从未写过 → 不命中。修复：断点移到最后一个跨请求相同的稳定块。

### Q8. usage 三段式怎么算总输入 token？为什么对成本和限流都重要？

> 要点：`total = cache_read_input_tokens + cache_creation_input_tokens + input_tokens`；`input_tokens` 只含断点之后的 token。它决定了真实计费与限流额度（命中豁免限流）。

### Q9. 5 分钟 vs 1 小时 TTL 怎么选？

> 要点：命中即免费刷新——使用频率高于 5 分钟用 5m；间隔在 5min~1h 之间、或想改善限流额度利用率用 1h（写成本 2x）。混用时长 TTL 必须在短 TTL 之前。

### Q10. Constitutional SL 阶段的 critique-revise 如何产出监督数据？

> 要点：初始回答 → 按原则 critique → revise → 用修订对做 SFT；可大规模、可复现、可随宪法版本演进。

### Q11. RLAIF 与 RLHF 在工程管线上的关键差异？

> 要点：偏好标签来源——RLAIF 用"模型对照宪法的判断"训练偏好模型；RLHF 用人类 pairwise 标注。RLAIF 把瓶颈从标注量转移到宪法质量与偏好模型训练。

### Q12. workspace 级与 org 级 cache 隔离的区别与平台差异？

> 要点：2026-02 起 Claude API/Foundry 按 workspace 隔离；Bedrock/Vertex 仍 org 级。多 workspace 部署需据此调整缓存策略。

## 高级（架构与权衡）

### Q13. 设计一个 Claude 生产网关，如何把 prompt caching、extended thinking、tool use、guardrails 组合起来？

> 要点：模板化 prompt + 断点注入；usage 三段式采集；thinking budget 按任务难度动态配；tool/computer use 沙箱执行；ASL 风格 guardrails 作为独立服务；多模型路由（Haiku/Sonnet/Opus）；多云 failover。

### Q14. 异构算力（Trainium + GPU）对训练框架与运维提出哪些挑战？

> 要点：两套软件栈（Neuron vs CUDA/Triton）；分布式并行在两套硬件上的可移植性与性能对齐；故障域与 checkpoint 策略统一；监控指标可比性。

### Q15. 如何用可解释性产出指导安全决策？给出一个工程化方案。

> 要点：SAE/dictionary learning 训练特征字典 → 标注高风险特征（欺骗、CBRN 相关）→ 作为运行时监控信号接入 → 触发阈值告警/熔断；与黑盒评估双轨，定期更新字典。

### Q16. RSP 的"区域模糊（zone of ambiguity）"是什么？企业如何借鉴？

> 要点：模型能力接近但未明确越过阈值，评估科学不够 dispositive；Anthropic 取预防性态度。企业借鉴：定义保守的"疑似达阈"处理流程，结合人工复核与渐进放量。

### Q17. 假设你的 Claude 应用 cache_read 长期为 0，但 prompt 看似稳定，如何系统排查？

> 要点：(1) 确认达到模型最小可缓存 token；(2) 确认平台是否支持所用缓存模式；(3) 检查断点是否落在稳定块（而非时间戳/用户输入）；(4) 检查 tool_choice/图像/thinking 参数是否变化导致失效；(5) 检查 JSON key 顺序是否稳定；(6) 用 cache diagnostics 对比连续请求找出发散点。

### Q18. 比较 OpenAI 与 Anthropic 两条工程路线，给出"什么场景该学谁"的判断框架。

> 要点：规模/产品化/API 生态/多模态消费产品 → 学 OpenAI；对齐管线/可解释性/安全治理/成本极致优化/芯片多元化 → 学 Anthropic。两者互补，非替代。

## 开放设计题

### Q19. 为一个客服 Agent 设计完整的缓存与对齐策略。

> 要点：system（品牌话术/RAG 检索结果）显式断点 + 1h TTL（客服间隔长）；对话历史用自动缓存或补充断点；thinking budget 小或关闭；tool use 沙箱；输出 guardrails（合规/PII）；宪法原则内化为 system 指令与 guardrails。

### Q20. 如果要在企业内部复刻一个"迷你 RSP"，你会定义哪些 ASL 与门禁？

> 要点：按业务风险（数据泄露/误导/合规违规）定义 2–3 级；每级对应防护（guardrails 强度、人工复核、审计粒度、权重访问控制）；能力评估流水线 + 发布门禁 + Risk Report；定期外部审查。

## 小结

这些题目覆盖了从概念（HHH、CAI）、机制（prompt caching 命中模型）、架构（异构算力、网关设计）到治理（RSP/ASL）的完整光谱。能在白板上讲清 Q6、Q10、Q13、Q16，基本具备 Anthropic 案例的工程理解力。
