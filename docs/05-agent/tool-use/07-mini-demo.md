# Mini Demo 说明

为了帮助读者把概念落地，本主题配套了一个最小可运行的示例（`docs/05-agent/tool-use/mini-demo/`）。示例**只依赖 Python 标准库**：LLM 由确定性的 Mock 客户端扮演，工具返回固定数据，不访问网络、不需要任何 API Key，方便离线阅读与调试。

> 注意：本章只说明示例的设计思路、目录结构与运行方式，**不重复贴出完整源码**。读者可在配套目录中阅读并运行实际代码。

## 场景设计

示例选择一个覆盖两类典型调用模式的复合查询：

> “帮我查一下北京天气和美元兑人民币汇率，然后计算 1000 美元能换多少人民币。”

为了完成这个任务，Agent 需要调用三个工具：

1. `get_weather(city)`：查询指定城市的当前天气（独立调用）。
2. `get_exchange_rate(currency_pair)`：查询汇率（独立调用，但首次调用会失败，走重试/兜底路径）。
3. `calculate_rmb(amount_usd, rate)`：用汇率计算人民币金额（依赖前两个工具的结果，顺序调用）。

这个场景同时覆盖了**并行调用**（天气与汇率并发执行）和**顺序依赖**（换算必须等汇率返回）两种模式，外加一条“参数 malformed → 校验拒绝 → 重试修正”的容错路径。

## 目录结构

```text
docs/05-agent/tool-use/mini-demo/
├── README.md                  # 运行说明
├── pyproject.toml             # 打包配置（hatchling），dev 依赖为 pytest
├── tool_use_mini/             # 示例包
│   ├── __init__.py
│   ├── llm_client.py          # MockLLMClient：按对话历史返回预编排响应
│   ├── tool.py                # Tool / ToolRegistry / JSON Schema 工具定义
│   ├── parser.py              # 解析模型输出的 tool_calls
│   ├── validator.py           # JSON Schema 校验，输出结构化错误
│   ├── executor.py            # 并发执行、超时、重试、fallback
│   ├── formatter.py           # 把工具结果格式化为模型消息
│   ├── policy.py              # 允许工具清单、调用次数与超时预算
│   └── demo.py                # run_demo() 主循环入口
└── tests/                     # 每个模块一组单元测试
    ├── test_llm_client.py
    ├── test_tool.py
    ├── test_parser.py
    ├── test_validator.py
    ├── test_executor.py
    ├── test_formatter.py
    └── test_demo.py
```

## 运行方式

```bash
cd docs/05-agent/tool-use/mini-demo

# 安装（可选，含 dev 依赖）
pip install -e ".[dev]"

# 运行 demo
python -m tool_use_mini.demo
# 或安装后使用入口脚本
tool-use-demo

# 运行单元测试
pytest tests/ -v
```

## 关键设计点

### 1. MockLLMClient 保证完全确定性

`llm_client.py` 中的 Mock 客户端根据当前对话历史返回预编排的响应：第一轮同时发出 `get_weather` 和 `get_exchange_rate` 两个并行调用；在收到汇率结果后发出 `calculate_rmb`；全部完成后给出最终自然语言答案。因为响应是预编程的，测试与演示结果完全可复现。

### 2. 工具定义就是 JSON Schema

每个工具模块提供名称、描述与 JSON Schema（`type` / `properties` / `required` / `enum`）。`validator.py` 中的 `validate_arguments` 是一个手写的小型校验器，覆盖 `object`、`properties`、`required` 与基本类型检查，校验失败时输出**结构化错误**（参数路径 + 原因），供模型自我修正。

### 3. 解析、校验、执行、格式化分层

`demo.py` 主循环串联各模块，对应第 4 章的生命周期：

```text
MockLLMClient.chat(messages)
  → parser.parse_tool_calls(...)     # 解析
  → registry.get(...) + validator    # 查表 + 校验
  → policy.check(...)                # 策略检查（允许清单 / 次数 / 预算）
  → executor.execute(...)            # 并发执行（ThreadPoolExecutor）
  → formatter.format_tool_message(...)  # 格式化回写消息
  → 下一轮对话
```

### 4. 显式的容错路径

示例内置三条容错路径，均可在测试中复现：

- **工具故障 + fallback**：`get_exchange_rate` 首次调用返回错误，Executor 按配置重试并使用兜底汇率，最终调用成功。
- **malformed 调用**：某轮 `calculate_rmb` 参数不合法，Validator 拒绝并生成错误结果回传，Mock 模型下一轮修正参数。
- **并发执行**：独立的天气与汇率调用在 `ThreadPoolExecutor` 中并行执行。

### 5. Policy 模块兜底

`policy.py` 维护允许工具清单、最大调用次数与总超时预算。任一约束被突破时抛出异常，防止无限循环——对应第 4 章的终止条件。

## 预期输出

运行 `python -m tool_use_mini.demo` 后，终端先打印完整对话与工具调用 trace（角色、tool_call 名称与参数、tool_call_id、结果），最后输出：

```text
============================================================
Final answer:
北京今天晴，气温 28℃，湿度 45%。
美元兑人民币汇率为 7.25。
1000 美元可以兑换 7250.00 人民币。
```

## 与生产系统的差距

这个 Mini Demo 为了可读性做了大量简化，与真实生产系统存在明显差距：

| 能力 | Demo 实现 | 生产要求 |
| --- | --- | --- |
| 模型 | Mock 预编排响应 | 真实 LLM + 受约束解码 |
| 鉴权授权 | Policy 允许清单 | RBAC、OAuth、参数级授权、HITL |
| 沙箱执行 | 本地函数 | 容器 / 网络隔离 |
| 工具发现 | 静态注册 | MCP 动态发现、版本管理、哈希存证 |
| 可观测性 | 打印 trace | OpenTelemetry、指标、告警 |
| 错误治理 | 简单重试 + fallback | 熔断、降级、幂等键、verify-before-retry |
| 多模型兼容 | 单一消息格式 | Schema Manager 适配多家厂商 |
| 结果压缩 | 直接序列化 | 摘要、截断、外置存储 |

尽管如此，Demo 已经足以展示 Tool Use 的核心循环，并作为后续扩展的起点。
