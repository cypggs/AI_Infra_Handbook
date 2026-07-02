# 2. 核心思想

## 一句话理解

> TensorRT-LLM 把 LLM 推理拆成两段：**构建期**把模型编译成一张针对 GPU 深度优化的执行图；**运行期**用 Executor 持续动态批处理请求，让 GPU 尽量满载。

## 核心抽象

### 1. Builder（构建器）

Builder 负责把模型定义（来自 HuggingFace、NVIDIA Megatron、GPTQ/AWQ/FP8 checkpoint 等）转换成可执行产物。historically 它输出 TensorRT engine / plan；在 1.2 之后，Builder 的概念更多体现在 **LLM API 的初始化与编译流程** 中：

```python
from tensorrt_llm import LLM
llm = LLM(model="meta-llama/Llama-3.1-8B-Instruct")
```

`LLM(model=...)` 会隐式完成：权重加载 → 量化配置解析 → 模型转换 → 编译/优化 → Executor 启动。

### 2. Engine / Plan（执行计划）

在 TensorRT 时代，Engine 是 Builder 产出的序列化二进制，包含：

- 每个算子的 CUDA kernel 选择
- 张量显存布局与生命周期
- 融合后的计算图（如 fused attention、 fused MLP）
- 精度配置（FP16 / FP8 / FP4 / INT8）

在 PyTorch 后端时代，Engine 的概念被 **PyTorchModelEngine** 取代：它持有语言模型，并通过 `torch.compile`、CUDA Graph、自定义 Triton kernel、Plugin 等方式实现类似甚至更强的执行优化。对上层用户而言，仍然是“加载一次、多次运行”。

### 3. Runtime / Executor（运行时与执行器）

Runtime 是执行 Engine 的环境；Executor 是面向服务的调度与执行入口。在 PyTorch 后端中：

- `LLM` 是 Python 入口，封装 tokenization / detokenization。
- `PyExecutor(Worker)` 在每个 rank 上运行一个持续后台循环。
- `PyExecutor` 内部维护 Scheduler、ModelEngine、Decoder、KVCacheManager，完成每轮的 IFB 调度与执行。

### 4. Plugin（插件）

TRT-LLM 内置大量自定义 CUDA plugin，也支持用户通过 `@trtllm_plugin("Name")` 注册：

```python
class MyPlugin(PluginBase):
    def shape_dtype_inference(self, ...): ...
    def forward(self, ...): ...
```

historically 关键 plugin 包括：

- `gpt_attention_plugin`：融合 masked / flash / paged attention
- `gemm_plugin`：融合 GEMM + bias + activation
- `nccl_plugin`：多 GPU 通信算子

PyTorch 后端时代，plugin 机制仍然存在，但更多以 custom op / Triton kernel / PyTorch extension 的形式融入模型执行图。

### 5. In-flight Batching（IFB）

IFB 是 TRT-LLM 的运行时核心优化之一：在同一个 batch 中交错执行 context-phase（prefill）与 generation-phase（decode）请求，而不是等到所有 prefill 完成再统一 decode。

关键规则：

- 每轮优先调度 generation-phase 请求，保证 decode 不被长 prefill 阻塞。
- 剩余 token budget 再分配给 context-phase 请求。
- 输入必须 packed（无 padding），否则无法做 IFB。

IFB 与 vLLM / SGLang 的 Continuous Batching 本质相同，只是 TRT-LLM 更强调与 compiled engine 的结合。

### 6. Compile vs Interpret（编译 vs 解释执行）

| 维度 | Compile（TRT-LLM） | Interpret（vLLM / SGLang Eager） |
|---|---|---|
| 优化时机 | 构建期 | 运行期 |
| 算子融合 | 全局优化，可跨层融合 | 受限于 PyTorch 即时执行 |
| 动态 shape | 需要指定 profile / 动态范围 | 天然支持 |
| 启动时间 | 构建/编译耗时 | 几乎即开即用 |
| 极限性能 | 更高（NVIDIA 硬件） | 通用场景足够 |

TRT-LLM 的核心取舍是：**用构建期时间换运行期性能**。

## 设计哲学

| 设计选择 | 解决的问题 | Trade-off |
|---|---|---|
| Builder / Engine 分离 | 构建期做全局优化，运行期只做轻量加载 | 构建耗时、需要处理版本兼容性 |
| In-flight Batching | 提高 GPU 利用率、降低尾部延迟 | 调度复杂度、必须 packed input |
| Paged KV Cache | 减少显存碎片、支持前缀复用 | 需要维护 block table |
| Plugin 机制 | 注入硬件定制 kernel | 增加模型适配成本 |
| 多精度量化 | 降低显存、提升吞吐 | 精度损失风险、校准流程 |
| 移除 TensorRT 后端 | 简化维护、拥抱 PyTorch 生态 | 老用户迁移、部分极致优化路径变化 |

## 与 vLLM / SGLang 核心思想的对比

| 维度 | vLLM | SGLang | TensorRT-LLM |
|---|---|---|---|
| 核心问题 | 通用高吞吐 | LLM 程序高效执行 | NVIDIA 极致性能 |
| 主要武器 | PagedAttention + Continuous Batching | RadixAttention + Compiler | Compile + IFB + Plugin |
| KV Cache 管理 | Block Table | Radix Tree | Block-based / Paged |
| 用户接口 | OpenAI API / LLM class | `gen`/`select`/`fork` | `LLM.generate` / Triton backend |
| 优化重心 | 运行期调度 | 程序级复用与约束 | 构建期编译与硬件 kernel |

## 本章小结

TensorRT-LLM 的核心思想可以概括为：**构建期用编译/优化把模型变成硬件专属执行图，运行期用 In-flight Batching + Paged KV Cache 持续满载执行**。1.2 之后，TensorRT 后端退出历史舞台，PyTorch 后端通过 `torch.compile`、CUDA Graph、custom plugin 等手段延续了这一思想，同时让生态集成更平滑。
