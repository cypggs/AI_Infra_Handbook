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

### 3. Airflow 的核心组件有哪些？

**答案**：Webserver/UI、Scheduler、Executor、Worker、Metadata Database、Triggerer、DAG Processor。

### 4. XCom 是什么？有什么使用限制？

**答案**：XCom 是任务间数据交换机制，默认存储在 Metadata Database。限制：不适合传大对象；Airflow 2.5+ 支持自定义 XCom backend（S3/GCS）。

### 5. 常见 Executor 有哪些？开发环境用哪个？

**答案**：SequentialExecutor、LocalExecutor、CeleryExecutor、KubernetesExecutor、DaskExecutor。开发环境常用 SequentialExecutor 或 LocalExecutor。

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

### 15. Airflow 3 的 Execution API 和 JWT 有什么意义？

**答案**：Airflow 3 中 Task 不再直接访问 Metadata DB，而是通过 Execution API 与 Scheduler 通信。Execution API 使用 JWT 认证，降低数据库暴露面，提升安全性，同时解耦 Scheduler 与 Worker。

### 16. 如何设计一个高可用的 Airflow 生产集群？

**答案**：

- PostgreSQL 主从 + 自动故障转移。
- 多 Scheduler、多 Webserver、多 Triggerer。
- Executor 按需选择 Celery/Kubernetes。
- 远程日志存储（S3/GCS）。
- Secrets Backend 管理凭据。
- Prometheus/Grafana 监控，配置告警。
- 定期备份 DB，演练恢复。

### 17. 如何处理 DAG 之间的依赖？

**答案**：

- **Dataset/Asset 调度**：上游 DAG 更新 dataset，下游 DAG 自动触发。
- **TriggerDagRunOperator**：一个 DAG 显式触发另一个 DAG。
- **ExternalTaskSensor**：等待外部 DAG 的 TaskInstance 完成。
- **共享状态**：通过数据库、对象存储、消息队列传递信号。

### 18. Airflow 的 Provider 架构有什么好处？

**答案**：Airflow 2.0+ 把 Operator/Hook/Sensor 拆成独立 provider 包，减少核心包体积，各 provider 独立发版，第三方可以发布自己的 provider，生态更轻量、可扩展。

## 10.4 场景题

### 19. 一个训练 DAG 每天凌晨 2 点运行，但最近经常因为上游数据延迟而失败，你会怎么优化？

**答案**：

1. 用 Deferrable 的 ExternalTaskSensor 或 Dataset 调度替代固定时间调度。
2. 增加上游数据到达的监控和告警。
3. 配置合理的 retries 和 retry_delay。
4. 评估是否用 SLA 告警提前发现延迟。
5. 考虑把 DAG 拆成“数据就绪检查 → 训练”两个 DAG。

### 20. Airflow 集群在大促期间任务排队严重，如何快速扩容？

**答案**：

- KubernetesExecutor：HPA / Cluster Autoscaler 自动扩容 Worker Pod。
- CeleryExecutor：增加 Celery Worker 副本。
- 检查是否有任务占满 Pool，临时增加 pool_slots。
- 优化长任务，拆分或提升资源。
- 提前预热镜像，减少 Pod 启动时间。

## 本章小结

- 初级题聚焦概念：DAG、Operator、Task、TaskInstance、Executor、XCom。
- 中级题聚焦机制：状态流转、Scheduler、Deferrable Operator、Executor 选型。
- 高级题聚焦架构与源码：DAG Processor 拆分、调用链、K8s Executor、Airflow 3 Execution API、高可用设计。
- 场景题考察综合落地能力。

**参考来源**

- [Apache Airflow — Core Concepts](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/index.html)
- [Apache Airflow — FAQ](https://airflow.apache.org/docs/apache-airflow/stable/faq.html)
- 本手册前 9 章内容
