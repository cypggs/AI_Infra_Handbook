import numpy as np
import pytest

from ai_compiler_mini.graph import Graph, OpKind


@pytest.fixture()
def simple_graph():
    g = Graph()
    x = g.placeholder("x", (4, 8))
    w = g.constant_with_value("W", np.ones((8, 16)))
    mm = g.matmul(x, w, name="mm")
    relu = g.elementwise("relu", mm, name="relu")
    return g, x, mm, relu


def test_empty_placeholder_shape_rejected():
    g = Graph()
    with pytest.raises(ValueError):
        g.placeholder("x", ())


def test_constant_keeps_value_and_shape():
    g = Graph()
    w = g.constant_with_value("W", np.arange(6.0).reshape(2, 3))
    assert w.shape == (2, 3)
    assert w.kind == OpKind.CONSTANT
    assert np.array_equal(w.attrs["value"], np.arange(6.0).reshape(2, 3))


def test_elementwise_unary_shape_preserved(simple_graph):
    g, x, _, _ = simple_graph
    r = g.elementwise("relu", x)
    assert r.shape == x.shape
    assert r.kind == OpKind.ELEMENTWISE


def test_elementwise_binary_broadcast():
    g = Graph()
    x = g.placeholder("x", (4, 8))
    b = g.constant_with_value("bias", np.zeros((8,)))
    out = g.elementwise("add", x, b)
    assert out.shape == (4, 8)


def test_elementwise_broadcast_both_sides():
    g = Graph()
    a = g.placeholder("a", (2, 1, 4))
    b = g.placeholder("b", (1, 3, 1))
    out = g.elementwise("mul", a, b)
    assert out.shape == (2, 3, 4)


def test_elementwise_incompatible_broadcast_raises():
    g = Graph()
    a = g.placeholder("a", (3,))
    b = g.placeholder("b", (4,))
    with pytest.raises(ValueError):
        g.elementwise("add", a, b)


def test_unknown_elementwise_raises():
    g = Graph()
    x = g.placeholder("x", (2,))
    with pytest.raises(ValueError):
        g.elementwise("frobnicate", x)


def test_matmul_shape_inference():
    g = Graph()
    a = g.placeholder("a", (8, 16))
    b = g.placeholder("b", (16, 4))
    mm = g.matmul(a, b)
    assert mm.shape == (8, 4)
    assert mm.kind == OpKind.MATMUL


def test_matmul_dim_mismatch_raises():
    g = Graph()
    a = g.placeholder("a", (8, 16))
    b = g.placeholder("b", (8, 16))
    with pytest.raises(ValueError):
        g.matmul(a, b)


def test_reduce_keepdims_shape():
    g = Graph()
    x = g.placeholder("x", (4, 8))
    s = g.reduce("sum", x, axis=1, keepdims=True)
    assert s.shape == (4, 1)
    assert s.attrs["axis"] == 1


def test_reduce_no_keepdims_shape():
    g = Graph()
    x = g.placeholder("x", (4, 8))
    s = g.reduce("sum", x, axis=1, keepdims=False)
    assert s.shape == (4,)


def test_users_mapping(simple_graph):
    g, x, mm, relu = simple_graph
    users = g.users()
    assert [n.name for n in users[x.id]] == ["mm"]
    assert [n.name for n in users[mm.id]] == ["relu"]
    assert users[relu.id] == []


def test_eval_matches_numpy(simple_graph):
    g, x, mm, relu = simple_graph
    feed = {"x": np.arange(32.0).reshape(4, 8) - 16.0}
    env = g.eval(feed)
    expected = np.maximum(feed["x"] @ np.ones((8, 16)), 0)
    assert np.allclose(env["relu"], expected)


def test_eval_missing_feed_raises(simple_graph):
    g, _, _, _ = simple_graph
    with pytest.raises(KeyError):
        g.eval({})
