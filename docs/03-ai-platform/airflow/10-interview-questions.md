# 10. 面试题

> 本章汇总 Airflow 相关的初、中、高级面试题，覆盖核心概念、架构、源码、生产实践与生态集成。

## 10.1 初级

### 1. 什么是 DAG？DAG 和 Task 的关系是什么？

**答案**：DAG（Directed Acyclic Graph）是有向无环图，描述一组 Task 及其依赖关系。Task 是 DAG 中的节点，代表一个工作单元。一个 DAG 包含多个 Task，Task 之间通过依赖边连接。

### 2. Airflow 中 Operator、Task、TaskInstance 的区别？

**答案**：

- **Operator** 是类，定义“怎么执行”（如 PythonOperator、BashOperator）。
- **Task** 是 Operator 在某个 DAG 中的实例。
- **TaskInstance** 是某个 Task 在某次 DAG Run 中的具体执行。

### 3. Airflow 的核心组件有哪些？（Airflow 3）

**答案**：Metadata Database、API Server（FastAPI，承载 REST API v2 + React UI + Execution API）、DAG Processor（必需）、Scheduler、Executor（调度器的配置属性）、Worker、Triggerer。Airflow 2 时代的 Webserver（Flask）已被 API Server 取代。

### 4. XCom 是什么？有什么使用限制？

**答案**：XCom 是任务间数据交换机制，默认存储在 Metadata Database（3.x 任务侧经 Execution API 读写）。限制：不适合传大对象；支持自定义 XCom backend（S3/GCS 等）。

### 5. 常见 Executor 有哪些？开发环境用哪个？

**答案**：SequentialExecutor（仅开发）、LocalExecutor（单机）、CeleryExecutor（多机）、KubernetesExecutor（K8s Pod 级隔离）、EdgeExecutor（Airflow 3，边缘/受限网络 worker 出站轮询）。开发环境用 SequentialExecutor 或 LocalExecutor；注意 Airflow 3 中 Celery/K8s/Edge Executor 都在 provider 包里。

## 10.2 中级

### 6. Scheduler 的主要职责是什么？

**答案**：Scheduler 负责：1）根据 schedule_interval 创建 DAG Run；2）检查 TaskInstance 的依赖、资源、并发；3）把满足条件的 TaskInstance 状态推进到 queued，并交给 Executor 执行。

### 7. 解释 Airflow 中 TaskInstance 的状态流转。

**答案**：典型流转：`none → scheduled → queued → running → success`。失败时可能 `failed → up_for_retry → queued`。Sensor 可能进入 `sensing`，Deferrable Operator 会进入 `deferred`。

### 8. Deferrable Operator 和传统 Sensor 的区别？

**答案**：传统 Sensor 占 worker slot 轮询；Deferrable Operator 第一次执行后进入 `deferred` 状态，释放 worker，由 Triggerer 异步监听事件，事件发生后唤醒 TaskInstance。

### 9. 如何选择 Executor？

**答案**：

- 单机中小规模：LocalExecutor。
- 多机传统扩展：CeleryExecutor。
- 云原生/强隔离/弹性：KubernetesExecutor。
- 混合：Airflow 2.10+ 多 Executor。

### 10. 生产环境 Metadata Database 为什么推荐 PostgreSQL？

**答案**：PostgreSQL 性能好、稳定性强、并发处理能力强、社区支持好，适合存储大量 TaskInstance、XCom、Log 等数据。

### 11. 如何实现任务幂等性？

**答案**：

- 输出按 execution_date 分区，避免覆盖。
- 写入前检查目标是否已存在。
- 使用 `IF NOT EXISTS`、upsert 等语义。
- 避免副作用（如重复发邮件）。

## 10.3 高级

### 12. DAG Processor 和 Scheduler 为什么要拆分？

**答案**：Airflow 2.3+ 把 DAG Processor 独立出来，避免 DAG 文件解析（可能耗时、可能失败）阻塞 Scheduler 的调度循环，提升调度稳定性和延迟可预测性。

### 13. 描述一次 TaskInstance 从创建到执行的完整调用链。

**答案**：

1. DAG Processor 解析 DAG 文件，序列化后写入 Metadata DB。
2. Scheduler 读取序列化 DAG，创建 DAG Run 和 TaskInstance。
3. Scheduler 检查依赖和资源，把 TaskInstance 状态改为 scheduled → queued。
4. Executor 接收任务，交给 Worker 执行。
5. Worker 执行 Operator.execute()，捕获日志，写 XCom。
6. Worker 把状态写回 Metadata DB。

### 14. KubernetesExecutor 的优缺点？

**答案**：优点：每个任务一个 Pod，资源隔离好，弹性扩缩，适合异构任务。缺点：Pod 启动有 overhead，不适合超短任务；需要 K8s 集群和镜像管理。

### 15. Airflow 3 的 Task Execution API 和 Task SDK 是什么？解决了什么问题？（AIP-72）

**答案**：Airflow 3.0 起，Task 不再直连 Metadata DB，而是通过 Task Execution API（运行在 API Server 内）上报状态、读写 XCom、发心跳。API 使用短期 JWT 认证，按任务发放。任务侧代码拆成独立包 `apache-airflow-sdk`（`from airflow.sdk import dag, task` 是稳定的编写契约），任务可以在 K8s Pod、CI Runner、边缘节点等任意环境运行。收益：数据库攻击面缩小、Scheduler 与执行环境解耦、执行环境只需轻量 SDK。

### 16. Edge Executor 的适用场景是什么？（AIP-69）

