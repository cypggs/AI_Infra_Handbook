"""Radix tree 前缀缓存：RadixAttention 语义的极简版。

SGLang 的 RadixAttention / vLLM 的 prefix caching 用一个 radix tree
维护「token 序列 → 已缓存 KV block」的映射：

- 多条请求共享相同前缀（system prompt、few-shot 示例、多轮对话历史）时，
  命中前缀的 token 不需要重新 prefill；
- tree 按 token 序列而不是 request 组织，天然支持任意两条请求的公共前缀复用；
- 显存紧张时按 LRU 逐出叶子节点，释放 block。

本模块的 match/insert 以单个 token 为单位（真实系统按 block 对齐，
这里为了教学把 block 粒度抽象掉，由调用方按 block 对齐 token 序列）。
"""

from __future__ import annotations


def _common_prefix_len(a: tuple[int, ...], b: tuple[int, ...] | list[int]) -> int:
    n = min(len(a), len(b))
    j = 0
    while j < n and a[j] == b[j]:
        j += 1
    return j


class RadixNode:
    __slots__ = ("segment", "children", "last_access")

    def __init__(self, segment: tuple[int, ...] = (), last_access: int = 0) -> None:
        self.segment: tuple[int, ...] = segment
        # children 以子节点 segment 的首 token 为 key
        self.children: dict[int, "RadixNode"] = {}
        self.last_access: int = last_access

    def is_leaf(self) -> bool:
        return not self.children


class RadixTree:
    """token 序列前缀树，支持最长前缀匹配与 LRU 逐出。"""

    def __init__(self) -> None:
        self.root = RadixNode()
        self._tick = 0
        self.evictions = 0

    # ------------------------------------------------------------------
    def _next_tick(self) -> int:
        self._tick += 1
        return self._tick

    def _walk(self, tokens):
        """返回 (公共前缀长度, 前缀末尾所在节点, 部分匹配的子节点, 子节点进入位置)。

        - 整段走完：末节点、partial=None；
        - 缺少子节点：返回当前位置与节点、partial=None；
        - segment 中段分叉：公共前缀长度含中段匹配，partial 为分叉子节点，
          entry_pos 为进入该子节点的 token 下标。
        """
        node = self.root
        i = 0
        while i < len(tokens):
            child = node.children.get(tokens[i])
            if child is None:
                return i, node, None, i
            j = _common_prefix_len(child.segment, tokens[i:])
            if j < len(child.segment):
                # 在 child.segment 中段分叉：匹配到 i+j，但节点仍属于父级
                return i + j, node, child, i
            i += j
            node = child
        return i, node, None, i

    def _refresh(self, tokens) -> None:
        """沿已匹配路径刷新 LRU 时间戳。"""
        node = self.root
        i = 0
        while i < len(tokens):
            child = node.children.get(tokens[i])
            if child is None:
                break
            j = _common_prefix_len(child.segment, tokens[i:])
            child.last_access = self._next_tick()
            if j < len(child.segment):
                break
            i += j
            node = child

    # ------------------------------------------------------------------
    def match(self, tokens: list[int] | tuple[int, ...]) -> int:
        """返回与已缓存序列的最长公共前缀长度，并刷新访问时间。"""
        matched, _, _, _ = self._walk(tuple(tokens))
        if matched > 0:
            self._refresh(tuple(tokens))
        return matched

    def insert(self, tokens: list[int] | tuple[int, ...]) -> int:
        """插入序列，返回插入前命中的前缀长度。

        已存在的公共前缀复用节点；分叉处分裂 segment；剩余部分挂新叶子。
        """
        tokens = tuple(tokens)
        matched, node, partial, entry_pos = self._walk(tokens)
        if matched == len(tokens):
            self._refresh(tokens)
            return matched

        if partial is not None:
            # 在 partial.segment 的 matched-entry_pos 处分裂出中间节点
            j0 = matched - entry_pos
            upper = RadixNode(partial.segment[:j0], last_access=partial.last_access)
            lower = RadixNode(partial.segment[j0:], last_access=partial.last_access)
            lower.children = partial.children
            upper.children[partial.segment[j0]] = lower
            node.children[partial.segment[0]] = upper
            node = upper

        rest = tokens[matched:]
        while True:
            if not rest:
                return matched
            # 找与 rest 公共前缀最长（且非零）的子节点
            child = None
            j = 0
            for c in node.children.values():
                cj = _common_prefix_len(c.segment, rest)
                if cj > j:
                    child, j = c, cj
            if child is None:
                leaf = RadixNode(rest, last_access=self._next_tick())
                node.children[rest[0]] = leaf
                return matched
            if j == len(child.segment):
                # 整段匹配：下潜继续
                node = child
                rest = rest[j:]
                continue
            # 中段分叉：分裂出一个中间节点，继续合并剩余部分
            upper = RadixNode(child.segment[:j], last_access=child.last_access)
            lower = RadixNode(child.segment[j:], last_access=child.last_access)
            lower.children = child.children
            upper.children[child.segment[j]] = lower
            node.children[child.segment[0]] = upper
            node = upper
            rest = rest[j:]

    # ------------------------------------------------------------------
    def total_tokens(self) -> int:
        """树中缓存的 token 总数（所有节点 segment 长度之和）。"""
        total = 0
        stack = [self.root]
        while stack:
            node = stack.pop()
            total += len(node.segment)
            stack.extend(node.children.values())
        return total

    def num_nodes(self) -> int:
        total = 0
        stack = [self.root]
        while stack:
            node = stack.pop()
            total += 1
            stack.extend(node.children.values())
        return total

    def evict_lru(self) -> int:
        """逐出最近最少访问的叶子节点，返回释放的 token 数。

        祖先节点仍持有有效的公共前缀缓存数据，因此只删除叶子本身。
        真实系统里释放的是 block；这里 token 数即 block 数的线性度量。
        """
        best_leaf: RadixNode | None = None
        best_parent: RadixNode | None = None
        best_access = None

        def dfs(node: RadixNode) -> None:
            nonlocal best_leaf, best_parent, best_access
            for first, child in node.children.items():
                if child.is_leaf():
                    if best_access is None or child.last_access < best_access:
                        best_access = child.last_access
                        best_leaf = child
                        best_parent = node
                else:
                    dfs(child)

        dfs(self.root)
        if best_leaf is None or best_parent is None:
            return 0
        freed = len(best_leaf.segment)
        del best_parent.children[best_leaf.segment[0]]
        self.evictions += 1
        return freed
