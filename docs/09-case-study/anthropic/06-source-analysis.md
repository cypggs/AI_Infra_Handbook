# 源码与可解释性生态

与 OpenAI 类似，Anthropic 的训练/推理基础设施核心代码并未开源；但它有一个 OpenAI 几乎没有的独特开源资产——**机制可解释性研究代码**（transformer-circuits）。此外，Claude API 的工程设计与 Constitutional AI 的公开算法，也是理解其工程思想的重要入口。

## 1. transformer-circuits 与 Dictionary Learning

- **定位**：Anthropic 可解释性团队（Transformer Circuits Thread）公开发布的研究代码与实验，演示如何用稀疏自编码器（SAE）/ dictionary learning 把模型内部激活分解为可解释特征。
- **价值**：这是目前业界最系统、可复现的"打开黑箱"工具链，被全球研究者大量复用。
- **核心思想**：单个神经元往往是"多义（polysemantic）"的——一个神经元可能同时对"猫""法庭""代码"都有反应。dictionary learning 通过学习一个**过完备字典（overcomplete dictionary）**，把混合激活分解成大量**单义（monosemantic）特征**。

### SAE 的训练目标（简化示意）

```python
# 概念示意，非逐行复刻官方实现
# z = 某层（如 MLP 中间层）的激活向量
# 目标：学一个编码器 W_enc + 解码器 W_dec + 字典特征激活 f(z)
#   f(z) = ReLU(W_enc @ (z - b_dec))   # 稀疏特征激活
#   z_hat = W_dec @ f(z) + b_dec        # 重建
# 损失 = 重建误差 + sparsity 罚（如 L1 on f(z)）

def sae_loss(z, W_enc, W_dec, b_enc, b_dec, l1):
    f = torch.relu(z @ W_enc + b_enc)        # [batch, n_features]，稀疏
    z_hat = f @ W_dec + b_dec                 # 重建
    recon = ((z_hat - z) ** 2).mean()
    sparsity = l1 * f.sum(dim=-1).mean()      # 鼓励大部分特征为 0
    return recon + sparsity
```

> 工程要点：n_features 远大于激活维度（"过完备"），L1（或 TopK 等变体）保证稀疏，重建约束保证特征确实"拼得出"原始激活。训练好后，对每个特征收集"激活最强的样本"即可人工/自动标注其语义。

### 研究演进

| 阶段 | 工作 | 规模 |
|---|---|---|
| 理论基础 | A Mathematical Framework for Transformer Circuits | 小模型、induction heads |
| 单义特征 | Towards Monosemanticity | 1 层模型，~数千特征 |
| 规模化 | Scaling Monosemanticity | Claude 3 Sonnet，数百万特征 |
| 应用 | Features as Classifiers / On the Biology of an LLM | 用特征做安全相关解释 |
| 追踪 | Circuit Tracing | 单 prompt 上的电路级信息流追踪 |

## 2. Constitutional AI 算法（公开）

CAI 的两阶段算法在论文（arXiv:2212.08073）中描述清晰，可工程化复现（本主题 Mini Demo 即演示 SL 阶段的 critique-revise）：

```text
# SL 阶段（伪代码）
for request in dataset:
    response = model.generate(request)
    for principle in constitution:
        critique  = model.generate(critique_prompt(request, response, principle))
        response  = model.generate(revise_prompt(request, response, critique))
    collect (request, response)   # 用修订后的 response 做监督微调

# RLAIF 阶段（伪代码）
for request in dataset:
    a, b = model.generate(request), model.generate(request)
    pref = model.generate(prefer_prompt(request, a, b, constitution))  # "哪个更好"
    collect (request, a, b, pref)   # 训练偏好模型 PM
pm = train_preference_model(...)
policy = rl_optimize(policy, reward=pm)   # 例如 PPO
```

> 关键工程差异（vs RLHF）：`pref` 来自"模型对照宪法的判断"，而非人类标注。人类的成本从"标注每对回答"降到"撰写并维护宪法"。

## 3. Claude API 的工程设计

Anthropic 的 API 设计（`/v1/messages`）体现了几个工程取舍，值得 LLM Gateway 设计者借鉴：

- **`content` 为数组**：单条 message 可含多个 block（text / image / tool_use / tool_result / thinking），天然支持多模态与工具循环。
- **`cache_control` 字段**：自动缓存放顶层、显式断点放 block 上；与 usage 字段配合，成本可计量。
- **`thinking` block 与 `effort` / task budget**：把测试时计算作为一等参数暴露。
- **`stop_reason`**：`end_turn` / `max_tokens` / `stop_sequence` / `tool_use` 等明确区分，便于 fallback 编排。
- **usage 三段式**：`cache_read_input_tokens` + `cache_creation_input_tokens` + `input_tokens`，让"哪些 token 走了缓存"完全透明。

### 自动缓存 vs 显式断点的命中判定（官方模型）

```text
# 命中模型（简化，忠实于官方文档）
# 1. 缓存写入只发生在断点：在断点处写一个"到此为止的 prefix hash"。
# 2. 缓存读取向前回看：在断点处算 hash，若不命中，向前逐 block 查找之前写过的条目。
# 3. 回看窗口为 20 个 block。
def process(blocks, breakpoint_idx, cache, ttl):
    hit = None
    for i in range(breakpoint_idx, max(-1, breakpoint_idx - 20), -1):
        if cache.has(blocks[:i+1].hash) and not cache.expired(blocks[:i+1].hash):
            hit = i
            break
    read_tokens   = sum_tokens(blocks[:hit+1])            # 命中部分按 0.1x 计价
    write_tokens  = sum_tokens(blocks[hit+1:breakpoint_idx+1])  # 新写部分按 1.25x/2x
    input_tokens  = sum_tokens(blocks[breakpoint_idx+1:])       # 末尾动态部分按 1x
    cache.write(blocks[:breakpoint_idx+1].hash, ttl)
    return Usage(read=read_tokens, write=write_tokens, input=input_tokens)
```

> 这是本主题 Mini Demo 的核心实现思路（见下一章）。

## 4. 开源 / 开放资料地图

| 类别 | 资料 | 用途 |
|---|---|---|
| 可解释性 | transformer-circuits.pub 系列论文与代码 | 学习 SAE / dictionary learning / circuit tracing |
| 对齐 | Constitutional AI 论文 | 复现 RLAIF 思路 |
| 治理 | RSP、Frontier Safety Roadmap、Risk Reports | 设计企业级安全发布门禁 |
| API | Claude Platform Docs | prompt caching、extended thinking、tool/computer use |
| 生态 | Anthropic SDK（Python/TS）、Cookbook、Skills、MCP 官方实现 | 集成与扩展 |

## 5. 从源码/资料学到的工程模式

- **把"研究方法"变成"可复现代码"**：dictionary learning 公开代码让"打开黑箱"从论文走进了工程实践。
- **把"对齐目标"变成"管线"**：CAI 的两阶段伪代码可直接落地为训练管线，而非黑箱技巧。
- **把"成本优化"变成"可计量的产品字段"**：usage 三段式让 prompt caching 的收益对开发者完全透明。
- **把"安全"变成"门禁 + 报告"**：RSP/ASL 把抽象的安全要求翻译成可审计的工程流程。

## 小结

Anthropic 的开源虽不如 Meta（Llama）"重"，但极有特色：transformer-circuits 让可解释性可复现，Constitutional AI 让对齐可工程化，Claude API 让推理优化可计量，RSP 让安全治理可审计。下一章通过 Mini Demo 动手复现其中两个核心机制。
