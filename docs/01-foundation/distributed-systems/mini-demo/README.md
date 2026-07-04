# 分布式系统基础 mini-demo

本包是《AI Infra Handbook》中“分布式系统基础”主题的 CPU 可运行 mini-demo，用纯 Python 模拟了分布式系统中的核心概念：

- Lamport 逻辑时钟
- Vector 时钟与并发冲突检测
- Raft 共识（Leader 选举、日志复制、故障恢复）
- 两阶段提交（2PC）
- Quorum N/W/R 读写一致性

所有模拟都是事件驱动、可步进的，并使用 `FakeClock` 代替真实 `time.sleep`，因此测试完全确定且可在 CPU 上快速运行。

## 安装

```bash
cd docs/01-foundation/distributed-systems/mini-demo
pip install -e ".[dev]"
```

## 运行测试

```bash
pytest tests/ -v
```

## 运行演示

```bash
python -m distributed_systems_mini.demo
```

演示会依次输出以下场景的结果：

1. Lamport 逻辑时钟因果排序
2. Vector 时钟并发冲突与合并
3. Raft 三节点 Leader 选举
4. Raft 日志复制与提交
5. Raft Leader 故障与重新选举（保证已提交日志不丢失）
6. 2PC 正常提交与投票否决回滚
7. Quorum 读写一致性、脑裂写入被拒绝、过期读取检测

## 包结构

```
distributed_systems_mini/
├── __init__.py
├── network.py          # FakeClock + InProcessNetwork
├── logical_clock.py    # Lamport 时钟
├── vector_clock.py     # Vector 时钟
├── raft.py             # Raft 节点
├── two_phase_commit.py # 2PC 协调者与参与者
├── quorum_store.py     # N/W/R Quorum KV
└── demo.py             # 演示脚本
```

## 依赖

- Python >= 3.10
- pytest（仅用于测试）
