"""算子融合 pass（operator fusion）。

真实 AI 编译器（XLA、Inductor、TVM）都会把「多个小算子合并成一个 kernel」，
这是 AI 编译器相对 eager 执行最大的性能来源：减少 kernel 启动开销、
减少 HBM 往返（把中间结果留在寄存器 / shared memory 里）。

本模块实现一个教学版融合器，规则与真实编译器同构：

1. 逐元素链融合：elementwise -> elementwise（如 add -> relu）
2. epilogue 融合：matmul -> elementwise（如 GEMM + bias + relu，类比 CUTLASS epilogue）
3. prologue 归约融合：elementwise -> reduce（如 relu -> sum，中间结果不落显存）
4. 合法性：只有「单消费者」的中间节点才能被融入下游组（否则会产生重复计算），
   这与 XLA 的 fusion 合法性检查、Inductor 的 buffer reuse 检查思想一致
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .graph import Graph, Node, OpKind


@dataclass
class FusionGroup:
    """一组被融合进同一个 kernel 的节点，root 是组内"最后执行"的节点。"""

    nodes: List[Node]
    root: Node
    kind: str  # "elementwise" | "matmul_epilogue" | "reduce_fused"

    @property
    def names(self) -> List[str]:
        return [n.name for n in self.nodes]

    def __repr__(self) -> str:  # pragma: no cover - 展示用
        return f"FusionGroup({self.kind}: {' -> '.join(self.names)})"


def _can_fuse(producer: Node, consumer: Node, users: Dict[int, List[Node]]) -> bool:
    """判断 producer 能否融入 consumer 所在的组。

    三条硬规则（均对应真实编译器的约束）：
    - 结构规则：允许的组合是 elementwise -> elementwise、matmul -> elementwise、
      elementwise -> reduce、reduce -> elementwise（归约结果上的后处理融合）
    - 单消费者规则：producer 的输出若被多个节点使用，融合会导致重复计算，
      只有它是「组输出」或仅被 consumer 使用时才允许
    - 归约不可连续：reduce -> reduce 不允许，归约之后的 shape 已变，无法共享 tile
    """
    # 结构规则
    if producer.kind == OpKind.ELEMENTWISE:
        ok_consumer = consumer.kind in (OpKind.ELEMENTWISE, OpKind.REDUCE)
    elif producer.kind == OpKind.MATMUL:
        ok_consumer = consumer.kind == OpKind.ELEMENTWISE
    elif producer.kind == OpKind.REDUCE:
        ok_consumer = consumer.kind == OpKind.ELEMENTWISE
    else:
        ok_consumer = False
    if not ok_consumer:
        return False
    # 单消费者规则
    return len(users[producer.id]) == 1


def _group_kind(nodes: List[Node]) -> str:
    kinds = {n.kind for n in nodes}
    if OpKind.MATMUL in kinds:
        return "matmul_epilogue"
    if OpKind.REDUCE in kinds:
        return "reduce_fused"
    return "elementwise"


def fuse(graph: Graph) -> List[FusionGroup]:
    """对整图做一次贪心融合扫描，返回融合组列表（按 root 拓扑序）。

    算法（自底向上，类似 Inductor 的 foreach node 扫描）：
    1. 统计每个节点的消费者数
    2. 对每个非输入节点，若其唯一消费者存在且满足 _can_fuse，
       则把 producer 挂到 consumer 所在组
    3. 组内保持拓扑序，root 为最后节点
    """
    users = graph.users()
    # 每个计算节点先自成一组；owner: node.id -> 组下标
    groups: List[List[Node]] = []
    owner: Dict[int, int] = {}

    for node in graph.topological_order():
        if node.kind in (OpKind.PLACEHOLDER, OpKind.CONSTANT):
            continue
        owner[node.id] = len(groups)
        groups.append([node])

    for node in graph.topological_order():
        if node.kind in (OpKind.PLACEHOLDER, OpKind.CONSTANT):
            continue
        consumers = users[node.id]
        if len(consumers) != 1:
            continue
        consumer = consumers[0]
        if consumer.kind in (OpKind.PLACEHOLDER, OpKind.CONSTANT):
            continue
        if not _can_fuse(node, consumer, users):
            continue
        # 把 node 所在组合并进 consumer 所在组
        src, dst = owner[node.id], owner[consumer.id]
        if src == dst:
            continue
        merged = groups[src] + groups[dst]  # producer 在前，保持拓扑序
        groups[dst] = merged
        groups[src] = []
        for n in merged:
            owner[n.id] = dst

    out: List[FusionGroup] = []
    for g in groups:
        if not g:
            continue
        root = g[-1]
        out.append(FusionGroup(nodes=g, root=root, kind=_group_kind(g)))
    # 按 root 的拓扑位置排序，保证输出稳定
    pos = {n.id: i for i, n in enumerate(graph.topological_order())}
    out.sort(key=lambda fg: pos[fg.root.id])
    return out


def fused_count(graph: Graph) -> Dict[str, int]:
    """统计融合结果：原始计算节点数、融合后 kernel 数、各类组数量。"""
    groups = fuse(graph)
    compute_nodes = [n for n in graph.nodes if n.kind not in (OpKind.PLACEHOLDER, OpKind.CONSTANT)]
    kinds: Dict[str, int] = {}
    for g in groups:
        kinds[g.kind] = kinds.get(g.kind, 0) + 1
    return {
        "nodes": len(compute_nodes),
        "kernels": len(groups),
        **{f"group_{k}": v for k, v in sorted(kinds.items())},
    }


def explain_non_fusion(graph: Graph) -> List[str]:
    """对每个「未融合」的 producer-consumer 边给出原因（教学用诊断）。"""
    users = graph.users()
    reasons: List[str] = []
    for node in graph.topological_order():
        if node.kind in (OpKind.PLACEHOLDER, OpKind.CONSTANT):
            continue
        consumers = users[node.id]
        if len(consumers) > 1:
            reasons.append(f"%{node.name} 有 {len(consumers)} 个消费者，融合会导致重复计算")
            continue
        if not consumers:
            continue
        consumer = consumers[0]
        if _can_fuse(node, consumer, users):
            continue
        if node.kind == OpKind.REDUCE:
            reasons.append(f"%{node.name}(reduce) 的消费者是 {consumer.op}，归约后形状已变化，无法共享 tile")
        elif node.kind == OpKind.MATMUL and consumer.kind != OpKind.ELEMENTWISE:
            reasons.append(f"%{node.name}(matmul) 的消费者是 {consumer.op}，非逐元素算子，无法做 epilogue 融合")
        else:
            reasons.append(f"%{node.name}({node.op}) -> %{consumer.name}({consumer.op}) 不满足融合结构规则")
    return reasons
