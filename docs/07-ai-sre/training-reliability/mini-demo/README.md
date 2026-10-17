# Training Reliability Mini Demo

一个纯 numpy 的 Python 原型，演示大规模训练可靠性工程的五个核心量化模型（AI Infra Handbook `docs/07-ai-sre/training-reliability/` 主题配套）：

- 可用率 vs 集群规模（MTBF/MTTR 模型，含 Kokolis HPCA'25 与 Llama 3 两组校准锚点）
- checkpoint 间隔优化（Daly 公式 vs 网格精确最优；差量 checkpoint 对比）
- 故障注入 + 弹性恢复（Llama 3 故障分类占比；冷重启 vs 热备的 ETTR 对比）
- straggler 检测与缓解（中位数法慢节点检测；替换后 step 时间恢复）
- SDC 双跑对比检测（bit flip 注入、分片指纹定位、loss 尖刺守卫）

所有模型 CPU 可运行、固定种子、输出确定。恢复时间线常数来自一手测量：TrainMover（arXiv:2412.12636，8,192 卡冷重启 6.47 min 拆解）与 ByteDance ByteRobust（arXiv:2509.16293，热备 hot-update 46-65 s、检测 2s/10s/30s）。

## 运行

```bash
cd docs/07-ai-sre/training-reliability/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m training_reliability_mini.demo
```

## 目录结构

```text
mini-demo/
├── README.md
├── pyproject.toml
├── conftest.py
├── training_reliability_mini/
│   ├── __init__.py
│   ├── availability.py   # MTBF/MTTR、可用率、ETTR 简化模型
│   ├── checkpoint.py     # checkpoint 间隔优化（Daly + 网格精确解）
│   ├── recovery.py       # 故障 taxonomy、注入、冷/热恢复时间线
│   ├── straggler.py      # 同步 step=max 语义、中位数法检测、替换缓解
│   ├── sdc.py            # bit flip 注入、双跑对比、分片指纹、尖刺检测
│   └── demo.py           # 五场景一键入口
└── tests/
    ├── test_availability.py
    ├── test_checkpoint.py
    ├── test_recovery.py
    ├── test_straggler.py
    ├── test_sdc.py
    └── test_demo.py
```

## 设计要点

- `availability.py` 用 `job MTBF = 节点 MTBF / N` 的独立故障指数模型反推两组实测锚点。
- `checkpoint.py` 同时给出 Daly 近似 `T* ≈ sqrt(2CM)` 与对长程效率的网格精确最优，两者互相校验。
- `recovery.py` 的恢复时间线逐分钟对齐 TrainMover Table 1 与 ByteRobust 的检测时延表。
- `straggler.py` 体现同步训练的"木桶语义"：一个慢 20% 的 rank 让所有 rank 的每个 step 慢 20%。
- `sdc.py` 模拟硬件 bit flip 导致的静默错误，以及两道防线：双跑逐位对比（高成本、零漏报）与 loss/grad-norm 尖刺守卫（低成本、事后）。

## 与真实系统的差异

| 方面 | Mini Demo | 真实系统 |
|---|---|---|
| 故障过程 | 固定种子泊松采样 | 真实故障有突发、级联与相关性（整机架断电） |
| 恢复 | 解析时间线常数 | NCCL 重建、checkpoint 加载与 warmup 依赖实现与拓扑 |
| checkpoint | 单参数阻塞模型 | 分层（GPU/CPU DRAM/本地 SSD/远端存储）+ 异步 + 差量 |
| straggler | 单轮中位数法 | 多轮投票、通信栈级归因（FALCON culprit score） |
| SDC | float64 bit flip | HBM/SRAM/CPU/网络全链路，检测需冗余计算或编码 |
