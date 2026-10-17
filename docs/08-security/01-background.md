# 背景：为什么 AI 系统需要专门的安全体系

传统软件安全已经建立了一套成熟的方法：WAF、RASP、IAM、 secrets management、漏洞扫描、SOC。但当系统引入大模型、Agent、RAG、外部工具链后，攻击面从“代码与网络”扩展到了“自然语言、模型权重、训练数据、工具调用与非人类身份”。原有的控制点不再足够。

## 从传统应用到 AI 系统的攻击面演进

| 维度 | 传统应用 | AI 系统 |
|---|---|---|
| 输入空间 | 结构化数据、固定协议 | 开放自然语言，几乎无限 |
| 核心资产 | 代码、数据库、配置 | 模型权重、训练数据、Embedding、向量库、Prompt |
| 执行主体 | 人类用户 + 服务账号 | 人类、Agent、模型、MCP Server、插件 |
| 敏感信息 | PII、支付信息、密码 | 系统提示、API Key、模型记忆、RAG 片段 |
| 失败模式 | 越权、注入、数据泄露 | 提示注入、越狱、工具滥用、模型窃取、幻觉 |
| 供应链 | 代码库、依赖包 | 基础模型、LoRA、数据集、向量库、Prompt 仓库 |

## AI 系统特有的关键威胁

1. **提示注入（Prompt Injection）**
   攻击者通过构造输入覆盖系统提示或诱导模型执行非预期操作。分为直接注入（用户输入）和间接注入（外部文档、网页、邮件）。

2. **越狱与系统提示泄露（Jailbreak / System Prompt Extraction）**
   通过角色扮演、编码、翻译等技巧绕过安全对齐；或通过特定提问让模型输出隐藏的系统提示。

3. **工具与 Agent 滥用（Tool / Agent Abuse）**
   Agent 被诱导调用高权限工具、访问敏感数据、发送邮件、删除资源。OWASP LLM Top 10 2025 版中的 *Excessive Agency*、OWASP Agentic Top 10（ASI02）中的 *Tool Misuse* 都属于此类。

4. **数据与模型外泄（Data / Model Exfiltration）**
   通过大量查询提取训练数据、模型参数或向量库内容；模型文件、权重被窃取后可在异地部署。

5. **模型供应链攻击（Supply Chain）**
   基础模型、微调适配器、训练数据、Python/Node 依赖中任何一个环节被投毒，都会在下游放大。2025 年后的新增焦点是 **MCP 工具供应链**：恶意 MCP Server 可以通过工具描述（Tool Description）注入指令，或在通过审核后发布带毒更新（Rug Pull），把代码投毒扩展成了"协议投毒"。

6. **幻觉导致的安全与合规风险**
   模型生成错误代码、错误医疗/法律建议、泄露不存在的事实，可能引发法律责任与品牌危机。

7. **非人类身份爆炸（Non-Human Identity Explosion）**
   API Key、Service Account、Workload Identity、Agent-to-Agent 身份数量远超人类用户，传统 IAM 无法有效管理。2026 年的共识是：Agent 是比普通服务账号风险更高的非人类身份——它会自主决策、链式调用工具，因此需要**短期凭证 + 委托链可审计**（如 OAuth 2.0 Token Exchange 的 `act` 声明），而不是长期静态 API Key。

8. **RAG 与知识库投毒（Knowledge Base Poisoning）**
   攻击者向被自动抓取的网页、文档、工单中埋入恶意文本，模型检索后照单执行。PoisonedRAG（USENIX Security 2025）证明：向百万级语料中注入 **5 份恶意文档**，对特定问题的攻击成功率即可达到约 90%。它不需要访问模型、不需要越狱，被称为"LLM 时代的 SQL 注入"，是 2025-2026 年企业环境中最现实的攻击路径之一。

9. **记忆与上下文投毒（Memory / Context Poisoning）**
   长期运行的 Agent 会把外部内容写入持久记忆（用户画像、任务历史、向量库）。攻击者只需一次注入即可在后续所有会话中持续生效，且几乎不留下传统取证痕迹。OWASP ASI06 与 MITRE ATLAS 2025 年新增的 Agent 专项技术（上下文投毒、凭证收割等 14 项）都把它列为独立威胁类别。

## 为什么传统控制不够

- **WAF 不懂语义**：基于签名的 Web 防火墙无法识别自然语言中的注入或越狱。
- **RBAC 粒度太粗**：模型、工具、数据片段需要细粒度、动态的授权决策（ABAC/ReBAC）。
- **密钥管理跟不上**：LLM API Key 被复制到 countless notebooks、CI pipeline、本地环境，难以轮换与审计。
- **边界防御失效**：模型训练数据来自外部，推理服务需要访问多个 SaaS，传统“内网可信”假设不再成立。
- **静态扫描漏掉模型资产**：SAST/DAST 不检查模型权重、Embedding、向量库、Prompt 仓库。