**答案**：Worker 只需安装 Task SDK + edge provider，通过出站 HTTPS 轮询中心 API 拉任务、上报结果，无需入站端口、无需 DB 连接串。适合 on-prem 机房、客户环境、跨云、数据主权受限网络。

### 17. 如何设计一个高可用的 Airflow 3 生产集群？

**答案**：

- PostgreSQL 主从 + 自动故障转移。
- API Server、Scheduler、DAG Processor、Triggerer 多副本。
- Executor 按需选择 Celery/Kubernetes/Edge。
- 远程日志存储（S3/GCS）。
- Secrets Backend 管理凭据；生产用 FAB Auth Manager（OAuth/LDAP）+ API token。
- Prometheus/Grafana 监控（3.2+ 结构化日志、OTel Histogram、Deadline Alerts）。
- 定期备份 DB，演练恢复。

### 18. 如何处理 DAG 之间的依赖？

**答案**：

- **Asset / Asset 分区调度（3.x 首选）**：上游 DAG 更新资产（或分区），下游自动触发。
- **TriggerDagRunOperator**：一个 DAG 显式触发另一个 DAG。
- **ExternalTaskSensor**（Deferrable）：等待外部 DAG 的 TaskInstance 完成。
- **共享状态**：通过数据库、对象存储、消息队列传递信号。

### 19. Airflow 的 Provider 架构有什么好处？Airflow 3 有什么变化？

**答案**：Provider 包让 Operator/Hook/Sensor 独立于核心发版，减小核心体积，第三方可发布自己的 provider。Airflow 3 进一步拆分：BashOperator/PythonOperator 移入 `providers-standard`，Celery/Kubernetes Executor 和 FAB 认证管理器也都 provider 化。

### 20. Airflow 2 → 3 迁移有哪些关键步骤和坑？

**答案**：

- 路径：先升到 2.11（最后一个 2.x，2.x 已于 2026-04-22 EOL），再升 3.1+（3.0 已 EOL）。
- 用 ruff `AIR301`（必须）/ `AIR302`（建议）自动改写导入与废弃参数。
- 人工核对语义变化：`data_interval_*` 默认值变化、`execution_date` → `logical_date`、`sla=` 被移除（改 Deadline Alerts，AIP-86）、SubDAG/pickling 移除。
- `airflow config update` + `airflow db migrate`；新增 `dag-processor`、`api-server` 组件。

### 24. Airflow 3.4（beta 2026-10）有哪些值得关注的演进？

**答案**：

- **Task Loops（AIP-111）**：装饰器任务组 `.loop()` 按运行期次数迭代，支持 `until` 条件（do-while）与 `max_iterations`；区别于 Dynamic Task Mapping 的无状态并行展开。
- **Dag Importer（AIP-85，实验性）**：可插拔的非 Python DAG 导入框架——原生 YAML DAG 格式与 TypeScript/Go/Java SDK 编写的 DAG 可以像 Python DAG 一样被 DAG Processor 解析调度，意味着 DAG 定义不再绑定 Python。
- **行为变化**：单资产/或表达式默认每个资产事件一个 DAG Run（`batch_asset_events` 控制）；`Dataset` 旧别名移除；psycopg3 成为元数据库默认驱动；新 XCom 行写入 `xcom_v2` 表（升级含表迁移，MySQL 降级不可回滚 DDL）。

## 10.4 场景题

### 21. 一个训练 DAG 每天凌晨 2 点运行，但最近经常因为上游数据延迟而失败，你会怎么优化？

**答案**：

1. 用 Asset/Asset 分区调度或 Deferrable 的 ExternalTaskSensor 替代固定时间调度。
2. 增加上游数据到达的监控和 Deadline Alert（AIP-86）提前发现延迟。
3. 配置合理的 retries 和 retry_delay（3.3 可用可插拔重试策略）。
4. 考虑把 DAG 拆成“数据就绪检查 → 训练”两个 DAG。

### 22. Airflow 集群在大促期间任务排队严重，如何快速扩容？

**答案**：

- KubernetesExecutor：HPA / Cluster Autoscaler 自动扩容 Worker Pod。
- CeleryExecutor：增加 Celery Worker 副本。
- Edge 场景：直接横向增加 Edge Worker 节点。
- 检查是否有任务占满 Pool，临时增加 pool_slots。
- 优化长任务，拆分或提升资源；提前预热镜像。

### 23. 团队想用 Airflow 编排 LLM Agent，你的建议？

**答案**：Airflow 适合编排 agent 周边的批处理工作：训练/评测数据生产、批量推理、结果归档、人工审批门禁（HITL）；不适合做 agent 运行时（高频交互决策）。Agent 本体放专用 Agent Runtime，Airflow 通过 API/operator 触发并接收结果。

## 本章小结

- 初级题聚焦概念：DAG、Operator、Task、TaskInstance、Executor、XCom。
- 中级题聚焦机制：状态流转、Scheduler、Deferrable Operator、Executor 选型。
- 高级题聚焦架构与源码：Airflow 3 的 Task SDK/Execution API/JWT、Edge Executor、2→3 迁移、3.4 新范式（Task Loops/Dag Importer）、高可用设计。
- 场景题考察综合落地能力（数据驱动调度、扩容、AI 工作流边界）。

**参考来源**

- [Apache Airflow — Core Concepts](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/index.html)
- [Apache Airflow — FAQ](https://airflow.apache.org/docs/apache-airflow/stable/faq.html)
- [Apache Airflow — Upgrading to Airflow 3](https://airflow.apache.org/docs/apache-airflow/stable/installation/upgrading_to_airflow3.html)
- 本手册前 9 章内容
