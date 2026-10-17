# 4. 训练与推理工作流程

## 4.1 一次 V3 训练的完整链路

把 3.6 节的架构展开成时序。一个 micro-batch 的前向在 EP 组（8 节点 × 8 卡）内的旅程：

```mermaid
sequenceDiagram
    participant C as CPU/Dataloader
    participant S0 as Stage s 本卡
    participant EP as EP 组其它 63 卡
    participant S1 as Stage s+1
    C->>S0: 3FS 随机读样本（免预取，直接进卡）
    S0->>S0: Router 打分，top-8 选专家<br/>（无辅助损失，bias 动态修正均衡）
    S0->>EP: DeepEP dispatch：token×FP8 激活 → 目标专家所在卡<br/>（节点受限路由：每 token 最多 4 节点）
    EP-->>S0: 收齐后发回确认（重叠开始）
    S0->>S0: 本地 4 个专家：FP8 grouped GEMM（DeepGEMM）<br/>同时：下一 micro-batch 的 dispatch 已在路上
    S0->>EP: combine：专家输出加权求和 all-to-all 收回
    S0->>S0: MLA 注意力（训练用标准 MHA 语义，潜向量在线展开）
    S0->>S1: DualPipe：前向激活经 PP 边界下发<br/>（与反向 B_in/B_w 重叠）
    Note over S0,EP: 反向：同样的 all-to-all 走一轮梯度<br/>RMSNorm/MLA 上投影用重计算省显存
```

几个容易忽略但决定成败的细节：

1. **Router 在 dispatch 之前**——均衡性（aux-loss-free 的 bias 项）决定了 all-to-all 的尾部延迟，是"通信账"的第一推动力。
2. **FP8 出现在两个位置**：激活以 FP8 量化后进 DeepGEMM（前向 1x128 行分组、反向 128x1 列分组），DeepEP 还支持 FP8 dispatch 直接传输量化后的激活。
3. **重计算策略**：只重计算 RMSNorm 与 MLA 上投影这类"廉价且吃显存"的算子，大规模重计算（full recompute）会吃掉 FP8 省下的算力，不划算——这是"Extremely Memory Saving with Minimal Overhead"一节的取舍。
4. **EMA 放 CPU**：指数滑动平均参数（评估用）不占 GPU 显存。
5. **每个 optimizer step 结束**：梯度经 ZeRO-1 分片聚合，checkpoint 高吞吐并行写入 3FS。

训练的宏观账（技术报告 Table 1 + §4）：

| 项目 | 数字 |
|---|---|
| 预训练数据 | 14.8T 高质量多语 tokens |
| 上下文扩展 | 两阶段：32K → 128K（119K GPU 小时） |
| 单 1T tokens 成本 | 180K H800 GPU 小时 ≈ 2048 卡 × 3.7 天 |
| 预训练总时长 | 不到两个月（2664K GPU 小时） |
| 后训练 | 5K GPU 小时（SFT + RL） |
| 数值稳定性 | 全程零不可恢复 loss spike、零回滚 |

## 4.2 R1 的训练流程：让推理能力涌现

R1（arXiv:2501.12948）展示的是**第二类工程**：不是把训练算力压下来，而是把 RL 的工程量做上去。

```mermaid
flowchart LR
    subgraph Zero["R1-Zero：纯 RL，证明可行性"]
        B0[V3-Base] --> RL0[GRPO 强化学习<br/>规则奖励：答案对错 / 格式]
        RL0 --> Z[ AIME 2024 pass@1<br/>15.6% → 77.9%<br/>自发出现反思与验证 ]
    end
    subgraph R1["DeepSeek-R1：四阶段 pipeline"]
        CS[① Cold-start 数据<br/>数千条带思考过程对话] --> RRL[② 推理 RL<br/>语言一致性奖励]
        RRL --> RS[③ 拒绝采样 + SFT<br/>600K 推理 + 200K 非推理样本]
        RS --> ARL[④ 全场景 RL<br/>有用性/无害性/推理统一]
    end
    Z -.继承能力，修正可读性.-> R1
    ARL --> D[蒸馏到 Qwen 1.5B-32B<br/>Llama 8B/70B（MIT）]
```

关键机制与数字：

- **GRPO（Group Relative Policy Optimization）**：PPO 的变体，去掉 value model，用一组采样结果的相对排名估计优势——省下一个 critic 模型的训练与显存开销；
- **R1-Zero 的涌现曲线**：纯 RL 过程中 AIME 2024 pass@1 从 15.6% 一路涨到 77.9%，并自发出现"延长思考时间、自我验证"的行为——这是"推理是 RL 的自然产物"这一论点的实证；
- **R1 的代价与修正**：R1-Zero 有可读性差、语言混杂问题，四阶段 pipeline 用少量 cold-start 数据修正风格而不损伤推理能力；
- **最终成绩**：AIME 2024 pass@1 **79.8%**（OpenAI-o1-1217 为 79.2%）、MATH-500 **97.3%**、SWE-bench Verified **49.2%**、Codeforces 评分 **2029**（超越 96.3% 的人类选手）；
- **开放策略**：R1 及蒸馏系列全部 **MIT 许可**——这是"DeepSeek 时刻"的直接引爆点之一。

