import numpy as np
import pytest

from ai_compiler_mini.fusion import explain_non_fusion, fuse, fused_count
from ai_compiler_mini.graph import Graph


def build_chain():
    """x -> relu -> sigmoid -> sum(axis=1)，纯 elementwise 链 + 归约。"""
    g = Graph()
    x = g.placeholder("x", (8, 16))
    r = g.elementwise("relu", x, name="relu")
    s = g.elementwise("sigmoid", r, name="sig")
    t = g.reduce("sum", s, axis=1, name="rowsum")
    return g


def build_matmul_epilogue():
    """x @ W + bias -> relu：GEMM epilogue 融合。"""
    g = Graph()
    x = g.placeholder("x", (16, 8))
    w = g.constant_with_value("W", np.ones((8, 8)))
    b = g.constant_with_value("bias", np.ones((8,)))
    mm = g.matmul(x, w, name="mm")
    add = g.elementwise("add", mm, b, name="bias_add")
    relu = g.elementwise("relu", add, name="relu")
    return g


def test_elementwise_chain_fuses_into_one_group():
    g = build_chain()
    groups = fuse(g)
    assert len(groups) == 1
    assert groups[0].kind == "reduce_fused"
    assert groups[0].names == ["relu", "sig", "rowsum"]


def test_matmul_epilogue_fusion():
    g = build_matmul_epilogue()
    groups = fuse(g)
    assert len(groups) == 1
    assert groups[0].kind == "matmul_epilogue"
    assert groups[0].names == ["mm", "bias_add", "relu"]


def test_matmul_without_epilogue_stands_alone():
    g = Graph()
    x = g.placeholder("x", (4, 4))
    w = g.constant_with_value("W", np.ones((4, 4)))
    y = g.constant_with_value("y", np.ones((4, 4)))
    mm = g.matmul(x, w, name="mm")
    g.matmul(mm, y, name="mm2")
    groups = fuse(g)
    assert len(groups) == 2
    assert {fg.root.name for fg in groups} == {"mm", "mm2"}


def test_multi_consumer_blocks_fusion():
    g = Graph()
    x = g.placeholder("x", (8, 8))
    r = g.elementwise("relu", x, name="relu")
    g.elementwise("sigmoid", r, name="sig")
    g.elementwise("exp", r, name="exp")
    groups = fuse(g)
    # relu 有两个消费者，不能融进任何一个下游组
    sig_group = next(fg for fg in groups if fg.root.name == "sig")
    exp_group = next(fg for fg in groups if fg.root.name == "exp")
    assert "relu" not in sig_group.names
    assert "relu" not in exp_group.names
    assert len(groups) == 3


def test_reduce_is_group_boundary():
    g = Graph()
    x = g.placeholder("x", (8, 8))
    s = g.reduce("sum", x, axis=1, name="rowsum")
    g.elementwise("relu", s, name="relu")  # reduce 下游可以继续融
    groups = fuse(g)
    assert len(groups) == 1
    assert groups[0].names == ["rowsum", "relu"]
    assert groups[0].kind == "reduce_fused"


def test_reduce_cannot_merge_upstream():
    g = Graph()
    x = g.placeholder("x", (8, 8))
    s = g.reduce("sum", x, axis=1, name="rowsum")
    g.reduce("sum", s, axis=0, name="total")
    groups = fuse(g)
    # reduce -> reduce 不允许（结构规则），保持两个组
    assert len(groups) == 2


def test_diamond_from_matmul_not_fused():
    """matmul 输出同时给 relu 和 rowsum：epilogue 不成立，mm 独立成组。"""
    g = Graph()
    x = g.placeholder("x", (8, 8))
    w = g.constant_with_value("W", np.ones((8, 8)))
    mm = g.matmul(x, w, name="mm")
    g.elementwise("relu", mm, name="relu")
    g.reduce("sum", mm, axis=1, name="rowsum")
    groups = fuse(g)
    roots = sorted(fg.root.name for fg in groups)
    assert roots == ["mm", "relu", "rowsum"]
    mm_group = next(fg for fg in groups if fg.root.name == "mm")
    assert mm_group.names == ["mm"]  # 多消费者，不能融进任何下游组


def test_broadcast_bias_fuses_with_matmul():
    g = Graph()
    x = g.placeholder("x", (8, 4))
    w = g.constant_with_value("W", np.ones((4, 8)))
    b = g.constant_with_value("bias", np.ones((8,)))
    mm = g.matmul(x, w, name="mm")
    add = g.elementwise("add", mm, b, name="bias_add")
    groups = fuse(g)
    assert len(groups) == 1
    assert groups[0].root.name == "bias_add"


def test_fused_count_statistics():
    g = build_matmul_epilogue()
    stats = fused_count(g)
    assert stats["nodes"] == 3  # mm, bias_add, relu
    assert stats["kernels"] == 1
    assert stats["group_matmul_epilogue"] == 1


def test_explain_non_fusion_reports_multi_consumer():
    g = Graph()
    x = g.placeholder("x", (8, 8))
    r = g.elementwise("relu", x, name="relu")
    g.elementwise("sigmoid", r, name="a")
    g.elementwise("exp", r, name="b")
    reasons = explain_non_fusion(g)
    assert any("relu" in r_ and "2 个消费者" in r_ for r_ in reasons)


def test_group_nodes_topologically_ordered():
    g = build_matmul_epilogue()
    (fg,) = fuse(g)
    positions = {n.name: i for i, n in enumerate(g.topological_order())}
    idx = [positions[nm] for nm in fg.names]
    assert idx == sorted(idx)
