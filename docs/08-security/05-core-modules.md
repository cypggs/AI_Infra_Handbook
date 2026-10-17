# 核心模块

AI 安全体系由若干相互协作的模块组成。理解每个模块的职责、输入输出与边界，是设计可落地架构的前提。

## 1. 身份提供者（Identity Provider, IdP）

- **职责**：管理人类与机器的注册、认证、会话、注销。
- **协议**：OIDC、OAuth2、SAML、LDAP、SCIM；**RFC 8693（OAuth 2.0 Token Exchange）**在 Agent 场景中的地位快速上升。
- **AI 场景**：人类用户登录、Service Account、Workload Identity、Agent Capability Token（含委托链 `act` 声明）。
- **代表产品**：Keycloak、Ory Kratos/Hydra、Authelia、Auth0（Auth for GenAI / Token Vault）、Clerk、Microsoft Entra、Okta。
- **2025-2026 趋势**：身份厂商开始提供 Agent 身份的全生命周期管理（创建、认证、按 scope 授权、注销）与 Token Vault（平台代管第三方 SaaS token）；初创领域出现并购潮（Astrix→Cisco、Entro→SailPoint、Oasis→Cyera），说明"非人类身份治理"已进入主流 IAM 版图。

## 2. 访问控制与策略引擎

- **RBAC**：基于角色的静态权限，适合组织架构。
- **ABAC**：基于属性动态决策，适合多租户与数据分类。
- **ReBAC**：基于关系（用户-文档-项目）决策，适合协作与共享场景。
- **Policy as Code**：把策略写成可版本化、可测试的代码。
- **代表产品**：
  - OPA（Open Policy Agent）：通用策略引擎，支持 Rego。
  - OpenFGA：Google 开源的 ReBAC 引擎。
  - Cedar：AWS 开源的授权语言与引擎。
  - Casbin：多语言支持的访问控制库。

## 3. 密钥与凭据管理（Secrets Manager）

- **职责**：安全存储、分发、轮换 API Key、数据库密码、证书、模型解密密钥。
- **关键能力**：
  - 加密静态与传输中。
  - 动态短期凭证（database credential、cloud IAM token）。
  - 自动轮换与版本管理。
  - 审计访问记录。
- **代表产品**：HashiCorp Vault、AWS Secrets Manager、Azure Key Vault、GCP Secret Manager、Doppler、Infisical、1Password Secrets Automation、Kubernetes external-secrets。

## 4. AI 安全网关（AI Security Gateway）

- **职责**：作为所有模型/Agent/RAG 请求的统一入口，执行安全策略。
- **功能**：
  - 认证与授权。
  - Rate limit、bot 防护、DDoS 缓解。
  - 请求/响应审计。
  - Provider key 与 tenant key 隔离。
  - 与 Guardrails 集成。
- **位置**：通常位于 LLM Gateway 之前或作为其插件。

## 4b. MCP / Agent 网关（2025 后新增）

随着 MCP 成为工具连接的事实标准，网关层多了一类专门组件：

- **工具注册管控**：哪些 Agent 允许使用哪些 MCP Server，按信任域分组。
- **Token Exchange**：网关把 Agent 的凭证兑换为后端系统的窄 scope 短期 token，Agent 永远不直接持有后端凭证。
- **描述快照与 diff**：首次审批时快照工具描述；Server 更新导致描述变化时冻结调用并重新审批（防 Rug Pull）。
- **版本锁定**：禁止使用浮动版本（`latest`）自动升级。
- **代表实现**：Solo.io AgentGateway、各类商业 MCP Gateway / AI Gateway 产品；MCP 规范 2026-07 修订版强制 OAuth 2.1 与 Resource Indicators。

## 5. 输入/输出 Guardrails

- **输入 Guardrails**：
  - 提示注入、越狱、系统提示提取检测。
  - PII 检测、恶意文件上传检测。
  - 工具描述投毒检测（MCP 场景）。
