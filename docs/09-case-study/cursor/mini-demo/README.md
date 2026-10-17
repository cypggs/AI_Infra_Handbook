# Cursor 案例研究 Mini Demo

`cursor_case_mini`：Cursor（Anysphere）案例里最值得动手验证的五组机制的教学模拟器。纯 Python + numpy，CPU 可运行，完全确定性（固定种子，无网络、无随机外部状态）。

| 模块 | 模拟的机制 | 证据来源口径 |
|---|---|---|
| `indexing.py` | 代码库索引管道：chunk → embed → Merkle 增量同步 → 向量检索（混淆路径） | Cursor 官方文档/安全说明 + 社区抓包分析（见主题 05/06 章） |
| `latency.py` | Tab 补全端到端延迟预算分解（合计 260 ms 教学预算） | 官方博客口径：更新后服务端延迟 475→260 ms |
| `speculative.py` | Speculative Edits：以现有文件为确定性草稿的投机解码，命中率/加速比 | 官方博客口径：~1000 tok/s、约 13x 于 Llama-3-70B 朴素推理 |
| `sandbox.py` | 后台 Agent 沙箱：配额硬约束、bin-packing 调度、空闲回收 | 官方文档：云端隔离 VM；Composer 博客：数十万并发沙箱复用同一调度器 |
| `economics.py` | 订阅推理经济学：盈亏平衡、毛利率、Router 节省 | 官方定价博客口径：$20 ≈ 225 Sonnet 4 / 550 Gemini / 650 GPT-4.1 次 |

注意：所有数值为**教学模型**，用于演示相对量级与权衡方向，不代表 Cursor 内部真实数字。凡有官方口径处已在代码注释中标注。

## 运行

```bash
cd docs/09-case-study/cursor/mini-demo
pip install -e ".[dev]"
pytest tests/ -v        # 52 个确定性测试
python -m cursor_case_mini.demo
```

## 测试

`tests/` 下 5 个文件共 52 个测试，全部确定性：同一环境运行两次结果完全一致。
