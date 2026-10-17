# 9. 最佳实践：参数签名、模型治理与成本效率

> 一句话理解：MLflow 的“最佳实践”不是把功能都用上，而是 **用最小必要信息让每次 Run 和每个 Model Version 都可解释、可复现、可回滚**。

## 9.1 实验管理

### 实验命名规范

```text
{team}/{project}/{task}
```

示例：`fraud/risk-score/v2`、`nlp/translation/exp01`。

- 避免所有实验都叫 `Default`。
- 废弃实验及时归档（删除或改 tag `status=archived`）。

### Run 命名规范

```python
mlflow.start_run(run_name=f"lr_{learning_rate}_bs_{batch_size}")
```

- 在 run name 里体现关键超参，便于快速识别。
- 或者使用自动生成的 UUID，关键参数通过 tag 标记。

### Tag 使用建议

| Tag 键 | 用途 |
|---|---|
| `git_commit` | 记录代码版本 |
| `branch` | 代码分支 |
| `author` | 实验负责人 |
| `model_type` | 模型类型 |
| `stage` | dev / staging / production |

```python
mlflow.set_tag("git_commit", os.popen("git rev-parse --short HEAD").read().strip())
```

## 9.2 参数与指标

### 参数：只 log 会影响结果的

```python
mlflow.log_params({
    "learning_rate": lr,
    "batch_size": bs,
    "epochs": epochs,
    "seed": seed,
})
```

- 不要把时间戳、路径、随机 ID 作为 param（应作为 tag）。
- 参数值尽量是标量或短字符串。

### 指标：统一命名与单位

```python
mlflow.log_metric("val_auc", val_auc)
mlflow.log_metric("train_loss", train_loss, step=epoch)
```

- 训练曲线用 `step` 维度。
- 同一指标不要混用不同单位。

### 避免指标爆炸

- 不要每步都 log 所有中间变量。
- 对多任务模型，按任务前缀分组：`taskA_loss`、`taskB_loss`。

## 9.3 模型打包

### 始终使用 Model Signature

```python
from mlflow.models import infer_signature
signature = infer_signature(X_train, model.predict(X_train))
mlflow.sklearn.log_model(model, "model", signature=signature)
```

- 没有 signature，在线服务无法验证输入格式。
- 多输入/复杂输入手动构建 signature。

### 提供 input_example

```python
mlflow.sklearn.log_model(model, "model", signature=signature, input_example=X_train[:3])
```

- 可用于 KServe/Triton 自动 schema 推断。
- 便于离线验证模型输入。

### 记录环境依赖

```python
mlflow.sklearn.log_model(
    model, "model",
    conda_env="conda.yaml",
    code_paths=["src/"],
)
```

- 包含 `conda.yaml` 或 `python_env.yaml`。
- 对自定义预处理代码，用 `code_paths` 一起打包。

## 9.4 Model Registry 治理

### 阶段与别名并用

| 机制 | 用途 |
|---|---|
| Stage | 静态生命周期标签（Staging / Production / Archived） |
| Alias | 动态业务标签（champion / challenger / shadow） |

推荐做法：

- 用 **Alias** 做服务路由：`models:/fraud-detector@champion`。
- 用 **Stage** 做审计与生命周期管理。
- 上线新版本时，先设 `challenger`，AB 测试后再切 `champion`。

### 版本描述与标签

```python
client.update_model_version(
    name="fraud-detector",
    version=mv.version,
    description="使用 2024-Q3 数据训练，val_auc=0.923"
)
client.set_model_version_tag(name="fraud-detector", version=mv.version, key="dataset", value="2024q3")
```

- 每个 Production 版本必须写清楚训练数据、指标、已知限制。

### 模型归档策略

- 旧版本自动打 `Archived` stage。
- 长期不用的模型删除 S3 artifact 以节省成本（但保留 registry 元数据）。

## 9.5 代码与流水线集成

### 在训练脚本里埋点

```python
def train():
    with mlflow.start_run():
        mlflow.log_params(cfg)
        model = build_model(cfg)
        for epoch in range(cfg.epochs):
            train_loss = ...
            val_loss = ...
            mlflow.log_metrics({"train_loss": train_loss, "val_loss": val_loss}, step=epoch)
        signature = infer_signature(...)
        model_info = mlflow.pytorch.log_model(model, "model", signature=signature)
        return model_info.model_uri
```

### CI/CD 中自动注册

```bash
# train.py 输出 model_uri
MODEL_URI=$(python train.py)
python register_model.py --name fraud-detector --uri "$MODEL_URI" --alias challenger
```

- 训练成功自动注册为 `challenger`。
- 人工/自动测试通过后，再提升为 `champion`。

## 9.6 成本与性能

### Artifact 存储成本

- 大模型 checkpoint 用 S3 标准；旧版本转 IA / Glacier。
- 不 log 大 tensorboard event 文件到 MLflow artifact。

