# 架构设计

Anthropic 的基础设施可以用"两条命脉 + 一个治理层"来概括：**训练/算力命脉**负责生产模型，**推理/产品命脉**负责把模型变成在线服务，**安全治理层（RSP/ASL）**贯穿两者，决定什么能训、什么能发。三者共享模型仓库与可解释性工具链。

## 总体架构

```mermaid
flowchart TB
    subgraph Compute["异构算力层"]
        TR[Trainium Cluster
            Project Rainier
            >1M chips / Neuron SDK]
        GPU[NVIDIA GPU Cluster
            Colossus 220k H100/H200]
        NET[高速互联 / 存储 / 电力]
    end

    subgraph Training["训练命脉"]
        DP[数据平台
            清洗 / 去重 / 安全过滤]
        TF[训练框架
            Neuron + 分布式并行]
        CK[Checkpoint / 容错]
    end

    subgraph Alignment["对齐层"]
        CON[Constitution
            可版本化原则集]
        SL[Constitutional SL
            critique + revise]
        RLA[RLAIF
            偏好模型 + RL]
    end

    subgraph Registry["模型仓库"]
        MR[Model Registry]
        INT[Interpretability Report]
    end

    subgraph Inference["推理命脉"]
        GW[API Gateway
            x-api-key / 限流 / 路由]
        ENG[推理引擎
            batching / KV cache]
        PC[(Prompt Cache
            prefix hash / TTL)]
        ET[Extended Thinking]
        CU[Computer / Tool Use]
        MA[Agent Infra
            Managed Agents / 沙箱 / checkpoint]
    end

    subgraph Governance["安全治理层 (RSP/ASL)"]
        RSP[Capability Eval]
        ASL[ASL 等级判定]
        RT[Red Team / Classifier]
        RR[Risk Report]
    end

    subgraph Product["产品层 (三云)"]
        API[Claude API]
        BR[Bedrock]
        VT[Vertex AI]
        FD[Azure Foundry]
    end

    TR --> TF
    GPU --> TF
    DP --> TF
    TF --> CK
    TF --> SL
    CON --> SL
    SL --> RLA
    RLA --> MR
    MR --> INT
    INT --> RSP
    RSP --> ASL
    ASL --> RT
    RT --> RR
    MR --> ENG
    GW --> ENG
    ENG --> PC
    ENG --> ET
    ENG --> CU
    ENG --> MA
    ENG --> API
    API --> BR
    API --> VT
    API --> FD
```

## 异构算力层

Anthropic 的算力层是整个案例中最具特色的部分——它主动选择了"两条腿走路"：

### Trainium 主力（AWS）

- **Project Rainier**：与 AWS 合作的专用超算集群，目前使用 **>100 万 Trainium2 芯片**，是"世界上最大的计算集群之一"。
- **规模承诺**（2026-04 官方扩大合作）：未来 10 年向 AWS 投入超 **$100B**，最高 **5GW** 电力，覆盖 Trainium2 → Trainium3 → Trainium4，以及 Graviton CPU；Amazon 同时追加投资（$5B 立即 + 最高 $20B 里程碑对赌）。
- **节奏**：Trainium2 容量 2026 Q2 大规模上线，Trainium3（re:Invent 2025 发布，AWS 首款 3nm 训练芯片，2.52 PFLOPS FP8、144GB HBM3e，约 2x Trainium2 算力）于 2026 年内放量；到 2026 年底 Trainium2 + Trainium3 合计接近 1GW。
- **软件栈**：AWS Neuron SDK（编译、运行时、分布式训练），与 PyTorch 集成。

### NVIDIA GPU 补充（Colossus）

- **Colossus 1**：与 SpaceXAI 合作租用的 **22 万 GPU 集群**（H100/H200，300+MW）；2026-05 Code with Claude 大会宣布获得 Colossus 1 的**独家算力接入**，用于训练未来 Claude 模型与支撑 Claude Code 的限流扩容。
- **意义**：芯片多元化降低单一供应链风险，也提升与供应商的议价能力。

### 网络与存储

- 高带宽节点内互联（Trainium 节点内高速链路 / NVLink 等）+ 集群间高速网络。
- 高吞吐并行文件系统支撑 TB 级 checkpoint。
- 电力与散热是 5GW 规模下的核心约束——Anthropic 甚至在 Colossus 合作中探讨了"轨道算力"的远期设想。

## 对齐层

对齐层把"宪法"作为一等公民的工程输入：

