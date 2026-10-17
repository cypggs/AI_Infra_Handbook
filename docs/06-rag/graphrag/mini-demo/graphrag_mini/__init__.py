"""graphrag_mini：GraphRAG 最小实现（教学版）。

对应《GraphRAG 与知识图谱检索》主题的 Mini Demo：
- extract：规则/模板式实体-关系抽取（确定性模拟 LLM OpenIE）
- graph：邻接表图存储 + 标签传播社区检测（Leiden 的简化版）
- community：map-reduce 结构的确定性社区摘要
- query：local / global / 多跳三种查询模式 + 向量基线 + 混合检索
- cost：模拟 LLM 调用计数（对比预计算 vs Lazy 式延迟索引）
"""

from .community import (
    CommunitySummary,
    summarize_communities,
    summarize_community,
    summarize_super_communities,
)
from .corpus import CHUNKS, UPDATE_CHUNK, UPDATE_CHUNK_ID
from .cost import CostMeter
from .extract import ENTITY_LEXICON, Triple, extract_chunks, extract_text, find_entities
from .graph import KnowledgeGraph
from .query import (
    GlobalResult,
    LocalResult,
    MultiHopResult,
    global_search,
    hash_embedding,
    hybrid_search,
    local_search,
    match_entities,
    multi_hop_search,
    vector_search,
)

__version__ = "0.1.0"

__all__ = [
    "CHUNKS",
    "UPDATE_CHUNK",
    "UPDATE_CHUNK_ID",
    "ENTITY_LEXICON",
    "Triple",
    "CostMeter",
    "KnowledgeGraph",
    "CommunitySummary",
    "LocalResult",
    "MultiHopResult",
    "GlobalResult",
    "extract_text",
    "extract_chunks",
    "find_entities",
    "summarize_community",
    "summarize_communities",
    "summarize_super_communities",
    "hash_embedding",
    "vector_search",
    "match_entities",
    "local_search",
    "multi_hop_search",
    "global_search",
    "hybrid_search",
    "__version__",
]
