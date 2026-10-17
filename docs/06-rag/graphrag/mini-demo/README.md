# GraphRAG Mini Demo

《GraphRAG 与知识图谱检索》主题的配套最小实现：`graphrag_mini` 包，纯 Python + numpy，CPU 可运行，完全确定性（不调任何真实 LLM / 图数据库）。

## 它模拟了什么

| 模块 | 模拟对象 | 实现方式 |
|---|---|---|
| `extract.py` | LLM OpenIE 实体/关系抽取 | 实体词典 + 句法模板的最长匹配，失败回退 `RELATED_TO` |
| `graph.py` | 图存储 + Leiden 社区检测 | 邻接表 + 同步标签传播（tie-break 字典序，确定性）+ 层次化 |
| `community.py` | LLM 社区摘要（map-reduce） | 关系陈述 map + 频次聚合 reduce，输出确定性文本 |
| `query.py` | local / global / 多跳查询 | 一跳邻域 / 社区摘要 map-reduce / BFS 寻路；另含哈希向量暴力基线与 RRF 混合检索 |
| `cost.py` | LLM 调用成本 | 调用计数（抽取次数 + 摘要次数） |

## 运行

```bash
pip install -e ".[dev]"
pytest tests/ -v
python -m graphrag_mini.demo
```

## 场景

1. **索引构建**：8 段语料 → 实体/关系 → 一级/二级社区 → 社区摘要
2. **局部查询**：`GraphRAG 是谁提出的？`
3. **全局查询**：`围绕知识图谱的检索技术有哪些研究进展？`
4. **多跳查询 vs 向量基线**：跨 C1+C3 的实体链，向量基线只能返回各自含局部信息的 chunk
5. **增量更新**：新文档（NebulaGraph）接入已有图谱
6. **成本对比**：预计算全部社区摘要 vs Lazy 式按需摘要的模拟 LLM 调用数
7. **混合检索**：图结果与向量结果 RRF 合并

## 与真实 GraphRAG 的差距

这是教学模型：抽取是模板而非 LLM、社区检测是标签传播而非 Leiden、摘要是统计聚合而非 LLM 生成、向量基线是哈希 embedding 而非真实模型。结构与数据流与真实系统一致，章节 07 中有逐项对照表。
