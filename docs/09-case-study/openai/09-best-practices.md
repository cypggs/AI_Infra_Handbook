# 最佳实践

以下清单提炼了 OpenAI 案例中对 AI Infra 工程师最直接可用的经验。

## 训练基础设施

- [ ] 把硬件故障视为常态，设计高频 checkpoint 与自动恢复。
- [ ] 根据网络拓扑选择并行策略，避免跨机架/跨 pod 成为瓶颈。
- [ ] 使用混合精度（BF16/FP16）与梯度缩放稳定训练。
- [ ] 对 MoE 模型做专家并行与 all-to-all 通信优化。
- [ ] 记录数据版本、清洗规则与模型性能，确保实验可复现。
- [ ] 训练环境严格隔离，限制外部 egress，保护数据与模型权重。

## 推理优化

- [ ] 优先减少输出 token（比减少输入 token 对延迟影响更大）。
- [ ] 使用 continuous batching / in-flight batching 提高 GPU 利用率。
- [ ] 引入 PagedAttention 或类似技术管理 KV cache。
- [ ] 对重复前缀使用 prefix caching。
- [ ] 在“输出结构已知”的场景使用 predicted outputs 或 speculative decoding。
- [ ] 简单任务路由到小模型/蒸馏模型，复杂任务再用大模型。
- [ ] 默认开启 streaming，改善用户感知延迟。

## API 与平台工程

- [ ] 设计 OpenAI-compatible API，降低开发者迁移成本。
- [ ] 实现多租户隔离（organization / project / key）。
- [ ] 按 tier、模型、并发、token budget 设置分层限流。
- [ ] 模型版本显式命名，支持灰度发布与快速回滚。
- [ ] 记录每次请求用于计费、可观测与审计。
- [ ] 多区域部署，按地理位置与容量路由。

## 安全与对齐

- [ ] 把 RLHF / 对齐训练作为持续过程，而非一次性步骤。
- [ ] 建立多维度安全评估：cybersecurity、CBRN、persuasion、autonomy。
- [ ] 定期进行内部 + 外部红队测试，覆盖多语言、多模态。
- [ ] 对 high/critical 风险模型设置更严格的发布门槛。
- [ ] 发布 System Card / Model Card，记录能力、限制与缓解措施。
- [ ] 建立滥用检测与响应机制，包括 rate limit、内容过滤、人工审核。

## 可观测与 SLO

- [ ] 定义核心 SLI：TTFT、ITL、可用性、每 token 成本、错误率。
- [ ] 配置 burn-rate 告警，大流量下短窗口异常会迅速消耗预算。
- [ ] 按用户/项目/模型聚合用量与成本。
- [ ] 保留完整 trace，便于定位延迟瓶颈与错误根因。

## 组织与流程

- [ ] 研究与工程团队紧密协作，基础设施需求来自研究前沿。
- [ ] 采用迭代部署，先 API/小范围用户，再逐步放量。
- [ ] 建立故障演练与回滚 playbook。
- [ ] 与云厂商深度 co-design，针对工作负载优化网络、存储、调度。

## 小结

OpenAI 的最佳实践不是“必须用 OpenAI 的工具”，而是**把规模化、产品化、安全化、成本化作为基础设施设计的共同目标**。下一章通过面试题检验理解。
