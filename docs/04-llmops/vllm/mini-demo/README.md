# Mini vLLM Demo

一个用于教学的极简 vLLM 实现，展示 **PagedAttention** 的 Block Table 机制与 **Continuous Batching** 的迭代级调度逻辑。

## 设计目标

- 不依赖 GPU，CPU 即可运行
- 代码量控制在 500~1500 行
- 可运行、可测试
- 帮助理解 vLLM 的核心设计思想

## 文件说明

| 文件 | 说明 |
|---|---|
| `vllm_mini/paged_attention.py` | Block、BlockManager、Paged KV Cache |
| `vllm_mini/scheduler.py` | Sequence、SequenceGroup、Scheduler（Waiting/Running/Swapped 三队列） |
| `vllm_mini/model_runner.py` | DummyModel 与 Greedy Sampler |
| `vllm_mini/worker.py` | 协调 BlockManager 与 ModelRunner |
| `vllm_mini/demo.py` | 入口脚本，模拟多请求并发场景 |
| `tests/test_scheduler.py` | pytest 测试 |

## 运行方式

```bash
# 进入 demo 目录
cd docs/04-llmops/vllm/mini-demo

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e ".[dev]"

# 运行 demo
python -m vllm_mini.demo

# 运行测试
pytest tests/
```

## 预期输出

```
[Iter 0] running=['seq_0', 'seq_1'], finished=[], blocks=2/32
[Iter 1] running=['seq_0', 'seq_1'], finished=[], blocks=2/32
[Iter 2] running=['seq_0', 'seq_1', 'seq_2'], finished=[], blocks=4/32
...
[Iter N] running=[], finished=['seq_0', 'seq_1', 'seq_2', 'seq_3'], blocks=0/32

=== Final outputs ===
seq_0: prompt=[1, 2, 3, 4, 5] output=[...]
...
```

## 关键观察

1. **Block 按需分配**：sequence 实际生成 token 时才会占用新的 Block，而不是预先分配最大长度。
2. **Continuous Batching**：新请求可以在任意 iteration 边界加入运行中的 batch。
3. **资源回收**：sequence 完成后 Block 回到 free pool，可被其他 sequence 复用。

## 与真实 vLLM 的区别

| 方面 | Mini Demo | 真实 vLLM |
|---|---|---|
| 模型 | Dummy 小模型 | 真实 Transformer |
| Attention | 未实现真实注意力 | PagedAttention CUDA Kernel |
| 分布式 | 单 Worker | TP / PP |
| 量化 | 不支持 | AWQ / GPTQ / FP8 |
| Swap | 简化逻辑 | CPU-GPU 双向 swap |

本 Demo 只关注协议与调度思想，不追求性能。
