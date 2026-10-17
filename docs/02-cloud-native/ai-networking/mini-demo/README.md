# ai_networking_mini —— AI 集群网络教学模拟器

纯 Python（仅依赖 numpy + pytest）的 AI 集群网络概念模拟器：没有真实 GPU、
交换机和网卡，但保留了 scale-up/scale-out fabric 设计中的全部关键语义。

## 快速开始

```bash
cd docs/02-cloud-native/ai-networking/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m ai_networking_mini.demo
```

## 模块与真实机制对照

| 模块 | 模拟的真实机制 |
|---|---|
| `topology.py` | Leaf-Spine / k-ary fat-tree / rail-optimized 拓扑生成；BFS 跳数；二分带宽与收敛比；rail-only 省交换机测算 |
| `traffic.py` | TP all-reduce / DP 梯度同步 / EP all-to-all / PP 点对点的大小与频率模型；流量矩阵与热点因子（incast 集中度） |
| `congestion.py` | incast 扇入完成时间与队列峰值；ECN 分段线性标记概率；简化 DCQCN 速率轨迹；PFC 缓冲区依赖图死锁检测 |
| `collective.py` | ring/tree all-reduce 与 all-to-all 的步数、数据量、α-β 时延模型；跨 fabric 对比；Amdahl 加速比 |

## 六个端到端场景（`python -m ai_networking_mini.demo`）

1. fat-tree 拓扑生成与二分带宽（k=8）
2. rail-optimized vs leaf-spine 的交换机数量与跳数对比
3. 一次训练 step 的 TP/DP/EP/PP 流量矩阵与热点因子
4. incast 队列冲击 + ECN/DCQCN 速率收敛
5. PFC 缓冲区依赖死锁检测
6. ring vs tree all-reduce、跨 fabric 对比与 Amdahl 定律

所有计算都是确定性闭式公式，测试不依赖随机数与外部环境。
