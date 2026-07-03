# Tool Use Mini Demo

A minimal, CPU-runnable demonstration of LLM Tool Use mechanics using only the Python standard library.

## Scenario

User asks in Chinese:

> 帮我查一下北京天气和美元兑人民币汇率，然后计算 1000 美元能换多少人民币。

The demo shows how an LLM can emit parallel tool calls, how the framework validates and executes them, and how the results are formatted back to the model for a final answer.

## Project Structure

```
mini-demo/
├── README.md
├── pyproject.toml
├── tool_use_mini/
│   ├── __init__.py
│   ├── llm_client.py      # deterministic MockLLMClient
│   ├── tool.py            # Tool / ToolRegistry / JSON Schema helpers
│   ├── parser.py          # parse model tool_calls output
│   ├── validator.py       # JSON Schema validation with structured errors
│   ├── executor.py        # execute tool calls (parallel, timeout, retry, fallback)
│   ├── formatter.py       # format tool results back to model messages
│   ├── policy.py          # allowed tools, max calls, timeout budget
│   └── demo.py            # run_demo() entry point
└── tests/
    ├── __init__.py
    ├── test_llm_client.py
    ├── test_tool.py
    ├── test_parser.py
    ├── test_validator.py
    ├── test_executor.py
    ├── test_formatter.py
    └── test_demo.py
```

## Running the Demo

```bash
python -m tool_use_mini.demo
```

Or after installing the package:

```bash
tool-use-demo
```

## Running Tests

```bash
pytest tests/ -q
```

## Key Features

- **No external API keys or network calls.** The LLM is mocked and tools return deterministic data.
- **Parallel tool execution.** The mock LLM emits `get_weather` and `get_exchange_rate` together; the executor runs them in parallel threads.
- **Retry / fallback path.** `get_exchange_rate` is configured to fail on its first invocation, then fall back to a cached rate.
- **Malformed tool-call handling.** The validator rejects bad arguments with structured errors; a retry path in the demo fixes the call.
- **Policy enforcement.** A simple policy limits allowed tools, maximum calls, and total timeout budget.

## Design Notes

- `MockLLMClient` returns pre-programmed responses based on the conversation history, making the demo fully deterministic.
- `ToolRegistry` stores tools by name, including their JSON Schema definitions.
- `validate_arguments` is a small hand-written validator supporting `object`, `properties`, `required`, and primitive `type` checks.
- `Executor` uses `concurrent.futures.ThreadPoolExecutor` for parallelism and supports per-call timeout, retry, and fallback values.
