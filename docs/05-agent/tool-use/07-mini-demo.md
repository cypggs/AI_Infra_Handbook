# Mini Demo 说明

为了帮助读者把概念落地，本主题配套了一个最小可运行的示例（`docs/05-agent/tool-use/mini-demo/`）。该示例不依赖复杂框架，只用 Python 标准库 + 一个 LLM 客户端，演示“工具注册 → 模型决策 → 解析校验 → 执行 → 结果反馈”的完整循环。

> 注意：本章只说明示例的设计思路、目录结构与运行方式，**不重复贴出完整源码**。读者可在配套目录中阅读并运行实际代码。

## 场景设计

示例选择一个贴近日常的复合查询：

> “我想下周三去北京出差，帮我查一下那天的天气，再算一下从北京南站到首都机场打车大概要多少钱，以及总共需要预留多少时间。”

为了完成这个任务，Agent 需要调用三类工具：

1. `get_weather(city, date)`：查询指定城市指定日期的天气。
2. `estimate_taxi_fare(distance_km, time_of_day)`：根据距离与时段估算打车费用。
3. `get_route_duration(origin, destination, mode)`：查询两点之间的交通耗时。

这个场景覆盖了**并行调用**（天气与路线可以并发查）和**顺序依赖**（估算费用需要先知道距离）两种典型模式。

## 目录结构

```text
docs/05-agent/tool-use/mini-demo/
├── README.md              # 运行说明与环境变量
├── requirements.txt       # 依赖：openai / anthropic 等
├── config.yaml            # 工具配置与执行策略（超时、重试）
├── agent.py               # 主循环：调用模型、调度工具、终止判断
├── tools/
│   ├── __init__.py
│   ├── weather.py         # get_weather 实现
│   ├── taxi.py            # estimate_taxi_fare 实现
│   └── route.py           # get_route_duration 实现
├── registry.py            # ToolRegistry：注册与发现
├── schema_manager.py      # SchemaManager：归一化与校验
├── executor.py            # ToolExecutor：并发、超时、重试
├── formatter.py           # ResultFormatter：结果格式化与截断
└── tests/
    ├── test_registry.py
    ├── test_validator.py
    └── test_executor.py
```

## 运行方式

1. 安装依赖：

```bash
cd docs/05-agent/tool-use/mini-demo
pip install -r requirements.txt
```

2. 配置 API Key：

```bash
export OPENAI_API_KEY=sk-...
# 或 export ANTHROPIC_API_KEY=...
```

3. 运行示例：

```bash
python agent.py \
  --query "下周三北京出差，查天气、算打车费、预估总耗时" \
  --provider openai \
  --max-turns 5
```

4. 运行单元测试：

```bash
pytest tests/
```

## 关键设计点

### 1. 工具定义完全用 JSON Schema 描述

每个工具模块除了实现函数，还提供一个 `definition()` 方法，返回标准 JSON Schema。`schema_manager.py` 负责把它转换为当前 provider 需要的格式。例如 OpenAI 需要 `function.parameters`，Anthropic 需要 `input_schema`。

### 2. 调用结果用内部模型标准化

无论使用哪家模型，`agent.py` 内部统一使用如下结构：

```python
@dataclass
class ToolInvocation:
    call_id: str
    tool_name: str
    arguments: dict
```

Parser 负责把不同厂商的响应解析成这个结构，Validator 再用 JSON Schema 校验参数。

### 3. 显式区分并行与串行

示例中 `executor.py` 的 `execute_batch` 方法默认并发执行独立调用，但 `agent.py` 会在调用前检查参数依赖。如果发现某个调用需要依赖前一次结果（例如估算费用需要距离），则先执行前置调用，再构造后续调用。

### 4. 结果截断与错误回显

`formatter.py` 对过长的执行结果做截断，并把执行异常包装成模型可理解的错误描述。例如：

```text
调用 get_weather 失败：外部天气服务返回 503，已重试 2 次仍不可用。请稍后重试或换一个城市查询。
```

### 5. 终止条件可配置

`agent.py` 支持 `max-turns`、`max-tool-calls`、`no-progress-threshold` 等终止条件，防止无限循环。

## 预期输出

运行成功后，终端会打印：

```text
[Turn 1] Model decided: tool_use get_weather, get_route_duration
[Turn 1] Executed 2 tools in 0.42s
[Turn 2] Model decided: tool_use estimate_taxi_fare
[Turn 2] Executed 1 tool in 0.18s
[Turn 3] Model decided: final_answer

Final Answer:
下周三北京天气晴，气温 22~30°C。
北京南站到首都机场驾车约 35 公里，预计 50 分钟。
非高峰时段打车费用约 110~140 元。
建议预留 1.5~2 小时（含安检与市内交通）。
```

## 与生产系统的差距

这个 Mini Demo 为了可读性做了大量简化，与真实生产系统存在明显差距：

| 能力 | Demo 实现 | 生产要求 |
| --- | --- | --- |
| 鉴权授权 | 无 | RBAC、OAuth、HITL |
| 沙箱执行 | 本地函数 | 容器 / 网络隔离 |
| 工具发现 | 静态注册 | MCP 动态发现、版本管理 |
| 可观测性 | 打印日志 | OpenTelemetry、指标、告警 |
| 错误治理 | 简单重试 | 熔断、降级、幂等、批量部分失败 |
| 多模型兼容 | 单一 provider | Schema Manager 适配多家模型 |
| 结果压缩 | 硬截断 | 摘要模型、embedding 检索 |

尽管如此，Demo 已经足以展示 Tool Use 的核心循环，并作为后续扩展的起点。
