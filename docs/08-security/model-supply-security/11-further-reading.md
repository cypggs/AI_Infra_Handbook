# 延伸阅读

## 官方文档与一手资料

**平台与格式安全**

- [Hugging Face Security 总览](https://huggingface.co/docs/hub/security)：访问控制、2FA、SSO、恶意软件与 pickle 扫描入口。
- [HF Pickle Scanning](https://huggingface.co/docs/hub/security-pickle)：opcode 扫描原理、best-effort 免责声明、safetensors 推荐——本章 5.1/5.2 节的直接出处。
- [HF Malware Scanning](https://huggingface.co/docs/hub/security-malware)：ClamAV 扫描机制（每次 commit、2GB 以下文件）。
- [safetensors](https://github.com/huggingface/safetensors)：格式规范与安全设计说明。
- [PyTorch 2.6 发布说明](https://pytorch.org/blog/pytorch2-6/)：`torch.load` 默认 `weights_only=True` 的动机与语义。

**扫描器**

- [picklescan](https://github.com/mmaitre314/picklescan)：HF 平台在用的 pickle 扫描器。
- [Fickling](https://github.com/trailofbits/fickling)：pickle 符号执行与反编译，检测 OVERTLY_MALICIOUS 载荷。
- [ModelScan](https://github.com/protectai/modelscan)：多格式模型扫描（pickle/SavedModel/H5/Keras V3），CI 退出码设计。

**签名与 provenance**

- [Sigstore 文档](https://docs.sigstore.dev/)：cosign / Fulcio / Rekor / OIDC 签名验证流程。
- [google/model-transparency](https://github.com/google/model-transparency)：模型目录签名的 Sigstore 实践（model_signing）。

**MCP 与工具链**

- [MCP Security Best Practices](https://modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices)：confused deputy、token passthrough 禁令、SSRF 防护、本地 Server 同意机制。
- [Invariant Labs: Tool Poisoning Attacks](https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks)：tool poisoning / rug pull / shadowing 的原始披露。
- [ToolHive](https://github.com/stacklok/toolhive)：容器化 MCP Server 运行与 Registry 管控的开源实现。

**沙箱**

- [Firecracker](https://firecracker-microvm.github.io/)：microVM 设计与快照能力。
- [gVisor](https://gvisor.dev/)：用户态内核隔离模型。
- [E2B](https://github.com/e2b-dev/infra)：开源 Firecracker 代码执行沙箱平台。

**法规与框架**

- [EU AI Act 监管框架页](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai)：分阶段适用时间表（GPAI 义务 2025-08、全面强制 2026-08）。
- [中国《人工智能生成合成内容标识办法》](https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm)：显式/隐式标识义务、日志留存 ≥6 个月。
- [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework)：Manage 职能的供应链条款。
- [ISO/IEC 42001](https://www.iso.org/standard/44545.html)：AI 管理体系标准的供应商管理要求。
- [MITRE ATLAS](https://atlas.mitre.org/)：AI 系统攻击技术知识库。
- [OWASP LLM Top 10](https://genai.owasp.org/llm-top-10/)：LLM03 Supply Chain 与 LLM04 Data and Model Poisoning 的分类基准。

## 研究报告（厂商一手，注意立场）

- [JFrog × Hugging Face：恶意 ML 模型联合披露](https://jfrog.com/community/ai/jfrog-and-hugging-face-join-forces-to-expose-malicious-ml-models/)：100+ 恶意模型发现与平台扫描误报分析。
- [ReversingLabs：nullifAI 坏 pickle 逃逸](https://www.reversinglabs.com/blog/rl-identifies-malware-ml-model-hosted-on-hugging-face)：解析器差异攻击面。

## 学术论文

- Shokri et al. 2017, *Membership Inference Attacks Against Machine Learning Models*：成员推断奠基工作。
- Tramèr et al. 2016, *Stealing Machine Learning Models via Prediction APIs*：模型抽取经典。
- Shan et al. 2023, *Poisoning RLHF-based LLMs with Adversarial Utterances*：投毒 RLHF 数据植入后门。
- Hubinger et al. 2024, *Sleeper Agents: Training Deceptive LLMs that Persist Through Safety Training*：后门挺过安全微调的实验证据。
- Carlini et al. 2024, *Stealing Part of a Production Language Model*：对生产 LLM 的嵌入/投影层抽取。
- Kirchenbauer et al. 2023, *A Watermark for Large Language Models*：green-list 水印构造；及其 2024 年关于水印可靠性与 paraphrase 攻击的后续分析。

## 相关章节

- [安全篇](/08-security/)：身份、密钥、零信任、Guardrails 与合规总体系，本主题是其"供应链 + 模型资产"专线的展开。
- [Personal AI Agent](/05-agent/personal-agent/)：个人 Agent 场景的 MCP 工具安装与本地执行风险。
- [MCP](/05-agent/mcp/)：协议机制、授权流程与生态，本主题的 G4 门禁建立在它之上。
- [Agent Runtime](/05-agent/agent-runtime/)：Agent 循环运行时，沙箱与 egress 的执行层。
- [向量数据库](/06-rag/vector-db/)：RAG 数据底座的投毒与完整性问题（OWASP LLM08）。
- [MLflow](/03-ai-platform/mlflow/)：Model Registry 门禁（G2/G3）的挂载点实践。
- [模型量化](/04-llmops/model-quantization/)：GGUF 等分发格式的供应链视角，水印 strength 与量化步长的耦合。
- [Benchmark + Evaluation](/07-ai-sre/benchmark-evaluation/)：canary 触发率与红队评测的方法论、防污染纪律。
