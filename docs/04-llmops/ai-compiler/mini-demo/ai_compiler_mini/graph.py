"""计算图 IR（Intermediate Representation，中间表示）。

模拟真实 AI 编译器（如 TorchInductor、XLA、TVM Relax）的第一层抽象：
把一段计算表示成「节点 = 算子实例，边 = 张量数据流」的有向无环图。

本模块只依赖 numpy，完全 CPU 可运行，语义上对齐真实编译器的 graph IR：

- Node 持有算子类型、输入边、属性（如 reduce 的 axis）与推导出的 shape
- Graph 保证拓扑有序，支持 numpy 参考执行（相当于「解释执行」后端），
  供融合 / 调优 / 模拟执行的结果做正确性对拍
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np


class OpKind(Enum):
    """算子类别。真实编译器（MLIR/XLA HLO/TVM Relax）都有类似的一级分类。"""

    PLACEHOLDER = "placeholder"  # 图输入（类比 torch.fx 的 placeholder）
    CONSTANT = "constant"  # 常量（权重 / bias）
    ELEMENTWISE = "elementwise"  # 逐元素算子：add / mul / relu ...
    MATMUL = "matmul"  # 矩阵乘（含 bias 时仍是独立节点，交给融合 pass）
    REDUCE = "reduce"  # 归约：sum / max / mean，带 axis 属性


# ---------------------------------------------------------------------------
# 逐元素算子注册表：名称 -> (numpy 实现, 是否支持广播二元)
# ---------------------------------------------------------------------------

_UNARY_FUNCS: Dict[str, Callable[[np.ndarray], np.ndarray]] = {
    "relu": lambda x: np.maximum(x, 0),
    "exp": np.exp,
    "tanh": np.tanh,
    "sigmoid": lambda x: 1.0 / (1.0 + np.exp(-x)),
    "sqrt": np.sqrt,
    "neg": np.negative,
    "abs": np.abs,
}

_BINARY_FUNCS: Dict[str, Callable[[np.ndarray, np.ndarray], np.ndarray]] = {
    "add": np.add,
    "mul": np.multiply,
    "sub": np.subtract,
    "div": np.divide,
    "max": np.maximum,
    "min": np.minimum,
}

_REDUCE_FUNCS: Dict[str, Callable[..., np.ndarray]] = {
    "sum": np.sum,
    "max": np.max,
    "mean": np.mean,
}


def elementwise_funcs() -> List[str]:
    """返回所有已注册的逐元素算子名。"""
    return sorted(_UNARY_FUNCS) + sorted(_BINARY_FUNCS)


def reduce_funcs() -> List[str]:
    """返回所有已注册的归约算子名。"""
    return sorted(_REDUCE_FUNCS)


def _broadcast_shape(a: Sequence[int], b: Sequence[int]) -> Tuple[int, ...]:
    """numpy 风格的广播规则（从尾部对齐）。"""
    ra, rb = list(a)[::-1], list(b)[::-1]
    out: List[int] = []
    for i in range(max(len(ra), len(rb))):
        da = ra[i] if i < len(ra) else 1
        db = rb[i] if i < len(rb) else 1
        if da == db or da == 1 or db == 1:
            out.append(max(da, db))
        else:
            raise ValueError(f"无法广播的形状: {tuple(a)} vs {tuple(b)}")
    return tuple(out[::-1])


@dataclass
class Node:
    """计算图中的一个节点（一次算子调用）。"""

    id: int
    name: str
    kind: OpKind
    op: str  # 具体算子名，如 "add" / "matmul" / "sum"
    inputs: List["Node"] = field(default_factory=list)
    attrs: Dict[str, Any] = field(default_factory=dict)
    shape: Tuple[int, ...] = ()
    dtype: str = "float32"

    def __repr__(self) -> str:  # pragma: no cover - 展示用
        ins = ", ".join(n.name for n in self.inputs)
        extra = ""
        if self.attrs:
            extra = " {" + ", ".join(f"{k}={v}" for k, v in self.attrs.items()) + "}"
        return f"%{self.name} = {self.op}({ins}) -> {self.shape}{extra}"


class Graph:
    """计算图容器：负责节点创建、shape 推导、拓扑序与参考执行。"""

    def __init__(self) -> None:
        self.nodes: List[Node] = []
        self._by_name: Dict[str, Node] = {}

    # -- 图构造 -----------------------------------------------------------

    def _add(self, node: Node) -> Node:
        self.nodes.append(node)
        self._by_name[node.name] = node
        return node

    def placeholder(self, name: str, shape: Sequence[int], dtype: str = "float32") -> Node:
        if not shape:
            raise ValueError("placeholder shape 不能为空")
        return self._add(Node(len(self.nodes), name, OpKind.PLACEHOLDER, "input", shape=tuple(shape), dtype=dtype))

    def constant(self, name: str, value: np.ndarray) -> Node:
        arr = np.asarray(value, dtype=np.float64)
        return self._add(
            Node(
                len(self.nodes),
                name,
                OpKind.CONSTANT,
                "const",
                attrs={"value": arr},
                shape=tuple(arr.shape),
                dtype=str(arr.dtype),
            )
        )

    def constant_with_value(self, name: str, value: np.ndarray) -> Node:
        """创建常量节点（数值直接保存在节点 attrs 中，eval 时取用）。"""
        return self.constant(name, value)

    def elementwise(self, op: str, a: Node, b: Optional[Node] = None, name: Optional[str] = None) -> Node:
        """创建逐元素节点。一元算子只传 a；二元算子传 a、b（支持广播）。"""
        if op in _UNARY_FUNCS:
            if b is not None:
                raise ValueError(f"{op} 是一元算子，不接受第二个输入")
            shape = a.shape
            inputs = [a]
        elif op in _BINARY_FUNCS:
            if b is None:
                raise ValueError(f"{op} 是二元算子，需要第二个输入")
            shape = _broadcast_shape(a.shape, b.shape)
            inputs = [a, b]
        else:
            raise ValueError(f"未知逐元素算子: {op}，可选: {elementwise_funcs()}")
        return self._add(
            Node(len(self.nodes), name or f"{op}{len(self.nodes)}", OpKind.ELEMENTWISE, op, inputs=inputs, shape=shape)
        )

    def matmul(self, a: Node, b: Node, name: Optional[str] = None) -> Node:
        """创建 matmul 节点：a (..., M, K) x b (..., K, N) -> (..., M, N)。"""
        if a.ndim < 2 or b.ndim < 2:
            raise ValueError("matmul 输入至少是二维")
        if a.shape[-1] != b.shape[-2]:
            raise ValueError(f"matmul 维度不匹配: {a.shape} x {b.shape}")
        batch = _broadcast_shape(a.shape[:-2], b.shape[:-2])
        shape = batch + (a.shape[-2], b.shape[-1])
        return self._add(
            Node(len(self.nodes), name or f"mm{len(self.nodes)}", OpKind.MATMUL, "matmul", inputs=[a, b], shape=shape)
        )

    def reduce(self, op: str, a: Node, axis: int = -1, keepdims: bool = True, name: Optional[str] = None) -> Node:
        """创建归约节点，axis 为待消去的维度。"""
        if op not in _REDUCE_FUNCS:
            raise ValueError(f"未知归约算子: {op}，可选: {reduce_funcs()}")
        axis = axis % a.ndim
        if keepdims:
            shape = tuple(1 if i == axis else d for i, d in enumerate(a.shape))
        else:
            shape = tuple(d for i, d in enumerate(a.shape) if i != axis)
        return self._add(
            Node(
                len(self.nodes),
                name or f"{op}{len(self.nodes)}",
                OpKind.REDUCE,
                op,
                inputs=[a],
                attrs={"axis": axis, "keepdims": keepdims},
                shape=shape,
            )
        )

    # -- 查询 -------------------------------------------------------------

    @property
    def inputs(self) -> List[Node]:
        """placeholder 节点（图的外部输入）。"""
        return [n for n in self.nodes if n.kind == OpKind.PLACEHOLDER]

    @property
    def constants(self) -> List[Node]:
        return [n for n in self.nodes if n.kind == OpKind.CONSTANT]

    def get(self, name: str) -> Node:
        return self._by_name[name]

    def users(self) -> Dict[int, List[Node]]:
        """node.id -> 使用该节点输出的节点列表。"""
        out: Dict[int, List[Node]] = {n.id: [] for n in self.nodes}
        for n in self.nodes:
            for inp in n.inputs:
                out[inp.id].append(n)
        return out

    def topological_order(self) -> List[Node]:
        """Kahn 拓扑排序；图构造时即保证有序，这里做防御性校验。"""
        order: List[Node] = []
        seen: set = set()
        for n in self.nodes:
            for inp in n.inputs:
                if inp.id not in seen:
                    raise ValueError(f"节点 {n.name} 的输入 {inp.name} 未先定义（非拓扑序）")
            seen.add(n.id)
            order.append(n)
        return order

    # -- 参考执行 ---------------------------------------------------------

    def eval(self, feed: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """用 numpy 逐个节点解释执行，返回每个节点的值（相当于 eager 后端）。"""
        env: Dict[str, np.ndarray] = {}
        for n in self.topological_order():
            if n.kind == OpKind.PLACEHOLDER:
                if n.name not in feed:
                    raise KeyError(f"缺少输入 {n.name} 的数据")
                env[n.name] = np.asarray(feed[n.name], dtype=np.float64)
            elif n.kind == OpKind.CONSTANT:
                env[n.name] = np.asarray(n.attrs["value"], dtype=np.float64)
            elif n.kind == OpKind.ELEMENTWISE:
                if n.op in _UNARY_FUNCS:
                    env[n.name] = _UNARY_FUNCS[n.op](env[n.inputs[0].name])
                else:
                    env[n.name] = _BINARY_FUNCS[n.op](env[n.inputs[0].name], env[n.inputs[1].name])
            elif n.kind == OpKind.MATMUL:
                env[n.name] = env[n.inputs[0].name] @ env[n.inputs[1].name]
            elif n.kind == OpKind.REDUCE:
                fn = _REDUCE_FUNCS[n.op]
                r = fn(env[n.inputs[0].name], axis=n.attrs["axis"], keepdims=n.attrs["keepdims"])
                env[n.name] = np.asarray(r, dtype=np.float64)
        return env

    # -- 展示 -------------------------------------------------------------

    def dump(self) -> str:
        """打印类似 MLIR / torch.fx 的文本形式 IR。"""
        lines = ["graph {"]
        for n in self.topological_order():
            ins = ", ".join(f"%{i.name}" for i in n.inputs)
            suffix = ""
            if n.kind == OpKind.REDUCE:
                suffix = f" axis={n.attrs['axis']} keepdims={n.attrs['keepdims']}"
            lines.append(f"  %{n.name} = {n.op}({ins}) : {n.shape}{suffix}")
        lines.append("}")
        return "\n".join(lines)


# Node.ndim 便捷属性
Node.ndim = property(lambda self: len(self.shape))  # type: ignore[attr-defined]
