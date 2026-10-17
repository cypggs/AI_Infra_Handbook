# 8. 企业生产实践

分布式系统理论最终要落地到 AI 生产集群。本章把前面章节的抽象概念，映射到训练、推理、存储、编排四个真实场景中。

## 8.1 分布式训练中的集合通信

### 8.1.1 数据并行 vs 模型并行 vs 流水线并行

| 并行方式 | 切分对象 | 通信模式 | 适用场景 |
|---|---|---|---|
| 数据并行 | 数据 batch | all-reduce 梯度 | 模型可放入单卡显存 |
| 模型并行 / 张量并行 | 模型层内参数 | all-gather / reduce-scatter | 单卡放不下整个层 |
| 流水线并行 | 模型层间 | point-to-point | 超大模型，层间流水线 |
| 专家并行（MoE） | 专家路由 | all-to-all | Mixture-of-Experts 模型 |
| 上下文并行（CP） | 长序列维切分 | ring / striped attention 通信 | 百万 token 级长序列 |

### 8.1.2 通信拓扑与算法

- **Ring all-reduce**：把梯度拆成 N 份，沿环传递，通信量与节点数无关；
- **Tree all-reduce**：层次化聚合，降低延迟；
- **Hierarchical all-reduce**：跨机用 RDMA/NCCL，机内用 NVLink；
- **Reduce-scatter + all-gather**：常用于张量并行；
- **Scale-up 域内 all-to-all**：NVL72 这类单机柜 72 GPU 的 NVLink Switch 域让 MoE 专家并行、张量并行的 all-to-all 在机柜内完成，机间只做更粗粒度的数据并行——“机柜即一台机器”成为新的故障与调度单元；
- **在网计算**：NCCL 的 NVLS（NVLink SHARP）等把规约卸载到交换芯片，进一步压低 all-reduce 延迟；
- **RoCE vs InfiniBand**：万卡级 RoCE 部署已很常见，拥塞控制（DCQCN 及后续算法）与丢包敏感度是主要运维难点；Ultra Ethernet Consortium（UEC）2025 年发布 1.0 规范，专为 AI 集合通信优化以太网；scale-up 侧则有 UALink 1.0（2025-04）作为 NVLink 的开放对标。

### 8.1.3 容错与弹性

生产训练常遇到的故障：

- GPU 掉卡、Xid 错误；
- NCCL 超时；
- 节点 OOM；
- 网络抖动导致 straggler。

应对：

- **Checkpoint 频率**：平衡 IO 开销与恢复时间；
- **弹性训练**：PyTorch Elastic、Kubernetes Volcano/Kueue、Ray Train；
- **Health check**：NCCL watchdog、GPU 温度/ECC 监控；
- **重试与隔离**：失败节点暂时隔离，任务迁移到其他节点。

### 8.1.4 万卡级集群的容错工程（2024-2026 现状）

