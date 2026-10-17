# Mini Demo：纯 Python 实现 GraphRAG 最小栈

配套 demo 位于本主题目录下的 `mini-demo/`（`graphrag_mini` 包），纯 Python + numpy 实现，CPU 可运行、完全确定性（不调任何真实 LLM 与图数据库），用一个 7 段的 AI 基础设施微型语料库端到端跑通"抽取 → 建图 → 社区检测 → 社区摘要 → 三种查询 → 增量更新 → 成本对比"。

## 运行方式

```bash
cd docs/06-rag/graphrag/mini-demo
pip install -e ".[dev]"
pytest tests/ -v          # 78 个确定性测试
python -m graphrag_mini.demo
```

## 模块结构

| 模块 | 对应真实系统的环节 |
|---|---|
| `extract.py` | LLM OpenIE 抽取：实体词典最长匹配 + 句法模板谓词匹配（失败回退 RELATED_TO，模拟 OpenIE 噪声） |
| `graph.py` | 图存储（邻接表 + 关系合并）与社区检测（异步标签传播，tie-break 确定性，层次化 2 层） |
| `community.py` | 社区摘要：map（关系陈述）+ reduce（频次聚合）的确定性文本，支持超级社区聚合 |
| `query.py` | local（一跳邻域）/ global（社区摘要 map-reduce）/ 多跳（BFS 寻路）三种模式 + 哈希向量基线 + RRF 混合检索 |
| `cost.py` | 模拟 LLM 调用计数，对比预计算与延迟摘要两种策略 |

## 端到端场景与实测输出

**场景 1：索引构建。** 7 段语料抽出 **20 个实体、22 条关系**；标签传播分出 **3 个一级社区**，层次化得到 **3 个二级社区**：

- 社区 0（7 实体）：PagedAttention / vLLM / SGLang / RadixAttention / 伯克利 / GPU 集群 / LLM 推理社区 —— "LLM 推理引擎"主题；
- 社区 1（3 实体）：Kubernetes / Google / KServe —— "云原生模型服务"主题；
- 社区 2（10 实体）：GraphRAG / LightRAG / HippoRAG / 知识图谱 / 三家研究机构等 —— "图检索增强生成"主题。

**场景 2：局部查询。** 问"GraphRAG 是谁提出的？"：命中实体 GraphRAG，返回 PROPOSED_BY 微软研究院、BASED_ON 知识图谱等关系及来源 chunk C5/C6/C7。

**场景 3：全局查询。** 问"围绕知识图谱的检索技术有哪些研究进展？"：按问题实体在社区摘要中的命中数打分，图检索社区（score=1）排在第一，答案由其报告与代表性关系陈述组成。

**场景 4：多跳查询 vs 向量基线。** 问"由加州大学伯克利分校开发的推理引擎，其核心技术启发了 SGLang 的哪个组件？"：

- 图检索找到路径 `加州大学伯克利分校 -> PagedAttention -> RadixAttention -> SGLang`，涉及 C2+C3 两段拼接，答案链指向 RadixAttention；
- 向量基线 top-3 为 C1/C2/C3——每段各自只含局部事实，没有任何一段能独立回答（RELATED_TO 噪声边导致的 2 跳近路也会在路径列表中出现，是观察抽取噪声影响的好机会）。

**场景 5：增量更新。** 新文档（NebulaGraph）接入后关系数 22 → 26，STORES 边把 NebulaGraph 直接挂到 GraphRAG 上；查询"NebulaGraph 是由谁开发的，它可以存储什么？"返回 DEVELOPED_BY NebulaGraph 团队与 STORES GraphRAG。

**场景 6：成本对比。** 用调用次数模拟 LLM 成本：

| 策略 | 抽取 | 摘要 | 合计 |
|---|---|---|---|
| GraphRAG 风格（预计算全部层级摘要） | 7 | 6（3 一级 + 3 二级） | 13 |
| Lazy 风格（摘要延迟到查询时） | 7 | 1（按需 1 个社区） | 8 |

小语料下差距是 13 vs 8；放到真实规模（社区数随语料增长、报告生成是 LLM 调用），摘要环节会主导成本——这正是 LazyGraphRAG 要解决的问题（其官方口径是索引成本降至约 0.1%、全局查询成本约降为 1/700，见第 2 章）。

**场景 7：混合检索。** "GraphRAG 是谁提出的？"的图结果（C5/C6/C7）与向量结果按 RRF 合并，C5 双路命中排第一。

## 关键代码走读

谓词模板匹配（`extract.py`）是整个 demo 的语义核心：

```python
RELATION_TEMPLATES = {
    "{A}是{B}的轻量化改进": "VARIANT_OF",
    "{A}是{B}的核心技术": "CORE_TECH_OF",
    "{A}由{B}提出": "PROPOSED_BY",
    # ... 共 14 个模板
}
# 对共现实体对：按出现顺序替换为 {A}/{B} 得到 "句子框架"，
# 取最长包含匹配的模板为谓词；无匹配回退 RELATED_TO。
```

社区检测（`graph.py`）用异步标签传播替代 Leiden：节点按字典序处理、标签就地更新（避免两节点社区互换标签的震荡），频次相同保持当前标签——完全确定，行为与 Leiden 一样是"内部紧密连接的簇"。

## 跑测试

78 个测试覆盖：抽取（词典、模板优先级、RELATED_TO 回退、成本计量）、图（三元组合并、三角形社区、语料社区划分、层次化、寻路深度约束、增量更新）、摘要（聚合正确性、层次聚合、可追溯性）、查询（embedding 确定性、局部/全局/多跳行为、向量基线局限、RRF 混合）与端到端 demo（统计数字、确定性）。全部通过：

```text
78 passed in 0.11s
```

## 与真实系统的差距

对照表见[第 6 章](06-source-analysis)（6.5 节）。最重要的三点：抽取是规则而非 LLM（无 gleaning、无语义泛化）、社区检测是标签传播而非 Leiden（无模块度保证）、摘要是统计聚合而非 LLM 生成。数据流与真实 GraphRAG 完全一致，适合作为阅读真实源码前的热身。
