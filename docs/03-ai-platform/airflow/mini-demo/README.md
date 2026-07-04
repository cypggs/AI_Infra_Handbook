# Airflow Mini Demo

一个纯 Python、CPU 可运行、无需外部依赖的 Airflow 核心机制模拟。

## 运行

```bash
cd docs/03-ai-platform/airflow/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m airflow_mini.demo
```

## 覆盖机制

- DAG 定义与依赖表达
- DAG 解析与拓扑排序
- Scheduler 创建 DAG Run / TaskInstance
- Executor 按依赖顺序执行
- TaskInstance 状态机（none → scheduled → queued → running → success/failed/deferred）
- XCom 任务间数据传递
- Deferrable Operator + Triggerer 异步唤醒

## 与真实 Airflow 的差异

本 Demo 用于教学，不替代真实 Airflow。真实 Airflow 使用 PostgreSQL/MySQL Metadata DB、独立 Scheduler/Worker/Webserver 进程、真实 Executor（Local/Celery/Kubernetes）等。
