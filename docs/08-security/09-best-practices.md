# 最佳实践

以下检查清单汇总了 AI 安全设计与运营中的关键动作。可对照项目现状逐项评估。

## 身份与访问

- [ ] 所有人类用户强制启用 MFA，单点登录走 OIDC/SAML。
- [ ] 服务账号与Workload 使用 SPIFFE/SPIRE 或云 Workload Identity，避免长期 API Key。
- [ ] LLM/Agent/MCP 工具按 capability 授权，禁止“万能账号”。
- [ ] 多租户场景下，按 tenant 隔离身份、密钥、数据与网络。
- [ ] 授权策略使用 Policy as Code（OPA/OpenFGA/Cedar），可版本化、可测试。
- [ ] 定期审查权限，移除过期账号与过度授权。
- [ ] Agent 使用 OAuth 2.0 Token Exchange（RFC 8693）换取短期窄 scope 凭证，委托链（`act`）可审计；第三方 SaaS token 由 Token Vault 代管。
- [ ] 定期盘点非人类身份（服务账号、Agent、MCP 连接），清理僵尸凭证。

## 密钥与凭据

- [ ] 禁止在代码、日志、Notebook、CI 输出中硬编码 API Key。
- [ ] 使用 Vault 或云 Secret Manager 集中管理，启用自动轮换。
- [ ] 优先使用短期动态凭证（database、cloud IAM、signed URL）。
- [ ] 密钥按环境（dev/staging/prod）与租户隔离。
- [ ] 开启密钥访问审计，异常读取实时告警。
- [ ] 模型权重、Embedding、向量库存储加密静态数据，传输使用 TLS/mTLS。

## 输入/输出安全

- [ ] 在服务端部署多层 Guardrails：网关层 + 模型前 + 模型后。
- [ ] 提示注入检测覆盖直接注入、间接注入、多轮绕过。
- [ ] 输出过滤覆盖毒性、偏见、PII、恶意代码、危险指令。
- [ ] 高风险输出引入 Human-in-the-Loop 审批。
- [ ] 记录被拒绝的请求与原因，用于持续改进。
- [ ] 注入/越狱检测采用"小模型拦截 + 大模型审计"双层（如 Prompt Guard 2 + AlignmentCheck），并用 AgentDojo 等基准回归。

## Agent 与 MCP 工具链

- [ ] 威胁建模覆盖 OWASP Agentic Top 10（含系统时），而不只是 LLM Top 10。
- [ ] 外部 MCP Server 经过代码审计与行为测试后才准入；不默认信任官方 Registry 的收录。
- [ ] MCP Server 版本精确锁定，禁止浮动版本自动升级。
- [ ] 首次审批时快照工具描述，运行时 diff 不一致即冻结（防 Rug Pull）。
- [ ] 不同信任域的 MCP Server 不共享同一 Agent 会话上下文。
- [ ] 写操作类工具按风险分级审批（发邮件异步审批、删数据强制人工）。
- [ ] Agent 记忆/知识库写入过 Guardrail，长期记忆视为不可信输入。

## 网络与运行时

- [ ] 服务间通信默认启用 mTLS。
- [ ] 使用 NetworkPolicy / Service Mesh 实施微分段。
- [ ] 限制 egress，只允许访问必要的外部模型 API 与数据源。
- [ ] Agent 工具调用在 sandbox / 受限网络中执行。
- [ ] 容器以非 root 运行，只读文件系统，最小镜像。
- [ ] 启用运行时威胁检测（Falco/Tetragon）。
- [ ] NVIDIA Container Toolkit / GPU Operator 及时升级（历史上出现过容器逃逸 CVE）。
- [ ] 多租户 GPU：不同信任域节点级隔离；单卡共享用 MIG；高敏感负载用 CC 模式 + 远程证明；租户切换清空 VRAM。

## 数据与模型

- [ ] 训练数据上线前清洗，去除 PII、毒性、后门样本。
- [ ] 建立数据血缘与模型版本追溯。
- [ ] 模型文件使用 Safetensors 替代 pickle-based 格式。
- [ ] **入库 CI 强制 Picklescan / ModelScan 扫描**，未知来源 `.bin`/`.pt` 一律拒绝。
- [ ] 对模型镜像、权重文件签名并验证 provenance（Sigstore/cosign/SLSA）。
- [ ] 向量库按租户/项目隔离，敏感字段加密。
- [ ] 知识库写入管道做来源校验与语义异常检测（防 PoisonedRAG 类投毒）。
- [ ] 制定数据保留与删除策略，满足 GDPR/CCPA 等要求。
- [ ] 对"删除权"请求提供机器遗忘流程（近似擦除 + 成员推断验证 + 留存证据）。

## 供应链

- [ ] 生成并维护 SBOM。
- [ ] 依赖漏洞扫描集成到 CI/CD（Snyk、Dependabot、OSV、Trivy）。
- [ ] 镜像扫描与签名，禁止运行未签名镜像。
- [ ] 基础模型与数据集来自可信来源，验证 checksum 与签名。
- [ ] Prompt 模板、系统提示纳入版本控制与安全 review。
- [ ] 引入 AI 安全开源组件时评估其维护状态（如 LLM Guard 已归档，勿再新增依赖）。

## 审计与事件响应

- [ ] 所有认证、授权、Guardrail 决策、模型调用记录 append-only 审计日志。
- [ ] Agent 系统记录每步工具调用 trace（含工具描述版本与委托链）。
- [ ] 审计日志集中到 SIEM，设置异常检测规则。
- [ ] 制定事件响应 playbook（含 MCP 投毒 / Rug Pull 场景），定期演练。
- [ ] 建立红队机制，至少每季度一次对抗测试；基准回归（AgentDojo/AgentHarm 等）接入发布流水线。
- [ ] 事后复盘输出可执行的改进项，并跟踪闭环。

## 合规与治理

- [ ] 上线前完成 AI 影响评估（AIA）与数据保护影响评估（DPIA）。
- [ ] 高风险系统满足人类监督、可解释性、公平性要求。
- [ ] 维护模型卡片与数据使用说明。
- [ ] 与法务/合规团队定期审查数据跨境、subprocessor、DPA 条款。
- [ ] 面向欧盟用户的生成式服务落实 AI Act 第 50 条透明度义务（AI 交互告知、深度伪造披露、合成内容标记）。
- [ ] 面向中国公众的服务落实《人工智能生成合成内容标识办法》：显式 + 隐式标识，标识逻辑落在生成链路。

## 性能与安全的平衡

- **不要为安全牺牲可用性到无法使用**：多层过滤可以异步化，关键路径只保留轻量检查。
- **不要为速度牺牲底线**：认证、授权、审计不能降级或绕过。
- **持续度量**：Guardrail 误杀率、漏检率、延迟影响、成本影响应纳入 SLO。

## 小结

最佳实践不是一次性清单，而是需要随着模型版本、业务场景和威胁情报持续更新的活的文档。下一章通过面试题帮助你检验对这些知识的掌握程度。
