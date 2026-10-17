# deepseek-case-mini

DeepSeek 训练系统核心机制的纯 Python（numpy）CPU 模拟器，配套
《AI Infra Handbook · DeepSeek 案例研究》第 7 章。所有随机性均通过
固定 seed 的 `numpy.random.default_rng` 注入，结果完全确定。

## 模块

| 模块 | 复现对象 | 关键机制 |
|---|---|---|
| `pipeline.py` | DeepSeek-V3 技术报告 §3.2.1 + Table 2 | DualPipe 双向流水线气泡 `(PP/2-1)(F+B-3W)` vs 1F1B `(PP-1)(F+B)`；列表调度器数值复现 1F1B；ASCII 甘特图 |
| `fp8.py` | 技术报告 §3.3 + 附录 B | E4M3 量化（饱和语义，max 448）；1x128 tile-wise 细粒度缩放；每 128 元素提升 CUDA Core FP32 累加；离群值矩阵上的误差对比 |
| `ep.py` | 技术报告 §3.2.2 | EP all-to-all 通信量（dispatch/combine 对称）；NVLink vs IB 带宽拆分；节点受限路由（M=4/8 节点）降低跨节点流量；负载不均因子（EPLB 的动机） |
| `mla.py` | 技术报告 §2.1.1；V3.2 报告 §2.1 | MLA 低秩 KV 压缩（V3 维度下 ~57×）；潜空间重建误差；lightning indexer 打分 + top-K 选择（DSA 伏笔） |
| `demo.py` | 端到端 | 5 个场景串成"一步训练的时间账" |

## 运行

```bash
pip install -e ".[dev]"
pytest tests/ -v
python -m deepseek_case_mini.demo
```

## 注意

- 所有带宽/时间数字是**量级示意**（uniform 假设的简化模型），用于讲清
  趋势与相对关系，不代表 DeepSeek 生产环境的实测值。
- 通信带宽默认值：H800 NVLink ≈ 400 GB/s/卡、IB 400 Gb/s ≈ 50 GB/s/卡。
