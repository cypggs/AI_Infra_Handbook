# 核心模块

AI 安全体系由若干相互协作的模块组成。理解每个模块的职责、输入输出与边界，是设计可落地架构的前提。

## 1. 身份提供者（Identity Provider, IdP）

- **职责**：管理人类与机器的注册、认证、会话、注销。
- **协议**：OIDC、OAuth2、SAML、LDAP、SCIM。
- **AI 场景**：人类用户登录、Service Account、Workload Identity、Agent Capability Token。
- **代表产品**：Keycloak、Ory Kratos/Hydra、Authelia、Auth0、Clerk、Azure AD。

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

## 5. 输入/输出 Guardrails

- **输入 Guardrails**：
  - 提示注入、越狱、系统提示提取检测。
  - PII 检测、恶意文件上传检测。
- **输出 Guardrails**：
  - 有害内容过滤（hate、violence、sexual、self-harm）。
  - PII/敏感信息 redaction。
  - 代码安全性扫描（避免生成有漏洞代码）。
- **代表产品/模型**：OpenAI Moderation、Azure Content Safety、AWS Comprehend、Llama Guard、NeMo Guardrails、Guardrails AI、Lakera、Microsoft Presidio。

## 6. 网络与运行时隔离

- **Service Mesh / mTLS**：Istio、Linkerd、Cilium 提供服务间加密与细粒度授权。
- **网络策略**：K8s NetworkPolicy、云安全组、egress 白名单。
- **沙箱**：gVisor、Firecracker、Kata Containers 限制容器行为。
- **运行时安全**：Falco、Tetragon 检测异常进程与网络行为。

## 7. 数据治理与 DLP

- **数据分类**：识别公开、内部、机密、高度敏感数据。
- **数据血缘**：追踪数据从采集到模型输出的完整链路。
- **去标识化 / 匿名化**：k-匿名、差分隐私、tokenization。
- **DLP**：防止敏感数据通过 prompt、response、日志外泄。
- **代表产品**：Microsoft Presidio、AWS Macie、Google Cloud DLP、Apache Atlas、DataHub、OpenLineage。

## 8. 模型安全

- **模型签名与溯源**：Sigstore cosign、SLSA provenance、HuggingFace Safetensors。
- **模型扫描**：检查模型文件是否包含恶意代码、后门、异常权重。
- **模型水印与指纹**：追踪泄露模型来源。
- **对抗训练**：提高模型对对抗样本的鲁棒性。
- **代表工具**：ModelScan、Picklescan、HuggingFace Safetensors、PyRIT、Garak。

## 9. 依赖与供应链安全

- **依赖扫描**：Snyk、Dependabot、OSV、Trivy。
- **SBOM**：生成并审计软件物料清单。
- **镜像扫描**：Trivy、Grype、Snyk Container。
- **模型/数据集来源**：使用可信来源、验证 checksum、签名与 provenance。

## 10. 审计与 SIEM

- **审计日志**：记录身份、动作、资源、决策、原因、时间戳。
- **不可篡改存储**：WORM（Write Once Read Many）、区块链/哈希链、对象存储 Object Lock。
- **SIEM/SOAR**：Splunk、Elastic Security、Chronicle、Sentinel、Wazuh。
- **行为分析**：UEBA 检测异常访问模式。

## 11. 事件响应与红队

- **红队**：模拟真实攻击者测试系统韧性。
- **Purple team**：红队与蓝队协作，验证检测与响应能力。
- **自动化响应**：根据策略自动隔离、撤销凭证、通知 on-call。
- **工具**：MITRE ATLAS（AI 威胁矩阵）、OWASP LLM Top 10、PyRIT、Garak。

## 模块协作示例

```text
用户请求
  → AI Security Gateway（认证）
  → IdP（验证 token）
  → Policy Engine（OPA/OpenFGA 授权）
  → Input Guardrails（提示注入检测）
  → Agent Runtime（执行，受 Service Mesh mTLS 保护）
  → Tool Sandbox（最小权限）
  → Output Guardrails（有害内容/PII 过滤）
  → Audit Logger → SIEM
```

## 小结

核心模块不是简单堆砌，而是围绕“身份 → 策略 → 执行 → 审计”形成闭环。下一章通过开源项目的源码与生态分析，把这些模块落地为具体技术选型。