- **输出 Guardrails**：
  - 有害内容过滤（hate、violence、sexual、self-harm）。
  - PII/敏感信息 redaction。
  - 代码安全性扫描（避免生成有漏洞代码）。
- **2025-2026 产品演进**：
  - Meta 的 **LlamaFirewall**（2025-04 开源，PurpleLlama 项目）成为 Agent 防护的参考架构：**Prompt Guard 2**（86M/22M 参数的小模型，专抓注入与越狱，官方报告在 1% 误报率下越狱召回率从 v1 的 21.2% 提升到 97.5%）+ **AlignmentCheck**（用大模型审计 Agent 的逐步推理，抓目标漂移与间接注入）+ **CodeShield**（生成代码静态扫描）。在 AgentDojo 基准上，Prompt Guard 2 + AlignmentCheck 组合把攻击成功率从 17.63% 压到 1.75%。
  - **Llama Guard 4**（2025-04，随 Llama 4 发布）扩展到多模态（文本 + 图像）内容安全分类。
  - **市场整合剧烈**：Lakera→Check Point（2025-09）、Protect AI→Palo Alto（2025，并入 Prisma AIRS，其开源 LLM Guard 项目已于 2026 年归档停止维护）、Prompt Security→SentinelOne（2025-09）、Robust Intelligence→Cisco、CalypsoAI→F5（2025-09）。企业采购时应评估厂商存续能力，并优先选择策略可移植的方案。
  - 云厂商侧：Azure AI Content Safety（Prompt Shields）、Google Cloud Model Armor、AWS Bedrock Guardrails、Cloudflare Firewall for AI（把 WAF 能力扩展到 Prompt 检查，跑在边缘）各有取舍。
- **代表产品/模型**：OpenAI Moderation、Azure AI Content Safety、AWS Bedrock Guardrails、Llama Guard 4、LlamaFirewall / Prompt Guard 2、NeMo Guardrails、Guardrails AI、Microsoft Presidio、Cloudflare Firewall for AI。

## 6. 网络与运行时隔离

- **Service Mesh / mTLS**：Istio、Linkerd、Cilium 提供服务间加密与细粒度授权。
- **网络策略**：K8s NetworkPolicy、云安全组、egress 白名单。
- **沙箱**：gVisor、Firecracker、Kata Containers 限制容器行为。
- **运行时安全**：Falco、Tetragon 检测异常进程与网络行为。
- **GPU 隔离（AI 特有）**：
  - **MIG**（Ampere 起）提供硬件级显存与算力分区，是多租户共享单卡的最强隔离；MPS 与时间片共享**不提供**显存隔离，只能用于同信任域。
  - **机密计算**：H100/H200/Blackwell 的 CC 模式加密 VRAM，配合 CPU TEE（SEV-SNP/TDX）与远程证明（NVIDIA NRAS），让宿主机与云平台无法读取租户数据；大矩阵运算开销可低至约 3%。
  - **驱动栈加固**：NVIDIA Container Toolkit / GPU Operator 曾曝出容器逃逸漏洞（CVE-2025-23266，2025-01），AI 集群的节点级加固（及时升级、限制 socket 挂载）是 K8s 通用基线之外的必修课。

## 7. 数据治理与 DLP

- **数据分类**：识别公开、内部、机密、高度敏感数据。
- **数据血缘**：追踪数据从采集到模型输出的完整链路。
- **去标识化 / 匿名化**：k-匿名、差分隐私、tokenization。
- **DLP**：防止敏感数据通过 prompt、response、日志外泄。
- **机器遗忘（Unlearning）**：为删除权请求提供"尽力擦除 + 可验证"的流程。截至 2026-10，LLM 规模下的精确遗忘仍不可行，生产实践多用近似方法（梯度显著性擦除如 SalUn 系列、负向微调）+ 成员推断攻击（MIA）验证"是否还能问出来"。
- **代表产品**：Microsoft Presidio、AWS Macie、Google Cloud DLP、Apache Atlas、DataHub、OpenLineage。