### 数据库成本

- metrics 表是主要增长点；按时间分区或归档。
- 删除废弃 experiment 时使用 `mlflow gc` 清理孤儿 artifact。

### 网络成本

- 训练节点与 Artifact Store 同区域。
- 避免跨云/跨区域拉取大模型文件。

## 9.7 GenAI / Agent 应用最佳实践（3.x）

### 观测：一行 autolog + 手动补关键 span

```python
import mlflow

mlflow.langchain.autolog()          # 自动追踪 LLM 调用 / 检索 / 工具
mlflow.openai.autolog()

@mlflow.trace                       # 对关键业务函数手动补 span
def risk_check(transaction):
    ...
```

- 用 autolog 覆盖框架内部，用 `@mlflow.trace` 标注业务语义，二者出现在同一条 trace 里。
- 不要把 prompt 里的密钥、用户个人信息打进 span 属性（会被审计和导出）。

### 评估：评估集 + scorer 进版本控制

```python
result = mlflow.genai.evaluate(
    data=eval_dataset,                      # 来自线上 trace 采样的评估集
    predict_fn=my_agent,
    scorers=["relevance", "groundedness"],  # RAG 场景必查幻觉
)
```

- 评估数据集像代码一样管理：命名、版本化、记录来源（哪些线上 trace 采样而来）。
- scorer 的选择要业务化：客服机器人优先 relevance / safety，RAG 优先 groundedness。
- 用 `@mlflow.test`（3.14+）把关键评估用例固化为 pytest 回归测试，防止 prompt 改动悄悄劣化质量。

### Prompt 与模型独立发版

- Prompt 改动走 Prompt Registry：注册新版本 → 设 `staging` 别名灰度 → 评估通过 → 切 `production`。
- 模型升级走 Model Registry：两者互不阻塞，出问题各自独立回滚。
- 应用代码只引用别名（`prompts:/support-bot@production`），禁止硬编码版本号。

### 反馈闭环

- 用 Review Queue（3.14+）让业务专家在 UI 里直接标注失败 trace，标注结果回流为评估数据。
- 定期用 Judge Builder（3.9+）调整 LLM-as-a-Judge 的评审标准，与人工标注对齐。

### 成本治理

- 用 AI Gateway 按日/周/月时间窗口设 token 预算、告警与超支自动阻断（3.11.1+），避免某条 Agent 死循环打爆账单。
- trace 保留策略按环境区分：生产 30 天，开发 7 天。

## 9.8 安全与合规

### 敏感信息

- 不要 log API key、密码、个人信息。
- 参数/标签/artifact 文件名都可能被审计；提前脱敏。

### 访问控制

- 生产环境必须启用认证。
- 按团队隔离 experiment 和 registered model。
- 定期审计 Model Registry 的 Production 变更。

## 9.9 常见反模式

| 反模式 | 后果 | 建议 |
|---|---|---|
| 所有实验都在 `Default` | 无法检索 | 用命名规范 |
| 不记录随机种子 | 无法复现 | `mlflow.log_param("seed", seed)` |
| 用 run_id 硬编码服务 | 无法灰度 | 用 alias / stage |
| 模型文件和代码分开管理 | 版本不一致 | `code_paths` 打包 |
| 不设置 signature | 服务失败 | 始终 infer 或手写 signature |
| 长期不清理 artifact | 成本暴涨 | 生命周期 + 归档 |
| 改 prompt 直接上生产 | 质量劣化无感知 | Prompt Registry + 别名灰度 + `@mlflow.test` 回归 |
| trace 无保留策略 | Backend Store 膨胀 | 配置 Trace Archival（3.13+） |
| LLM 调用绕过 Gateway | 成本失控、无 Guardrails | 统一走 AI Gateway 并设预算 |
| prompt 模板硬编码在代码里 | 无法版本化对比 | 迁入 Prompt Registry |

## 本章小结

- 实验/Run/Tag/Param/Metric 要有统一命名和治理规范。
- 模型打包必须带 signature、依赖和代码路径。
- Model Registry 用 stage + alias 做生命周期和流量管理。
- GenAI 应用：autolog 观测 + 评估集回归 + Prompt/模型独立发版 + 反馈闭环 + Gateway 成本治理。
- 安全、成本、合规是生产落地不可忽视的三要素。

**参考来源**

- [MLflow — Best Practices for MLflow Tracking](https://mlflow.org/docs/latest/tracking/tracking-api.html#logging-functions)
- [MLflow — Model Signatures](https://mlflow.org/docs/latest/models.html#model-signature)
- [MLflow — Model Registry](https://mlflow.org/docs/latest/model-registry.html)
- [MLflow GenAI 文档](https://mlflow.org/docs/latest/genai/)
- [MLflow 3.14.0 — Review Queues / @mlflow.test](https://mlflow.org/releases/3.14.0/)
- 本手册 [MLflow 企业生产实践](08-production-practice.md)
