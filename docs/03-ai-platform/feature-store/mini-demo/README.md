# Feature Store Mini Demo

一个纯 Python、CPU 可运行的特征平台最小实现，演示特征基础设施最核心的三件事：

1. **Point-in-time join**：用 `event_timestamp` 构建无泄漏训练集
2. **在线/离线分离**：离线存全量历史，在线存最新快照并支持 TTL
3. **训练/服务偏斜检测**：同一条逻辑特征的两条计算路径逐样本对比 + PSI

## 运行

```bash
cd docs/03-ai-platform/feature-store/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m feature_store_mini.demo
```

## 目录结构

```
mini-demo/
├── README.md
├── pyproject.toml
├── feature_store_mini/
│   ├── __init__.py
│   ├── entity.py      # 实体/主键模型（user/item）
│   ├── offline.py     # 离线特征表 + point-in-time join
│   ├── online.py      # 在线 KV 存储（最新快照 + TTL + 假时钟）
│   ├── skew.py        # 偏斜检测（配对对比 / 分布统计 / PSI）
│   └── demo.py        # 端到端场景入口
└── tests/
    ├── test_entity.py
    ├── test_offline.py
    ├── test_online.py
    ├── test_skew.py
    └── test_demo.py
```

## 演示场景（demo.py）

| 场景 | 说明 |
|---|---|
| 事件流 → 离线表 | 10 天 × 5 用户的消费事件，计算 `spend_sum_7d` 窗口聚合写入离线表 |
| PIT 训练集 | 第 10 天打标签，特征只取标签时刻之前的数据（无泄漏） |
| 在线服务 + TTL | 快照物化到在线存储；1 天内可读、4 天后 TTL 过期返回空 |
| 偏斜检测（对齐） | 离线重算 vs 在线快照，逐样本一致 → 无偏斜 |
| 偏斜检测（窗口 bug） | 在线误用 3 天窗口，配对对比 + PSI 检出偏斜 |
| 迟到事件回填 | 迟到数据 retro-correct 离线历史（append-only） |

## 与生产的差异

真实生产环境应使用列式离线存储（BigQuery/Snowflake/Spark/Delta Lake）、KV 在线存储
（Redis/DynamoDB/RonDB）、流式计算（Flink/Kafka Streams）与真实时钟，并处理高并发读写、
schema 演进与监控告警。本 Demo 仅用于理解核心语义。