万卡以上的训练集群，**每小时都有节点出故障**。真实账单：Llama 3 405B 用 16,384 张 H100 训练，单 run 54 天发生 466 次任务中断，约 78% 与硬件有关（[The Llama 3 Herd of Models](https://arxiv.org/abs/2407.21783)）；xAI Colossus 从开工到 10 万卡 H100 上线仅用数月，随后又规划翻倍扩展。这带来一组新的工程范式：

1. **MTTR 取代 MTBF 成为核心指标**：不追求“少坏”，追求“坏了快恢复”。Google 的 Gemini（SOSP'24）把 checkpoint 驻留在集群空闲 CPU 内存中，配合少量重计算，把大模型训练的故障恢复从小时级压到分钟级，并已在 Google 生产环境长期使用。
2. **三级 checkpoint + 异步 DCP**：GPU/CPU 内存 → 本地 NVMe → 对象存储（见工作流程章 4.7），PyTorch DCP 后台异步写出，训练不停顿。
3. **局部回滚代替全任务重启**：Oobleck（SOSP'23）预生成多套流水线模板，部分节点失效时只重排受影响的 stage，其余计算保留。
4. **预测性故障隔离**：结合 Xid 错误码、ECC、温度遥测，在节点真正掉卡前摘除，把“恢复”提前为“规避”。
5. **Straggler 治理**：慢节点检测、动态摘重、热点机架规避；单节点慢 10% 就能拖垮整个 all-reduce。
6. **WAN / 异步训练**：DiLoCo / OpenDiLoCo 路线把同步梯度换成周期性伪梯度同步，容忍跨地域带宽与节点流失（见工作流程章 4.8），适合获取异构、易失的算力资源。

这一节与后续 KubeRay、GPU 调度、存储章节形成闭环：容错最终是由调度器补位速度、checkpoint 写入带宽、通信库超时策略三者共同决定的。

## 8.2 推理服务的多副本一致性

### 8.2.1 状态共享问题

多副本 LLM 推理面临：

- 是否共享 KV Cache？
- 如何保持模型版本一致？
- 长连接断开后如何恢复上下文？

常见方案：

| 方案 | 一致性 | 复杂度 | 适用 |
|---|---|---|---|
| 每个副本独立 KV Cache | 最终一致（请求固定副本） | 低 | 无状态负载均衡 |
| 分布式 KV Cache（如 vLLM 的 TP/PP） | 强一致 | 高 | 大模型单实例内并行 |
| 外部缓存（Redis） | 最终一致 | 中 | 会话状态、前缀缓存 |

### 8.2.2 路由与故障转移

- **Round-robin**：简单，但可能把长请求集中到同一副本；
- **Least loaded**：根据当前请求数或 token 生成速度路由；
- **Session sticky**：同一用户固定到同一副本，便于缓存命中；
- **Circuit breaker**：副本异常时快速摘除，防止拖垮整体。

### 8.2.3 PD 分离与前缀缓存（2025 年起的主流演进）

推理服务架构的主线是 **Prefill/Decode 分离（PD 分离）**：prefill 计算密集、decode 访存密集，拆成独立资源池后各自弹性伸缩（vLLM、NVIDIA Dynamo 等均已支持）。这引入新的分布式问题：

- 请求在 prefill / decode 池之间转发，KV Cache 需要跨进程、跨节点搬运（NIXL、Mooncake 一类高速传输层）；
- 前缀缓存（prefix cache）跨副本共享时，一致性退化为“最终一致 + 请求 sticky”——缓存 miss 只损失性能，不损失正确性；
- 会话迁移时以 token 序列为唯一事实来源，任何缓存副本都可以重建——这正是架构章“把状态收敛到单写者”思想的应用：**副本间不共享可变状态，共享的只读缓存允许随意复制**。

## 8.3 Kubernetes 控制面调优

etcd 是 K8s 的“单一事实来源”，它的健康决定整个集群健康。

### 8.3.1 etcd 部署建议

- 版本：2025 年后的稳定线是 3.6.x（Raft 拆分为独立模块 `go.etcd.io/raft/v3`，默认 `--snapshot-count` 从 100,000 降到 10,000，快照更频繁、追赶更快）；3.7 起新增 RangeStream 流式读（Kubernetes 1.37 以 `EtcdRangeStream` 特性暴露，避免大 list 打爆内存），并修复了 ReadIndex 过期读（见 [3.6 变更日志](https://github.com/etcd-io/etcd/blob/main/CHANGELOG/CHANGELOG-3.6.md)、[3.7 发布公告](https://etcd.io/blog/2026/announcing-etcd-3.7/)）；
- 节点数：3（容忍 1 故障）或 5（容忍 2 故障）；
- 跨可用区部署，避免 AZ 级故障；
- 使用 SSD，WAL 与数据目录分离；
- 限制单个 key/value 大小，避免大对象拖垮 Raft；
- 定期 defrag 与 snapshot。

### 8.3.2 apiserver 与 controller

- apiserver 是无状态的，可水平扩展；
- controller 用 leader election，同一时间只有一个 active；
- watch 机制让各组件实时感知状态变化；
- 大规模集群要调大 `--max-requests-inflight` 和 `--max-mutating-requests-inflight`。

## 8.4 对象存储与多 AZ 复制

AI 训练数据、checkpoint、模型 artifact 通常存放在对象存储。

### 8.4.1 一致性级别选择

| 场景 | 推荐一致性 | 原因 |
|---|---|---|
| checkpoint 元数据 | 强一致 | 恢复时必须读到最新索引 |
| 训练数据只读副本 | 最终一致 | 数据不变，复制延迟可接受 |
| 模型版本注册 | 强一致 | 避免读取到未完成的 artifact |
| 推理日志/指标 | 最终一致 | 可容忍秒级延迟 |

### 8.4.2 跨区域复制

- **主动-被动**：主区域写，其他区域异步复制，故障时手动切换；
- **主动-主动**：多区域同时写，需要冲突解决；
- **近线复制**：热数据就近读取，冷数据归档到低成本存储。

## 8.5 故障域与爆炸半径

### 8.5.1 分层故障域

```text
GPU → 节点 → 机柜 → 机架 → 可用区 → 区域
```

关键设计原则：

- 控制面副本跨 AZ；
- 训练 job 的 worker 尽量分散到不同机架；
- 存储副本跨 AZ，重要数据跨区域；
- 单点服务（如 scheduler）要有热备或 leader election。

### 8.5.2 爆炸半径控制

- **Namespace / 租户隔离**：一个租户的异常不影响其他租户；
- **资源配额与限流**：防止单个 job 占满网络或存储带宽；
- **熔断与降级**：推理服务某副本卡顿时，快速熔断并返回降级结果；
- **混沌工程**：定期注入故障，验证系统韧性。

## 8.6 一句话总结

**生产级 AI 基础设施的分布式系统实践，核心是把“共识、复制、分区、超时”落到实处：训练用 all-reduce 和 checkpoint 保证进度，推理用多副本和路由保证可用，K8s 用 etcd/Raft 保证状态一致，存储用多 AZ 复制保证耐久，最终目标是在任何故障域下控制爆炸半径。**