## 8. 模型安全

- **模型签名与溯源**：Sigstore cosign、SLSA provenance、HuggingFace Safetensors。
- **模型扫描**：检查模型文件是否包含恶意代码、后门、异常权重。Hugging Face 上托管的模型中持续发现 pickle 反序列化武器化样本，**加载未知来源的 `.bin`/`.pt` 文件等同于执行远程代码**；CI 中必须接入 Picklescan / ModelScan，Safetensors 只解决格式安全、不解决权重后门。
- **权重投毒与后门**：针对微调（LoRA）与开源权重的投毒研究在 2025-2026 显著增多；目前尚无银弹，组合手段是：来源信誉 + 签名验证 + 行为评测（CyberSecEval / Garak 探测触发器）+ 异常权重检测。
- **模型水印与指纹**：追踪泄露模型来源。
- **对抗训练**：提高模型对对抗样本的鲁棒性。
- **代表工具**：ModelScan、Picklescan、HuggingFace Safetensors、PyRIT、Garak、CyberSecEval。

## 9. 依赖与供应链安全

- **依赖扫描**：Snyk、Dependabot、OSV、Trivy。
- **SBOM**：生成并审计软件物料清单。
- **镜像扫描**：Trivy、Grype、Snyk Container。
- **模型/数据集来源**：使用可信来源、验证 checksum、签名与 provenance。
- **MCP / Agent 工具链（2025 后新增）**：MCP Server 本质上是"可自动执行的依赖包"，要纳入同一套供应链管控：注册表准入评审（注意官方 MCP Registry 仅验证仓库所有权、不做代码审计）、版本锁定、描述快照、运行时 diff 告警。

## 10. 审计与 SIEM

- **审计日志**：记录身份、动作、资源、决策、原因、时间戳。
- **不可篡改存储**：WORM（Write Once Read Many）、区块链/哈希链、对象存储 Object Lock。
- **SIEM/SOAR**：Splunk、Elastic Security、Chronicle、Sentinel、Wazuh。
- **行为分析**：UEBA 检测异常访问模式。

## 11. 事件响应与红队

- **红队**：模拟真实攻击者测试系统韧性。
- **Purple team**：红队与蓝队协作，验证检测与响应能力。
- **自动化响应**：根据策略自动隔离、撤销凭证、通知 on-call。
- **基准驱动评测（2025 后主流）**：AgentDojo（Agent 注入）、AgentHarm（Agent 有害任务顺从度）、HarmBench / JailbreakBench（越狱）、Cybench（网络操作 Agent）等公开基准接入 CI，作为模型/Prompt/工具变更的安全回归门禁。
- **工具**：MITRE ATLAS（2025 年新增 14 项 Agent 专项技术）、OWASP LLM Top 10 2025、OWASP Agentic Top 10 2026、PyRIT、Garak。

## 模块协作示例

```text
用户请求
  → AI Security Gateway（认证）
  → IdP（验证 token，必要时 RFC 8693 Token Exchange 换发窄 scope 凭证）
  → Policy Engine（OPA/OpenFGA 授权 + 意图校验）
  → Input Guardrails（提示注入检测，小模型拦截 + 大模型审计）
  → Agent Runtime（执行，受 Service Mesh mTLS 保护）
  → MCP Gateway（工具描述 diff 校验、版本锁定）
  → Tool Sandbox（最小权限）
  → Output Guardrails（有害内容/PII/代码安全过滤）
  → Audit Logger（含每步工具调用 trace）→ SIEM
```

## 小结

核心模块不是简单堆砌，而是围绕“身份 → 策略 → 执行 → 审计”形成闭环。下一章通过开源项目的源码与生态分析，把这些模块落地为具体技术选型。
