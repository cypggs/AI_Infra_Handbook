# MLflow Mini Demo

一个使用真实 `mlflow` Python SDK 的本地 Mini Demo，不启动 Tracking Server，也不依赖外部存储。

## 运行

```bash
cd docs/03-ai-platform/mlflow/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m mlflow_mini.demo
```

## 内容

- 使用 iris 数据集训练 `LogisticRegression`
- 记录参数、指标、模型 artifact 和签名
- 使用 SQLite 作为 backend store
- 使用本地临时目录作为 artifact store
- 注册模型、设置 alias、加载并预测
- 测试结束后自动清理临时目录

## 与生产的差异

真实生产环境应使用 PostgreSQL backend、S3/GCS/Azure artifact store、MLflow Tracking Server 多副本，并配置认证。
