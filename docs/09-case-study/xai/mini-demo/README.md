# xAI 案例 Mini Demo：超集群建设核心权衡模拟

纯 Python + numpy，CPU 可运行、完全确定性，无外部 LLM 依赖。配套
《xAI 案例研究》主题的 [07-mini-demo](../07-mini-demo.md) 章节。

## 模块

| 模块 | 模拟的权衡 |
|---|---|
| `power.py` | 供电容量规划：电网容量 vs 燃气轮机补充 vs 训练功率曲线（MW 缺口时间线） |
| `network.py` | 单一大集群 vs 多园区拓扑的 AllReduce 通信模型（RoCE vs IB 效率假设） |
| `build.py` | 集群建设排程：并行工作流 + 关键路径分析（复现"122 天"式压缩） |
| `cooling.py` | 风冷 vs 液冷的机柜功率密度模型（kW/rack 上限） |
| `demo.py` | 5 个端到端场景 |

## 运行

```bash
pip install -e ".[dev]"
pytest tests/ -v
python -m xai_case_mini.demo
```

## 口径说明

所有数字为一阶教学模型（刻意保留的简化见各模块 docstring）。
案例事实（122 天、95% 吞吐、1M GPU 规划等）的出处以
《xAI 案例研究》章节正文为准；本 demo 不追求复刻精确工程数字。
