# 源码与开源生态

OpenAI 的训练与推理基础设施大量代码并未开源，但通过其公开项目、System Cards 与合作方披露，我们仍能提炼出关键工程模式。

## 1. OpenAI Triton

- **定位**：Python-like 语言与编译器，用于编写高效的 GPU kernel，目标是替代 CUDA。
- **意义**：降低 GPU kernel 开发门槛，让研究者更容易实现自定义 attention、矩阵乘法、量化算子。
- **影响**：vLLM、PyTorch 2.0 compile、SGLang 等都采用了 Triton 编写 kernel。
- **源码入口**：`python/triton/language/core.py` 定义 DSL，`lib/Dialect` 是 MLIR 编译层。

```python
import triton
import triton.language as tl

@triton.jit
def add_kernel(x_ptr, y_ptr, output_ptr, n_elements, BLOCK_SIZE: tl.constexpr):
    pid = tl.program_id(axis=0)
    block_start = pid * BLOCK_SIZE
    offsets = block_start + tl.arange(0, BLOCK_SIZE)
    mask = offsets < n_elements
    x = tl.load(x_ptr + offsets, mask=mask)
    y = tl.load(y_ptr + offsets, mask=mask)
    tl.store(output_ptr + offsets, x + y, mask=mask)
```

## 2. GPT-2 官方实现

- **定位**：OpenAI 最早开源的大模型实现之一。
- **价值**：展示了 Transformer decoder-only 架构、BPE tokenization、生成采样策略。
- **源码入口**：`src/model.py` 是核心 Transformer，`src/sample.py` 是自回归生成。

## 3. CLIP

- **定位**：对比学习视觉-语言模型。
- **价值**：
  - 展示了多模态预训练范式。
  - 其数据过滤与训练技巧被后续多模态模型借鉴。
- **源码入口**：`clip/model.py`、`clip/clip.py`。

## 4. Whisper

- **定位**：通用语音识别模型。
- **价值**：
  - 端到端 Transformer 架构，支持多语言与翻译。
  - 展示了如何把一个研究模型打包成易部署的库。
- **源码入口**：`whisper/model.py`、`whisper/transcribe.py`。

## 5. System Cards

- **定位**：OpenAI 发布的模型安全与能力评估报告。
- **示例**：GPT-4 System Card、GPT-4o System Card、o1 System Card。
- **内容**：
  - 模型能力概述。
  - 风险类别评估（cybersecurity、CBRN、persuasion、autonomy）。
  - 红队测试结果。
  - 缓解措施与剩余风险。
- **工程意义**：把安全评估流程标准化、文档化，可作为企业内部模型发布的模板。

## 6. Preparedness Framework

- **定位**：OpenAI 的前沿风险治理框架。
- **核心**：
  - 四类风险：Cybersecurity、CBRN、Persuasion、Model Autonomy。
  - 风险等级：low、medium、high、critical。
  - 部署门槛：high/critical 风险需额外缓解与监督。
- **工程落地**：需要 eval pipeline、red team platform、model registry gating。

## 7. 与开源生态的关系

| 领域 | OpenAI 贡献/采用 | 行业影响 |
|---|---|---|
| GPU Kernel | Triton | 成为 PyTorch/vLLM/SGLang 的 kernel 基础设施 |
| 语音识别 | Whisper | 被大量应用集成，推动端到端 ASR 普及 |
| 多模态 | CLIP | 奠定视觉-语言预训练基础 |
| 推理优化 | 未开源，但采用 continuous batching、speculative decoding | 推动 vLLM、TensorRT-LLM 等开源项目 |
| 安全评估 | System Cards、Preparedness Framework | 成为企业发布大模型的安全报告范式 |

## 8. 从源码学到的工程模式

- **DSL + 编译器**：Triton 证明“用高级语言写高性能 kernel”是可行的。
- **端到端模型库**：Whisper 展示如何把研究模型变成 `pip install` 即可用的产品。
- **标准化评估报告**：System Cards 把安全评估从内部文档变成可对外发布的 artifact。
- **研究与工程协同**：开源项目往往是研究 idea 的工程化验证，再反哺产品。

## 小结

OpenAI 的开源项目虽然不如 Meta（Llama）多，但每一件都切中要害：Triton 降低 GPU 编程门槛，Whisper/CLIP 推动多模态应用，System Cards 建立安全评估标准。下一章通过 Mini Demo 复现一个 OpenAI-style API 服务的核心控制。