- **Constitution（宪法）**：一组可版本化、可追溯来源（联合国人权宣言、平台服务条款等）的原则集合。
- **Constitutional SL**：critique-revise 循环，生成修订后的监督数据。
- **RLAIF**：用宪法驱动的 AI 偏好替代人类偏好，训练偏好模型，再做 RL。

> 详见 [训练与推理流水线](04-training-and-inference) 的对齐小节。

## 推理命脉

### 接入层

- **认证**：`x-api-key` 头、organization / workspace 隔离（prompt cache 在 Claude API、Claude Platform on AWS 与 Microsoft Foundry 上为 workspace 级隔离；Bedrock 与 Google Cloud 仍为 org 级）。
- **限流**：按 tier、模型、token budget、并发；cache 命中不计入限流额度。2026-05 起 Claude Code 各套餐五小时限流额度翻倍。
- **三云入口**：Claude API、Bedrock、Vertex AI、Azure Foundry——同一模型多云托管。

### 推理引擎层

- **Continuous Batching / In-flight Batching**：提高芯片利用率、降低平均延迟。
- **KV Cache 管理**：分页式管理、长上下文（1M token 已成为 4.5 系列以来的标配）。
- **Prompt Caching**：产品级 prefix cache（prefix hash + 20-block lookback + 5m/1h TTL），是 Anthropic 最具辨识度的推理工程；2026 年起缓存读按模型分档计价（0.1x / 0.05x / 0.025x）。
- **Extended Thinking**：测试时计算（thinking budget），并在 Opus 4.5+/Sonnet 4.6+ 上默认保留 thinking block 以利于缓存复用。
- **Computer Use / Tool Use**：智能体能力的执行后端，需要沙箱、权限与长程状态管理。
- **Agent 基础设施**：2026-04 起提供 Claude Managed Agents（public beta）——托管沙箱执行、OAuth 凭据管理、会话 checkpoint、长时会话（Dreaming / Outcomes / 多智能体编排），把智能体从"客户端循环"升级为"托管运行时"。

## 安全治理层（RSP / ASL）

治理层是"什么能训/什么能发"的控制平面：

- **Capability Eval**：在训练前后评估模型是否触及 CBRN、网络、说服、自主性等能力阈值。
- **阈值判定**：RSP v3.4（2026-08）起以 **CB-1 / CB-2** 能力阈值表述生物风险等级（取代早期 ASL-2/3 命名），并含"AI 研发自动化"阈值（AI 可归因的能力进步速度翻倍）；当前模型被评估为已达 CB-1、接近 CB-2 边界。
- **防护执行**：达阈模型对应输入/输出分类器、加强的权重安全等；低阶为常规 moderation。Fable 5 系列还在 API 入口内置分类器，把可疑请求路由到 Opus 4.8 处理。
- **Risk Reports**：每 3–6 个月发布，含能力、威胁模型、缓解措施与残余风险，必要时由第三方专家审查。
- **独立评估者（2026-10 新增）**：在 Risk Report 审查之上，给第三方评估机构分三层开放访问——METR 获"近似员工级"内部访问（可独立发表、无否决权），SecureBio 审查化生放章节，Accenture / Faculty 参与红队与防护测试。治理层从"自证 + 报告"演进为"嵌入式第三方监督"。

> 详见 [核心模块](05-core-modules) 与 [企业生产实践](08-production-practice)。

## 数据面与控制面

| 平面 | 职责 | 典型系统 |
|---|---|---|
| 数据面 | 训练/推理流量、模型权重、KV cache、prompt cache | Trainium/GPU 集群、推理服务器、缓存服务 |
| 控制面 | 任务调度、模型版本、宪法版本、ASL 判定、策略、审计 | Kubernetes、Model Registry、Constitution Store、ASL Policy Engine |

## 与云厂商的关系

Anthropic 自身聚焦模型与平台，把底层算力与全球分发交给云：

- **AWS**：主力训练与云提供商，Trainium 集群 + Bedrock + Claude Platform on AWS（同账户、同控制、同计费）。
- **Google Cloud**：Vertex AI 托管 Claude，Org 级 cache 隔离。
- **Microsoft Azure**：Azure Foundry 托管 Claude。
- **SpaceXAI**：Colossus 1 独家算力接入（2026-05 起，非托管，算力供给）。

Claude 因此成为"唯一在三朵最大云上都可用的前沿模型"。

## 小结

Anthropic 的架构 = **异构算力（Trainium + GPU）+ 宪法对齐层 + 推理优化（prompt caching / extended thinking）+ 托管智能体运行时（Managed Agents）+ RSP/CB 治理层**，在"三云"上承载同一套 Claude 能力。下一章拆解训练与推理两条流水线的具体环节。
