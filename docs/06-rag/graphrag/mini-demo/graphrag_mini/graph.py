"""知识图谱存储与社区检测（标签传播的确定性简化版）。

真实 GraphRAG 用图数据库（或内存图）存储实体关系，用 Leiden 算法做
层次化社区检测。本模块用邻接表存图，用 "同步标签传播（Label
Propagation）+ 字典序 tie-break" 实现确定性的社区检测，并保持与
Leiden 相同的两点本质：

- 社区 = 内部连接远密于外部的节点集合；
- 支持层次化：对社区再建 "社区图"，二次检测得到超级社区。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .extract import ExtractResult, Triple


@dataclass
class Relation:
    """一条合并后的关系：跨 chunk 重复出现的同一三元组会累计 weight。"""

    subject: str
    predicate: str
    object: str
    chunk_ids: set[str] = field(default_factory=set)

    @property
    def weight(self) -> int:
        return len(self.chunk_ids)

    def key(self) -> tuple[str, str, str]:
        return (self.subject, self.predicate, self.object)

    def statement(self) -> str:
        return f"{self.subject} -[{self.predicate}]-> {self.object}"


class KnowledgeGraph:
    """极简知识图谱：实体节点 + 带谓词的有向边 + 无向邻接索引。"""

    def __init__(self) -> None:
        self.entities: dict[str, dict] = {}  # name -> {"category": str, "chunk_ids": set}
        self.relations: dict[tuple[str, str, str], Relation] = {}
        self.adj: dict[str, set[str]] = {}

    # ------------------------------------------------------------------ #
    # 构建
    # ------------------------------------------------------------------ #
    def add_entity(self, name: str, category: str = "UNKNOWN", chunk_id: str = "") -> None:
        if name not in self.entities:
            self.entities[name] = {"category": category, "chunk_ids": set()}
            self.adj.setdefault(name, set())
        if chunk_id:
            self.entities[name]["chunk_ids"].add(chunk_id)

    def add_triple(self, triple: Triple) -> None:
        self.add_entity(triple.subject, chunk_id=triple.chunk_id)
        self.add_entity(triple.object, chunk_id=triple.chunk_id)
        key = (triple.subject, triple.predicate, triple.object)
        if key not in self.relations:
            self.relations[key] = Relation(
                triple.subject, triple.predicate, triple.object
            )
        if triple.chunk_id:
            self.relations[key].chunk_ids.add(triple.chunk_id)
        self.adj[triple.subject].add(triple.object)
        self.adj[triple.object].add(triple.subject)

    def ingest(self, results: list[ExtractResult]) -> None:
        """把抽取结果灌入图谱。"""
        for result in results:
            for triple in result.triples:
                self.add_triple(triple)

    # ------------------------------------------------------------------ #
    # 查询辅助
    # ------------------------------------------------------------------ #
    def __len__(self) -> int:
        return len(self.entities)

    @property
    def relation_count(self) -> int:
        return len(self.relations)

    def neighbors(self, name: str) -> set[str]:
        return self.adj.get(name, set())

    def relations_of(self, name: str) -> list[Relation]:
        """与某实体相连的所有关系，按 (weight 降序, 语句字典序) 排序。"""
        rels = [
            rel
            for rel in self.relations.values()
            if rel.subject == name or rel.object == name
        ]
        rels.sort(key=lambda r: (-r.weight, r.statement()))
        return rels

    def degree(self, name: str) -> int:
        return len(self.adj.get(name, set()))

    # ------------------------------------------------------------------ #
    # 社区检测：同步标签传播（确定性）
    # ------------------------------------------------------------------ #
    def _label_propagation(self, nodes: list[str], adj: dict[str, set[str]]) -> dict[str, str]:
        """异步标签传播直至收敛（确定性）。

        与同步版本不同，节点按字典序逐个处理、标签就地更新，避免
        两节点社区 "互相换标签" 导致的震荡；tie-break：当前标签在
        候选中时保持不动，否则取候选中字典序最小者。
        """
        labels = {n: n for n in nodes}
        for _ in range(100):
            changed = False
            for n in sorted(nodes):
                if not adj.get(n):
                    continue
                counts = Counter(labels[m] for m in adj[n])
                top = max(counts.values())
                candidates = {lab for lab, c in counts.items() if c == top}
                best = labels[n] if labels[n] in candidates else min(candidates)
                if best != labels[n]:
                    labels[n] = best
                    changed = True
            if not changed:
                break
        return labels

    def detect_communities(self) -> list[list[str]]:
        """对全图做社区检测，返回按社区内最小实体名排序的社区列表。"""
        nodes = sorted(self.entities)
        labels = self._label_propagation(nodes, self.adj)
        groups: dict[str, list[str]] = {}
        for n in nodes:
            groups.setdefault(labels[n], []).append(n)
        communities = [sorted(members) for members in groups.values()]
        communities.sort(key=lambda members: members[0])
        return communities

    def detect_hierarchy(self) -> list[list[list[str]]]:
        """层次化社区：第 0 层是实体社区，第 1 层是 "社区之间的社区"。

        返回 levels，其中 levels[0] 是实体社区列表；levels[1] 的每个元素
        是一组 "levels[0] 社区的下标"，模拟 Leiden 自底向上的层次结构。
        demo 规模下两层已经足够展示 "社区摘要可以再聚合" 的机制。
        """
        level0 = self.detect_communities()
        levels: list[list[list[str]]] = [level0]
        if len(level0) <= 1:
            return levels

        # 社区图：跨社区的边把两个社区连起来；没有跨社区边时各自成社区。
        index_of = {
            member: idx for idx, members in enumerate(level0) for member in members
        }
        cadj: dict[int, set[int]] = {i: set() for i in range(len(level0))}
        for rel in self.relations.values():
            a, b = index_of.get(rel.subject), index_of.get(rel.object)
            if a is None or b is None or a == b:
                continue
            cadj[a].add(b)
            cadj[b].add(a)
        labels = self._label_propagation(list(range(len(level0))), cadj)
        groups: dict[int, list[int]] = {}
        for i in sorted(labels):
            groups.setdefault(labels[i], []).append(i)
        level1 = sorted(
            (sorted(members) for members in groups.values()), key=lambda m: m[0]
        )
        levels.append(level1)
        return levels

    # ------------------------------------------------------------------ #
    # 多跳遍历
    # ------------------------------------------------------------------ #
    def find_paths(
        self,
        start: str,
        goal: str,
        max_depth: int = 4,
        max_paths: int = 16,
    ) -> list[list[str]]:
        """从 start 到 goal 的简单路径（BFS，邻居按字典序遍历，确定性）。"""
        if start not in self.adj or goal not in self.adj:
            return []
        paths: list[list[str]] = []
        queue: list[list[str]] = [[start]]
        while queue and len(paths) < max_paths:
            path = queue.pop(0)
            node = path[-1]
            if len(path) - 1 >= max_depth:
                continue
            for nxt in sorted(self.adj[node]):
                if nxt in path:
                    continue
                new_path = path + [nxt]
                if nxt == goal:
                    paths.append(new_path)
                else:
                    queue.append(new_path)
            paths.sort(key=lambda p: (len(p), p))
        # 返回时按 (路径长度, 字典序) 取最优顺序。
        return paths[:max_paths]

    def stats(self) -> dict[str, int]:
        return {
            "entities": len(self.entities),
            "relations": len(self.relations),
            "avg_degree": (
                sum(len(v) for v in self.adj.values()) // max(1, len(self.adj))
            ),
        }
