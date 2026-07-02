# 7. 工程实践：Mini vLLM

本章实现一个教学版 Mini vLLM，核心目标是理解 **PagedAttention 的 Block Table 机制** 与 **Continuous Batching 的调度逻辑**。

## 设计目标

- 不依赖 GPU，使用 PyTorch CPU 即可运行
- 代码控制在 500~1500 行
- 展示 Block 分配、回收、共享
- 展示 iteration-level 调度
- 展示 prefill / decode 两阶段

## 目录结构

```
mini-demo/
├── README.md
├── pyproject.toml
├── vllm_mini/
│   ├── __init__.py
│   ├── paged_attention.py    # Block / BlockManager / Paged KV Cache
│   ├── scheduler.py          # Continuous Batching 调度器
│   ├── worker.py             # 模拟 Worker
│   ├── model_runner.py       # 模型执行入口
│   └── api_server.py         # 简单 HTTP API（可选）
└── tests/
    └── test_scheduler.py
```

## 核心设计

### 1. Block

每个 Block 存储固定数量 token 的 KV 张量。

```python
class Block:
    def __init__(self, block_size, num_heads, head_size):
        self.block_size = block_size
        self.k_cache = torch.zeros(block_size, num_heads, head_size)
        self.v_cache = torch.zeros(block_size, num_heads, head_size)
        self.ref_count = 0
```

### 2. BlockManager

维护 free block pool 和每个 sequence 的 block table。

```python
class BlockManager:
    def __init__(self, num_blocks, block_size, ...):
        self.free_blocks = [Block(...) for _ in range(num_blocks)]
        self.block_tables = {}

    def allocate(self, seq_id, num_tokens):
        # 按需分配 block，并建立 block table
        ...
```

### 3. Scheduler

维护三个队列，每轮选择可执行的 sequence。

```python
class Scheduler:
    def schedule(self):
        # 1. 尝试从 waiting 加入 running
        # 2. 对 running 中的 sequence 执行 decode
        # 3. 处理完成 / 抢占
        ...
```

### 4. Model Runner

使用一个极小的 dummy model 模拟 forward。

```python
class DummyModel(nn.Module):
    def forward(self, input_ids):
        # 输出 logits，用于采样
        ...
```

## 运行方式

```bash
cd docs/04-llmops/vllm/mini-demo
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m vllm_mini.demo
```

## 预期输出

程序会模拟多个请求并发进入系统：

```
[Iter 0] Prefill seq_0 (tokens=10), seq_1 (tokens=5)
[Iter 1] Decode seq_0, seq_1, seq_2(prefill)
[Iter 2] Decode seq_0, seq_1, seq_2
...
[Done] seq_0 output: ...
```

## 完整代码

完整代码详见 [mini-demo/README.md](./mini-demo/README.md)。

## 本章小结

Mini Demo 的价值不在于性能，而在于把 vLLM 最核心的两个机制（PagedAttention + Continuous Batching）从源码中抽象出来，让人能用几十行代码看懂设计本质。
