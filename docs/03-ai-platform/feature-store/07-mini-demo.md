# 7. Mini Demo：Point-in-Time Join、在线 TTL 与偏斜检测

> 一句话理解：这个 Demo 用**纯 Python（numpy + pytest）从零实现特征平台最核心的三个机制**——带 `event_timestamp` 的离线特征表与 point-in-time join、只存最新快照且带 TTL 的在线 KV 存储、训练/服务偏斜的配对检测与 PSI 漂移度量——全部逻辑确定可测，50 个 pytest 用例全绿。

## 7.1 目标与约束

- **零外部服务**：不启动 Redis/Kafka/Spark，不需要网络。
- **CPU 可运行**：仅依赖 numpy；时间用注入的假时钟（fake clock）控制，结果完全确定。
- **语义对齐生产**：PIT join 取“event_timestamp ≤ 查询时刻的最新值”；在线存储 last-write-wins 且带时间戳守卫；TTL 过期返回空；偏斜检测 = 配对比对 + PSI。

## 7.2 目录结构

```
mini-demo/
├── README.md
├── pyproject.toml
├── feature_store_mini/
│   ├── __init__.py
│   ├── entity.py      # 实体/主键模型
│   ├── offline.py     # 离线特征表 + PIT join
│   ├── online.py      # 在线 KV（最新快照 + TTL + 假时钟）
│   ├── skew.py        # 偏斜检测（配对比对 / 分布统计 / PSI）
│   └── demo.py        # 6 个端到端场景
└── tests/
    ├── test_entity.py   # 7 用例
    ├── test_offline.py  # 17 用例
    ├── test_online.py   # 12 用例
    ├── test_skew.py     # 11 用例
    └── test_demo.py     # 6 用例
```

## 7.3 运行方式

```bash
cd docs/03-ai-platform/feature-store/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m feature_store_mini.demo
```

实测输出（2026-10，完全确定，无随机性）：

```
Demo result: {'offline_rows': 55, 'pit_training_rows': 5, 'pit_no_leakage': True,
'online_synced': 5, 'online_ttl_works': True, 'aligned_skewed': False,
'buggy_skew': {'skewed': True, 'mismatched': 5, 'psi': 26.2849,
               'offline_mean': 181.0, 'serving_mean': 77.0},
'late_event_delta': 999.0, 'retro_corrected': True}
```

`pytest tests/ -v` 实测：**50 passed**。

## 7.4 六个端到端场景

### 场景 1：事件流 → 离线特征表

10 天 × 5 个用户的消费事件流（固定伪随机序列），特征管道为每个用户每天计算 `spend_sum_7d`（近 7 天消费总额）写入离线表：

```python
def scenario_events_to_offline(events):
    user = Entity("user", "user_id")
    table = OfflineFeatureTable("user_spend_7d", user, ["spend_sum_7d"])
    for e in events:
        ts = e["event_timestamp"]
        table.ingest(e["user_id"], ts,
                     {"spend_sum_7d": offline_window_spend(events, e["user_id"], ts)})
    return table
```

### 场景 2：Point-in-Time 训练集（无泄漏验证）

第 10 天对每个用户打标签，PIT join 只取标签时刻之前的特征值；测试断言：训练集中每个特征值与“仅用标签时刻之前的事件重算”的批计算完全一致（`no_leakage=True`）。

### 场景 3：物化到在线存储 + TTL

`sync_from_offline` 把每个用户最新快照灌入在线库（TTL=3 天，假时钟）：

- 同步后 1 天：值可读；
- 4 天后：TTL 过期，`get` 返回 `None`（宁可置空，不服务陈旧值）。

### 场景 4：偏斜检测（两路对齐）

对同一实体同时取“离线从原始事件重算”与“在线快照”，逐样本配对比对（`abs_tol=1e-9`）——结果 5/5 一致，`skewed=False`。

### 场景 5：偏斜检测（窗口 bug 注入）

模拟在线服务误用 3 天窗口（训练用 7 天）：配对比对 5/5 全部失配，`PSI=26.28`（远大于 0.25 显著漂移阈值），分布均值 181 vs 77——偏斜被确定性检出。

### 场景 6：迟到事件与回填

第 5 天的一笔 999 元消费在第 10 天才到达（append-only 离线表）。回填管道重算第 5-9 天的所有窗口行（同时间戳、更新版本），查询第 6 天状态得到 retro-correct 后的值，delta 恰为 999。

```mermaid
sequenceDiagram
    participant E as 迟到事件<br/>(day5, +999元)
    participant OFF as 离线表
    E->>OFF: ingest day5 + 重算 day5..9 窗口行
    Note over OFF: append-only:<br/>同时间戳新版本覆盖旧值语义
    OFF->>OFF: as_of(day6) → 含 999 的新版本
```

## 7.5 核心语义与测试对照

| 语义 | 代码位置 | 代表测试 |
|---|---|---|
| PIT join 不取未来值 | `offline.as_of` / `point_in_time_join` | `test_no_future_leakage`、`test_as_of_picks_latest_not_future` |
| 乱序摄入自动排序 | `offline.ingest`（bisect） | `test_unsorted_ingestion_stays_sorted` |
| 同时间戳最新版本胜 | seq 单调递增 | `test_tie_timestamp_latest_insert_wins` |
| max_age 过期置空 | `as_of(max_age=)` | `test_max_age_filters_stale_rows` |
| 在线快照防乱序覆盖 | `online.set` 时间戳守卫 | `test_out_of_order_write_ignored` |
| TTL 过期返回空 | `online.get` | `test_ttl_expiry` |
| 配对偏斜检测 | `skew.detect_skew` | `test_detect_skew_window_bug` |
| PSI 漂移度量 | `skew.psi` | `test_psi_shifted_sample_is_elevated` |

## 7.6 与真实生产的差异

| 方面 | Mini Demo | 真实生产 |
|---|---|---|
| 离线存储 | 内存 list + 二分查找 | BigQuery/Snowflake/Spark + 列式扫描下推 |
| 在线存储 | dict | Redis/DynamoDB/RonDB（分布式、持久化） |
| 特征计算 | 单进程窗口函数 | Spark/Flink/RIFT 批流引擎 |
| 时钟 | 注入假时钟 | wall clock + NTP，迟到事件常见 |
| 规模 | 5 用户 × 10 天 | 十亿级实体、十万级 QPS |

## 本章小结

- 50 个确定性 pytest 用例覆盖实体/PIT join/在线 TTL/偏斜 PSI 四大模块。
- 6 个场景串起“事件 → 训练集 → 在线服务 → 监控”完整链路。
- 所有时间语义（event_timestamp、as-of、TTL、回填）与生产系统一一对应。

**参考来源**

- 本 Demo 源码：`docs/03-ai-platform/feature-store/mini-demo/`
- [Feast Point-in-time join 语义](https://docs.feast.dev/)
- [PSI（Population Stability Index）通用阈值约定（0.1 / 0.25）](https://www.databricks.com/blog/what-feature-store-complete-guide-ml-feature-engineering)
