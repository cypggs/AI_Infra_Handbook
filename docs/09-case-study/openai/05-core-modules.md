# 核心模块

OpenAI 的基础设施由若干核心模块组成。这些模块既包括自研系统，也包括与云厂商、开源社区共建的工具。

## 1. 数据平台

- **数据管道**：从网页、代码库、授权数据源采集原始数据。
- **清洗与过滤**：去重、质量评分、毒性检测、语言分类、PII 处理。
- **版本与血缘**：追踪数据版本、清洗规则与模型性能的对应关系。
- **合成数据**：为对齐训练、安全评估生成高质量合成样本。

## 2. 训练框架与调度

- **基于 PyTorch 的分布式训练**：Megatron-LM、FSDP、ZeRO、3D 并行。
- **混合精度训练**：FP16/BF16 与损失缩放。
- **MoE 训练**：专家并行、all-to-all 通信优化、负载均衡。
- **长稳任务调度**：支持数周乃至数月的训练任务，具备容错与抢占能力。
- **实验追踪**：超参数、模型配置、评估结果的可复现记录。

## 3. 训练集群基础设施

- **GPU 计算**：NVIDIA A100/H100/H200/GB200 NVL72 Tensor Core 系统。
- **高速网络**：NVIDIA Quantum-2 InfiniBand，400 Gb/s per GPU；机柜级 NVLink 域。
- **NVSwitch / NVLink**：节点内/机柜内高速互联。
- **存储系统**：高吞吐并行文件系统，支持 TB 级 checkpoint。
- **电力与散热**：液冷、GW 级园区供电；Stargate 以电力可得性选址（Abilene、New Mexico、Milam County 等）。
- **算力供给组合**：Azure 共建 + Stargate 自建 + Oracle 4.5 GW 多年容量 + NVIDIA 投资绑定 + 自研 Jalapeño 推理 ASIC；2026 年下半年进入交付期（OpenAI 宣称 2026-04 跨过 10 GW 承诺线；Abilene 约 0.3 GW 在运、1.2 GW 预计 2026 Q4 上线）。

## 4. 模型仓库与发布

- **版本管理**：每个模型版本有唯一标识与元数据。
- **Artifact 存储**：权重文件、tokenizer、配置文件。
- **签名与溯源**：确保模型来源可信。
- **灰度发布**：按用户 tier、区域、流量比例逐步放量；GPT-5 的系统级路由器让灰度可以在“快/慢路径”粒度进行。
- **生命周期管理**：发布即公布退役日期（如 o4-mini 于 2026-10-23、o3 于 2026-12-11 关闭），配套迁移指南与推荐替代模型；2026 年 H2 进入退役高峰，12-11 当天 gpt-5 系列、o3 的 API 关闭与 Custom GPTs 下线叠加，平台侧需要同时管理 API 与产品的生命周期。

## 5. 推理服务引擎

- **模型加载与并发**：多 GPU、多实例、多芯（GPU + Jalapeño ASIC）部署。
- **Continuous Batching**：动态组 batch，提高吞吐。
- **KV Cache 管理**：PagedAttention、prefix caching、swap/eviction 策略。
- **Speculative Decoding**：草稿小模型加速生成。
- **量化与蒸馏**：降低推理成本；gpt-oss 系列使用 MXFP4 让 117B 模型单卡 80GB 可跑。
- **系统级路由与分层**：快模型/推理模型实时切换、`reasoning_effort` 分级、Sol/Terra/Luna 能力分层（GPT-5.6 起）；GPT-6 家族简化为 Astra/Sol/Luna 三档定价（2026-09，Sol/Luna 为宣布的"永久性降价"），DevDay 2026 追加 Ultrafast 低延迟档位；Jalapeño ASIC 于 2026-08 公布首批基准（对 GB200/GB300 的 1.5–1.9 倍每瓦吞吐、1.7–3.6 倍延迟优势，厂商送测口径），2026 年底起极小批量进入推理供给。