## 2025-2026：威胁分类学的两次升级

AI 安全的威胁分类在两年内完成了两次重要升级，理解它们是设计防御体系的前提：

| 时间 | 发布 | 覆盖重点 |
|---|---|---|
| 2025-11 | [OWASP Top 10 for LLM Applications 2025](https://owasp.org/www-project-top-10-for-large-language-model-applications/) | 从"应用视角"重排 LLM 风险：Prompt Injection（LLM01）、敏感信息泄露（LLM02）、供应链（LLM03）、数据与模型投毒（LLM04）、Improper Output Handling（LLM05）、Excessive Agency（LLM06）、系统提示泄露（LLM07）、**向量与 Embedding 弱点（LLM08，首个 RAG 专项类别）**、错误信息（LLM09）、资源无限消耗（LLM10） |
| 2025-12 | [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/agentic-applications-top-10/) | 从"AI 说了什么"扩展到"AI 做了什么"：ASI01 目标劫持、ASI02 工具滥用、ASI03 身份与权限滥用、ASI04 Agent 供应链、ASI05 意外代码执行、ASI06 记忆投毒、ASI07 不安全 Agent 间通信、ASI08 级联失败、ASI09 人机信任滥用、ASI10 失控 Agent |

两个列表的关系：LLM Top 10 描述**单次模型调用的风险**，Agentic Top 10 描述**多步、多工具、多 Agent 编排系统的风险**。前者 LLM01 的 Prompt Injection 到后者演化成 ASI01 的 Agent Goal Hijack——注入的目标从"改一段话"变成" hijack 一个能调工具、花预算、发邮件的执行体"。

与此同时，攻击技术本身也在进化：

- **多轮与自动化越狱成为主流**：Crescendo（多轮渐进升级）、TAP（攻击树剪枝搜索）、many-shot（利用长上下文塞入数百轮假对话）等技术把攻击成功率推高，角色扮演类越狱在对抗评测中仍保持高成功率；2025-2026 的研究还出现了利用模型思维链透明性的"推理利用"家族。
- **间接注入成为头号现实风险**：企业 RAG 的自动抓取管道（Confluence、SharePoint、网页、邮件、工单）都是注入载体；当检索结果喂给带工具的 Agent 时，文档注入可能升级为真实的越权操作。
- **Agentic 评测基准成形**：AgentDojo（NeurIPS 2024，工具调用 Agent 注入基准，97 个任务 + 629 个安全用例）与 AgentHarm（ICLR 2025，110-440 个恶意 Agent 任务）成为事实标准——结果显示模型在 Agent 场景下"顺从度"高得惊人，且自适应攻击可以绕过当时所有被测防御。

## 合规与业务驱动

- **法规（截至 2026-10）**：
  - 欧盟 AI Act（Regulation 2024/1689）：2025-08-02 GPAI 义务生效（技术文档、版权政策、训练数据摘要；已有模型宽限至 2027-08-02）；2026-08-02 全面适用，第 50 条透明度义务（AI 交互告知、深度伪造披露、合成内容标记）开始执行，罚款最高 3500 万欧元或全球营业额 7%。2026-07 通过的 Digital Omnibus（Reg. 2026/1744）把 Annex III 高风险系统的合规截止日推迟到 2027-12-02，但 GPAI 与透明度义务不受影响——合规压力没有消失，只是转移。
  - 中国：《人工智能生成合成内容标识办法》与强制国标 GB 45438-2025 于 **2025-09-01 施行**，要求对 AI 生成合成的文本、图片、音频、视频同时附加显式与隐式标识；与算法备案、安全评估一起构成国内 AI 服务的合规基线。
  - GDPR、美国 CCPA/CPRA、《生成式人工智能服务管理暂行办法》继续作为底层数据与内容合规要求。
- **标准**：NIST AI RMF（及其生成式 AI 配套文件 NIST AI 600-1，2024-07 发布）、ISO/IEC 27001 与 **ISO/IEC 42001（AI 管理体系，2023-12 发布）**、SOC 2 Type II、HIPAA 正在成为企业采购 AI 服务的门槛。
- **商业**：数据泄露、模型被窃、有害内容生成可能直接造成罚款、诉讼、客户流失。2024-2026 年安全厂商对 AI 安全初创的并购潮（Check Point 收购 Lakera、Palo Alto 收购 Protect AI、SentinelOne 收购 Prompt Security 等）也说明企业级需求已经从"可选"变成"必答"。

## 小结

AI 系统把“代码执行”变成了“模型推理 + 工具调用 + 知识检索”，而 Agent 的普及又把它进一步变成了“自主规划 + 多跳委托 + 持久记忆”。这要求安全体系从边界防御转向**以身份、数据和模型为中心的内生安全**，并且把“不可信上下文”（检索片段、工具描述、Agent 记忆）当作一等公民来防。下一章将从核心思想出发，建立统一的安全原则集。
