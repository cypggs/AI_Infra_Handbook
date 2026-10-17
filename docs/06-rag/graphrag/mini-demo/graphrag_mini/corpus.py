"""Mini Demo 语料：一个 8 段的 AI 基础设施微型知识库（中文）。

主题刻意覆盖三个社区，便于社区检测分出清晰的三类：
1. LLM 推理引擎（vLLM / SGLang 及其技术谱系）
2. 云原生模型服务（Kubernetes / KServe）
3. 图检索增强生成（GraphRAG / LightRAG / HippoRAG）

UPDATE_CHUNK 用于演示增量更新：新文档如何把新实体接入已有图谱。
"""

CHUNKS: dict[str, str] = {
    "C1": "vLLM 是由加州大学伯克利分校开发的推理引擎。PagedAttention 是 vLLM 的核心技术。",
    "C2": "PagedAttention 由加州大学伯克利分校提出。vLLM 运行在 GPU 集群上。",
    "C3": "SGLang 是由 LLM 推理社区开发的推理框架。RadixAttention 是 SGLang 的核心技术，RadixAttention 受 PagedAttention 启发。",
    "C4": "Kubernetes 是由 Google 开源的容器编排系统。KServe 是 Kubernetes 生态的模型服务框架。",
    "C5": "GraphRAG 是由微软研究院提出的检索增强生成方法。GraphRAG 基于知识图谱。社区摘要是 GraphRAG 的关键组件。",
    "C6": "LightRAG 由香港大学数据科学实验室提出。LightRAG 是 GraphRAG 的轻量化改进。LightRAG 基于知识图谱。",
    "C7": "HippoRAG 由俄亥俄州立大学提出。HippoRAG 是对 GraphRAG 的改进。HippoRAG 使用个性化 PageRank。HippoRAG 在知识图谱上做多跳检索。",
}

# 增量更新场景使用的新文档：把 NebulaGraph 接入 "图检索" 社区。
UPDATE_CHUNK_ID = "C8"
UPDATE_CHUNK = (
    "NebulaGraph 是由 NebulaGraph 团队开发的知识图谱数据库。"
    "NebulaGraph 可存储 GraphRAG 的实体关系。"
)