## 4.3 V3.2 的稀疏注意力训练流程

V3.2（arXiv:2512.02556，及其实验先行版 V3.2-Exp）引入了 **DSA（DeepSeek Sparse Attention）**，训练流程值得一提，因为它展示了"架构改动如何以最小代价嫁接到已训练好的模型上"：

```mermaid
flowchart TB
    T[V3.1-Terminus（128K 上下文基座）] --> W[① Dense Warm-up<br/>少量步数让 lightning indexer 学会打分]
    W --> SP[② Sparse Training<br/>每 query 只对 top-2048 KV 做注意力]
    SP --> PT[③ 后训练<br/>专家蒸馏 + 混合 RL（同样用 DSA）]
    PT --> V32[DeepSeek-V3.2]
    PT --> SPE[V3.2-Speciale<br/>高算力变体：IMO/IOI 金牌]
```

已验证的关键数字：

- **稀疏训练**：每 query 从 128K 上下文中选 **2048** 个 KV；15000 步 × 每步 480 条 128K 序列 = **943.7B tokens**，学习率 7.3e-6；
- **机制**：**lightning indexer** 用低维潜向量做类 MQA 打分（仍是 O(L²) 但维度极低），主注意力只对 top-K 选中项计算，复杂度从 O(L²) 降到 **O(L·k)**（k=2048 时全量的 1/64）； indexer 的训练损失与主模型解耦（只拿索引损失优化）；
- **质量对齐**：公开 benchmark 上与 V3.1-Terminus 基本持平（MMLU-Pro 85.0 vs 85.0，AIME 2025 89.3 vs 88.4）——这是"细粒度稀疏几乎无损"的实证；
- **后训练**：沿用 V3.2-Exp 的 pipeline（专家蒸馏 + 混合 RL），并扩展到 **大规模 agentic 任务合成**：1800+ 个合成环境、85000 条复杂提示，把"推理融入工具调用"；后训练总算力被刻意提高到预训练的 **10% 以上**；
- **Speciale**：高算力变体在 IMO 2025 与 IOI 2025 达到金牌水平，推理能力与 Gemini-3.0-Pro 同级、超越 GPT-5。

## 4.4 推理工作流程：从请求到 token

以一次 chat 请求为例（V3.2 时代，PD 分离 + DSA）：

```mermaid
flowchart LR
    REQ[用户请求<br/>最长 128K 上下文] --> LB[负载均衡<br/>按 prefill/decode 分流]
    LB --> P[Prefill 节点组<br/>4 节点/32 GPU 最小单元<br/>8+1 冗余专家]
    P --> K1[lightning indexer 打分<br/>选出 top-2048 KV]
    K1 --> K2[MLA 潜向量压缩 KV<br/>写入 GPU 显存 + 3FS KVCache 卸载]
    K2 --> D[Decode 节点<br/>EP 并行逐 token 生成]
    D --> OUT[流式输出]
    D -.下一请求复用.-> K2
```

要点：

- **Prefill 是吞吐战场**：两个 micro-batch 交叉，attention/MoE 计算与 all-to-all 通信重叠（训练侧 DualPipe 思想的推理版）；冗余专家吸收路由热点；
- **Decode 是带宽战场**：MLA 把每 token 每层 KV 压到 1.12 KiB（对照 MHA 64 KiB），DSA 又把"要读的历史 KV"压到 1/64 以内——两个乘法叠加，长上下文解码的显存带宽压力比"朴素 MHA + 稠密注意力"低三个数量级；
- **KVCache 三层存储**：GPU 显存（热）→ 3FS SSD 池（温，40+ GiB/s 单客户端）→ 淘汰。对多轮对话与 agentic 长轨迹，命中温层就是成本差一个数量级的事；
- **错峰调度**：API 层用峰谷定价（2025-02 起 75% 折扣窗口；2026-08 起改为峰谷半价）把可延迟负载赶到夜间，把"闲置容量"变成收入（见 [第 8 章](08-production-practice)）。

## 4.5 工作流程中的四次"账本核对"

把四节串起来，DeepSeek 的每个流程节点都对应一本可核对的账：

| 流程节点 | 账本 | 关键数字 |
|---|---|---|
| 数据进卡 | 3FS 随机读带宽账 | 6.6 TiB/s 聚合读，dataloader 免预取 |
| 专家计算 | FP8 精度账 | 端到端损失误差 低于 0.25%（vs BF16，附录 B） |
| 跨卡搬运 | all-to-all 通信账 | 每 token 229 KB（BF16 dispatch+combine），计算通信比 ~140× |
| 流水线推进 | DualPipe 气泡账 | (PP/2-1)(F+B-3W)，PP=16 时较 1F1B 缩减 62.7% |
| 权重落盘 | checkpoint 吞吐账 | 高吞吐并行写 3FS |
| 推理服务 | 每 token 成本账 | 73.7K/14.8K tokens/s/节点，理论利润率 545% |

其中 all-to-all 通信账与 DualPipe 气泡账可以在 [Mini Demo](07-mini-demo) 里亲手复算——这也是下一章 [核心模块](05-core-modules) 逐模块展开这些机制的原因。