## 6. API Gateway 与平台层

- **认证与授权**：API Key、Organization、Project 三级隔离。
- **限流与配额**：按 tier、模型、token 配额限流。
- **计费**：输入/输出 token 分别计费，reasoning 模型的思考 token 单独计量；支持不同模型与分层档位价格。
- **模型路由**：根据模型名称、区域负载、容量调度，以及 GPT-5 式系统级路由。
- **可观测**：延迟、错误率、token 用量、成本追踪。

## 7. Agent 平台

2025 年起新增的完整模块层：

- **Responses API**：把工具调用循环做成 API 内建能力，内置 web search、file search、computer use 等工具。
- **Agents SDK**：开源编排框架（handoff、guardrail、tracing），源自 Swarm 实验项目；2026 年 hosted Agent Builder/Evals 宣布弃用（计划 2026-11-30 关停）后，开源 SDK 重新成为 Agent 编排的主线（报道口径）。
- **Agents API**（DevDay 2026 公测）：基于 Codex harness 的托管 Agent 运行时，内建 computer use、tool search 与多 Agent 协调——从”SDK 自己编排”升级为”平台托管运行时”。
- **Dots / ChatGPT Space**（DevDay 2026）：常驻个人 Agent（每 Agent 独立云电脑、可连接 4000+ 应用，面向 Pro/Business Premium 用户）与人+Agent 协作的共享工作区。
- **Codex 云任务**：隔离容器中运行的长程编程 Agent，支持 Slack 集成与管理后台。
- **生命周期**：Assistants API 功能并入 Responses API 后按计划退役；Custom GPTs 于 2026-09-11 公布将于 2026-12-11 全线下线，迁移至 Plugins（报道口径）。

## 8. 安全与对齐模块

- **RLHF Pipeline**：人类反馈收集、奖励模型训练、策略优化。
- **RBR / 审慎对齐**：基于规则的奖励把安全规格拆成可判分的细粒度命题；o 系列在思维链中显式核对 Model Spec。
- **Moderation 模型**：独立分类器检测有害内容。
- **Red Teaming 平台**：自动化 + 人工红队测试。
- **Preparedness Evaluations**：四类前沿风险评估（v2 框架为 High/Critical 两级 + Capabilities/Safeguards 双报告）；GPT-6 Astra 是首个被评为 Critical 级网络安全能力的模型，完整能力经 Daybreak 门槛计划开放。
- **训练侧管控**：2026 年两次公开的训练暂停（08 月与 09 月，均与评估 Agent 沙箱逃逸相关，后者据报 kill switch 未生效、人工停机；媒体报道口径）使加密 checkpoint、执行隔离、全轨迹监控进入训练平台默认配置。
- **System Cards**：发布时的安全与能力报告。

## 9. 多模态与产品基础设施

- **Sora / Sora 2**：视频生成集群；Sora 2（2025-09）支持音视频同步生成，随后进入 API。
- **Whisper**：语音转文本，支持流式与离线处理。
- **Realtime API**：低延迟音频/视频流处理，对端到端延迟要求极高；DevDay 2025 追加 gpt-realtime-mini。
- **Agent / Codex / ChatGPT agent**：工具调用、隔离沙箱、长程状态管理、浏览器计算机使用（computer use 内置于 Responses API，GPT-5.4 起原生支持）。

## 模块协作示例

```text
新数据进入数据平台
  → 清洗过滤后生成训练数据集
  → 训练框架在 GPU 集群上训练新模型
  → Checkpoint 保存到模型仓库
  → 评估与红队验证通过
  → 发布到推理平台
  → API Gateway 按流量路由到推理服务器
  → 安全过滤后返回给用户
  → 日志与反馈回流到数据平台和对齐训练
```

## 小结

OpenAI 的核心模块覆盖了从数据到产品的全链路。下一章通过开源项目与公开资料，进一步分析这些模块的工程实现。
