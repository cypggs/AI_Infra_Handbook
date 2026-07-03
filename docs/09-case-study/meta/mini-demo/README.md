# meta-mini — 同步训练可靠性模拟器

一个**确定性、纯 CPU、无需任何 LLM key** 的迷你示例，复现 Meta 超大规模同步训练中最具辨识度的工程：**故障经济学、checkpoint 权衡、与 Silent Data Corruption（SDC）治理**。

它把 Meta 公开的可靠性数字（>66% 中断来自硬件、SDC 约每 1000 设备 1 个、有效训练时间 >95%、中断率下降约 50 倍）变成可调参、可测试的模拟器。

## 安装

```bash
cd docs/09-case-study/meta/mini-demo
pip install -e ".[dev]"
```

## 运行对比实验

```bash
python -m meta_mini.demo
```

输出三组配置的对比表：**理想（无故障）**、**朴素（大 checkpoint 间隔 / 无 SDC 验证）**、**优化（小间隔 / 频繁验证）**，展示有效训练时间、回滚浪费、checkpoint/验证开销、中断次数、SDC 检出与焊死计数。

## 测试

```bash
pytest tests/ -q
```

## 模块

| 文件 | 作用 |
|---|---|
| `model.py` | `JobConfig` / `SimResult` 数据结构 |
| `failures.py` | 每 GPU 每小时故障率 → 每步集群风险（"集群越大越脆弱"的数学） |
| `checkpoint.py` | 固定间隔同步 checkpoint 边界判定 |
| `sdc.py` | SDC 周期验证边界判定（模拟 Fleetscanner/Ripple/Hardware Sentinel 检测延迟） |
| `simulator.py` | 主模拟循环：故障回滚 + 验证/checkpoint 赛跑 |
| `metrics.py` | 有效训练时间 / 回滚浪费 / 开销 指标 |
| `demo.py` | 三配置对比入口 |

## 核心机制

1. **每步集群风险** `1 - (1 - p_gpu)^n_gpus`：一个 N-GPU 同步任务里任一 GPU 故障即停顿，N 在指数上 → 集群越大越脆弱。
2. **故障回滚**：硬件故障 → 回滚到最近 checkpoint + auto-restart，丢失"自上次 checkpoint 以来的工作"。
3. **SDC 验证赛跑**：SDC 静默腐蚀状态，只能靠周期验证捕获。若验证先于 checkpoint（`validation_interval ≤ ckpt_interval`），SDC 总能在被"焊死"进 checkpoint 前捕获；否则腐蚀被持久化，工作作废。

## 与生产系统的差异

本模拟器是教学抽象，刻意省略了 Meta 生产系统的诸多细节（三层数字检测、NaN/梯度方差两种失败模式、tri-variate training、拓扑感知调度、straggler、异构硅等）。详见 `docs/09-case-study/meta/07-mini-demo.md` 的"与生产系统的差异"表与"扩展练习"。

## 许可

CC-BY-SA-4.0（随本手册整体许可）。
