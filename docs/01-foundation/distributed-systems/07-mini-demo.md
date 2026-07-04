# 7. 工程实践：分布式系统机制模拟器

本章配套的 Mini Demo 是一个纯 Python、CPU 可运行的分布式系统机制模拟器。它用**事件驱动 / 步进模拟 + 假时钟（FakeClock）**复现了分布式系统中最核心的几组概念：逻辑时钟、向量时钟、Raft 共识、两阶段提交、Quorum 读写。

## 7.1 目录结构

```text
docs/01-foundation/distributed-systems/mini-demo/
├── README.md
├── pyproject.toml
├── distributed_systems_mini/
│   ├── __init__.py
│   ├── network.py          # 进程内消息网络：延迟、丢包、分区
│   ├── logical_clock.py    # Lamport 逻辑时钟
│   ├── vector_clock.py     # 向量时钟与 happens-before
│   ├── raft.py             # Raft 节点：选主、日志复制、提交
│   ├── two_phase_commit.py # 2PC 协调者与参与者
│   ├── quorum_store.py     # Quorum KV：N/W/R 版本控制
│   └── demo.py             # 入口脚本
└── tests/
    └── test_all.py
```

## 7.2 运行方式

```bash
cd docs/01-foundation/distributed-systems/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m distributed_systems_mini.demo
```

## 7.3 核心设计

### 7.3.1 FakeClock + 事件驱动

为了避免真实 `time.sleep` 导致测试不稳定，所有 timeout（Raft 选举、心跳、2PC 等待）都依赖一个可手动推进的 `FakeClock`。测试代码可以精确控制“过了多久”，从而确定性验证状态机行为。

### 7.3.2 InProcessNetwork

```python
class InProcessNetwork:
    def send(self, src, dst, payload): ...
    def broadcast(self, src, payload): ...
    def partition(self, group_a, group_b): ...
    def drop_messages(self, probability): ...
```

- 所有节点注册一个消息处理函数；
- `send` 把消息放入按 `dst` 索引的队列，可选择延迟投递；
- `partition` 让两组节点之间所有消息被丢弃，模拟网络分区。

## 7.4 模拟场景

### 场景 1：Lamport 逻辑时钟

三个节点 `a`、`b`、`c` 互相发送消息。展示：

- 本地事件让时钟自增；
- 发送消息携带当前时间戳；
- 接收消息时把本地时钟更新为 `max(local, received) + 1`；
- 可以判断 `happens-before`，但无法区分并发事件。

### 场景 2：向量时钟冲突检测

两个节点并发更新同一个 key：

- `node1` 写 `x=1`，向量时钟 `(1, 0)`；
- `node2` 写 `x=2`，向量时钟 `(0, 1)`；
- 两者比较结果为 `concurrent`，需要 merge；
- merge 后得到 `(1, 1)`，合并值。

### 场景 3：Raft 领导者选举与日志复制

三节点 Raft 集群：

1. 所有节点都是 Follower；
2. 选举超时后某个节点变成 Candidate；
3. 赢得多数选票后成为 Leader；
4. Leader 收到客户端提案 `set x=42`；
5. Leader 追加日志并复制到 Follower；
6. 收到多数确认后提交，commit index 推进。

### 场景 4：Raft 故障恢复

1. Leader 宕机（模拟网络分区隔离 leader）；
2. 剩余两个节点选举超时后选出新 Leader；
3. 新 Leader 保留已提交日志；
4. 旧 Leader 重新加入后，发现更高 term，退为 Follower；
5. 日志冲突通过 `nextIndex` 回退解决。

### 场景 5：两阶段提交

- **成功路径**：Coordinator 发起 prepare，所有 Cohort 投 yes，Coordinator 发送 commit，所有 Cohort 提交。
- **中止路径**：某个 Cohort 投 no，Coordinator 发送 abort，所有参与者回滚。
- **超时路径**：Cohort 不响应，Coordinator 等待超时后 abort。

### 场景 6：Quorum 读写

N=3、W=2、R=2 的 Quorum KV：

- 正常写入需要至少 2 个副本确认；
- 正常读取需要读 2 个副本并取最新版本；
- 分区后，少数派分区无法达成 W，写入被拒绝；
- 如果 R 个副本中最新版本落后，返回 stale read 提示。

## 7.5 关键代码片段

### LamportClock

```python
class LamportClock:
    def __init__(self):
        self.time = 0

    def tick(self):
        self.time += 1
        return self.time

    def send(self):
        self.time += 1
        return self.time

    def receive(self, ts: int):
        self.time = max(self.time, ts) + 1
        return self.time
```

### VectorClock.compare

```python
def compare(self, other: "VectorClock") -> str:
    dominates = False
    dominated = False
    keys = set(self.clock) | set(other.clock)
    for k in keys:
        a = self.clock.get(k, 0)
        b = other.clock.get(k, 0)
        if a > b:
            dominates = True
        elif b > a:
            dominated = True
    if dominates and dominated:
        return "concurrent"
    if dominates:
        return "after"
    if dominated:
        return "before"
    return "equal"
```

### Raft 提交规则

```python
# 简化版：leader 维护每个 follower 的 match_index
# 当某个 index 被半数以上节点复制，且当前 term 一致，则标记为 committed
if replicated_count >= quorum:
    self.commit_index = max(self.commit_index, index)
```

## 7.6 与真实系统的差异

| 维度 | Mini Demo | 真实系统（etcd / Ray / Dynamo） |
|---|---|---|
| 网络 | 进程内队列 | TCP/RDMA/gRPC，真实延迟和丢包 |
| 持久化 | 内存 | WAL / SSTable / 分布式存储 |
| 时钟 | FakeClock | NTP / PTP / TrueTime |
| 规模 | 3 节点 | 数千节点、数百万请求 |
| 故障模型 | crash-stop / 分区 | crash-recovery、Byzantine、硬件故障 |
| 优化 | 无 | snapshot、batch、pipeline、lease |

## 7.7 测试结果示例

```text
tests/test_all.py::test_lamport_monotonic_and_causal_order PASSED
tests/test_all.py::test_vector_clock_concurrent_conflict PASSED
tests/test_all.py::test_vector_clock_merge_commutative_and_idempotent PASSED
tests/test_all.py::test_raft_leader_election_in_three_node_cluster PASSED
tests/test_all.py::test_raft_log_replication_and_commit PASSED
tests/test_all.py::test_raft_leader_failure_triggers_reelection PASSED
tests/test_all.py::test_raft_committed_entry_survives_minority_failure PASSED
tests/test_all.py::test_two_phase_commit_happy_path PASSED
tests/test_all.py::test_two_phase_commit_aborts_on_no_vote PASSED
tests/test_all.py::test_two_phase_commit_blocks_on_cohort_timeout PASSED
tests/test_all.py::test_quorum_write_then_read_consistent PASSED
tests/test_all.py::test_quorum_split_brain_write_rejected PASSED
tests/test_all.py::test_quorum_stale_read_detected PASSED
tests/test_all.py::test_demo_runs_without_exception PASSED
```

## 7.8 一句话总结

**这个 Mini Demo 不是生产级实现，而是一面“显微镜”：它把分布式系统中最抽象的概念（因果序、共识、事务、quorum）变成可步进、可测试、可观察的代码；跑一遍，你会发现 Raft 的选举超时和 2PC 的 prepare 并没有魔法，它们只是状态机加消息传递。**
