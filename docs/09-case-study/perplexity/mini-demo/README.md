# Perplexity 案例研究 Mini Demo：答案引擎推理经济学

对应文档：`docs/09-case-study/perplexity/07-mini-demo.md`。

纯 Python + numpy，CPU 可运行、完全确定性。模拟 Perplexity 案例中最值得动手验证的四组权衡：

| 模块 | 模拟的权衡 |
|---|---|
| `routing.py` | 按查询复杂度选择大/小模型：成本-质量权衡曲线与阈值路由 |
| `caching.py` | exact + 语义缓存的命中率与成本节省 |
| `streaming.py` | TTFT 与流式渲染对用户感知延迟的影响模型 |
| `rerank.py` | 检索-重排-生成流水线中重排层的效果/延迟权衡 |
| `demo.py` | 5 个端到端场景 |

## 运行

```bash
pip install -e ".[dev]"
pytest tests/ -v
python -m perplexity_case_mini.demo
```

所有模型参数为简化教学值（参照公开口径的相对量级），不代表 Perplexity 真实内部数字。
