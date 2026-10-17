"""实体/关系抽取（确定性规则版，模拟 LLM 的 OpenIE 抽取）。

真实 GraphRAG 用 LLM prompt 从文本中自由抽取实体与关系（schema-free
OpenIE）。本模块用 "实体词典 + 句法模板" 做确定性模拟：

1. 用实体词典在文本中做最长匹配，找到所有实体提及；
2. 对每个共现实体对，按出现顺序把实体替换为 {A}/{B} 得到 "句子框架"；
3. 在模板表中做最长包含匹配，得到谓词；匹配不到则回退为 RELATED_TO。

这套机制保留了 OpenIE 的两个关键性质：
- schema-free：词典与模板可随时扩充；
- 有噪声：并非所有共现对都有明确谓词（见 RELATED_TO 回退）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .cost import CostMeter

# ---------------------------------------------------------------------------
# 实体词典：name -> category。模拟 LLM 抽取时的 "可识别实体类型"。
# 生产系统中这一步由 LLM 完成，不需要词典；词典只是确定性的替代品。
# ---------------------------------------------------------------------------
ENTITY_LEXICON: dict[str, str] = {
    "加州大学伯克利分校": "ORG",
    "微软研究院": "ORG",
    "香港大学数据科学实验室": "ORG",
    "俄亥俄州立大学": "ORG",
    "Google": "ORG",
    "LLM 推理社区": "ORG",
    "NebulaGraph 团队": "ORG",
    "vLLM": "PRODUCT",
    "SGLang": "PRODUCT",
    "Kubernetes": "PRODUCT",
    "KServe": "PRODUCT",
    "GraphRAG": "PRODUCT",
    "LightRAG": "PRODUCT",
    "HippoRAG": "PRODUCT",
    "NebulaGraph": "PRODUCT",
    "PagedAttention": "TECH",
    "RadixAttention": "TECH",
    "GPU 集群": "TECH",
    "知识图谱": "CONCEPT",
    "社区摘要": "CONCEPT",
    "个性化 PageRank": "CONCEPT",
    "检索增强生成": "CONCEPT",
}

# ---------------------------------------------------------------------------
# 关系模板：框架字符串 -> 谓词。{A} 为句中先出现的实体，{B} 为后出现的。
# 匹配时取 "最长包含" 的模板，保证例如 "{A}是{B}的轻量化改进" 优先于
# 更短的通用模板。
# ---------------------------------------------------------------------------
RELATION_TEMPLATES: dict[str, str] = {
    "{A}是{B}的轻量化改进": "VARIANT_OF",
    "{A}是对{B}的改进": "VARIANT_OF",
    "{A}是{B}的核心技术": "CORE_TECH_OF",
    "{A}是{B}的关键组件": "COMPONENT_OF",
    "{A}是{B}生态的模型服务框架": "PART_OF_ECOSYSTEM",
    "{A}在{B}上做多跳检索": "OPERATES_ON",
    "{A}运行在{B}上": "RUNS_ON",
    "{A}可存储{B}": "STORES",
    "{A}是由{B}开发": "DEVELOPED_BY",
    "{A}是由{B}开源": "OPEN_SOURCED_BY",
    "{A}是由{B}提出": "PROPOSED_BY",
    "{A}由{B}提出": "PROPOSED_BY",
    "{A}受{B}启发": "INSPIRED_BY",
    "{A}基于{B}": "BASED_ON",
    "{A}使用{B}": "USES",
}

# 按模板长度降序排列，实现 "最长匹配优先"。
_SORTED_TEMPLATES: list[tuple[str, str]] = sorted(
    RELATION_TEMPLATES.items(), key=lambda kv: len(kv[0]), reverse=True
)

_SENT_SPLIT = re.compile(r"[。；！？\n]")
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Triple:
    """一条 (subject, predicate, object) 三元组。"""

    subject: str
    predicate: str
    object: str
    chunk_id: str = ""


@dataclass
class ExtractResult:
    """一段文本的抽取结果。"""

    chunk_id: str
    entities: list[str] = field(default_factory=list)
    triples: list[Triple] = field(default_factory=list)


def find_entities(text: str) -> list[str]:
    """在文本中查找实体提及，返回按出现位置排序、去重后的实体名列表。"""
    found: list[tuple[int, str]] = []
    occupied = [False] * len(text)
    # 最长匹配优先：先尝试词典里的长实体名。
    for name in sorted(ENTITY_LEXICON, key=len, reverse=True):
        start = 0
        while True:
            idx = text.find(name, start)
            if idx < 0:
                break
            end = idx + len(name)
            if not any(occupied[idx:end]):
                found.append((idx, name))
                for i in range(idx, end):
                    occupied[i] = True
            start = idx + 1
    found.sort()
    seen: set[str] = set()
    ordered: list[str] = []
    for _, name in found:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def _frame(sentence: str, first: str, second: str) -> str:
    """把句中 first 全部替换为 {A}、second 全部替换为 {B}，并去掉空白。

    先替换较长的实体名，避免 "NebulaGraph" 把 "NebulaGraph 团队" 截断。
    """
    ordered = sorted([(first, "{A}"), (second, "{B}")], key=lambda kv: len(kv[0]), reverse=True)
    framed = sentence
    for name, placeholder in ordered:
        framed = framed.replace(name, placeholder)
    return _SPACE.sub("", framed)


def match_predicate(sentence: str, first: str, second: str) -> str:
    """对共现实体对做模板匹配，返回谓词；无匹配则回退 RELATED_TO。"""
    if first == second:
        return "RELATED_TO"
    frame = _frame(sentence, first, second)
    for template, predicate in _SORTED_TEMPLATES:
        if template in frame:
            return predicate
    return "RELATED_TO"


def extract_text(text: str, chunk_id: str = "") -> ExtractResult:
    """抽取一段文本中的实体与关系三元组（确定性）。"""
    entities = find_entities(text)
    result = ExtractResult(chunk_id=chunk_id, entities=entities)
    for sentence in _SENT_SPLIT.split(text):
        if not sentence.strip():
            continue
        sentence_entities = [e for e in entities if e in sentence]
        # 按句内位置排序，保证 (先出现, 后出现) 的角色分配确定。
        sentence_entities.sort(key=lambda e: sentence.index(e))
        for i in range(len(sentence_entities)):
            for j in range(i + 1, len(sentence_entities)):
                first, second = sentence_entities[i], sentence_entities[j]
                predicate = match_predicate(sentence, first, second)
                result.triples.append(
                    Triple(first, predicate, second, chunk_id=chunk_id)
                )
    return result


def extract_chunks(
    chunks: dict[str, str], meter: CostMeter | None = None
) -> list[ExtractResult]:
    """对语料库逐段抽取；每段计 1 次模拟 LLM 抽取调用。"""
    results = []
    for chunk_id in sorted(chunks):
        if meter is not None:
            meter.charge_extract()
        results.append(extract_text(chunks[chunk_id], chunk_id=chunk_id))
    return results
