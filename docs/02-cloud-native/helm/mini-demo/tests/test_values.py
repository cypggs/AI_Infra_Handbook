import pytest
from helm_mini.values import deep_merge, merge_values


def test_deep_merge_map_recursive():
    dst = {"a": {"x": 1, "y": 2}}
    src = {"a": {"y": 9, "z": 3}}
    assert deep_merge(dst, src) == {"a": {"x": 1, "y": 9, "z": 3}}


def test_deep_merge_list_is_replaced_not_merged():
    # Helm 的关键语义：list 整体替换（不按下标合并）
    dst = {"env": [{"name": "A", "value": "1"}, {"name": "B", "value": "2"}]}
    src = {"env": [{"name": "C", "value": "3"}]}
    assert deep_merge(dst, src) == {"env": [{"name": "C", "value": "3"}]}


def test_merge_values_priority():
    base = {"replicaCount": 2, "image": {"tag": "0.6.3"}}
    layer1 = {"image": {"tag": "0.7.0"}}
    layer2 = {"image": {"tag": "0.8.0"}, "replicaCount": 4}
    out = merge_values([base], [layer1, layer2])
    # 后者覆盖前者：layer2 的 image.tag 胜出
    assert out["image"]["tag"] == "0.8.0"
    assert out["replicaCount"] == 4


def test_merge_values_skips_none_layers():
    out = merge_values([{"a": 1}], None, [{"b": 2}])
    assert out == {"a": 1, "b": 2}


def test_merge_does_not_mutate_inputs():
    base = {"a": {"x": 1}}
    snapshot = {"a": {"x": 1}}
    merge_values([base], [{"a": {"y": 2}}])
    assert base == snapshot  # base 不被改


def test_nested_list_under_overridden_key():
    base = {"ingress": {"enabled": False, "hosts": ["a"]}}
    over = {"ingress": {"enabled": True, "hosts": ["b", "c"]}}
    out = merge_values([base], [over])
    assert out["ingress"] == {"enabled": True, "hosts": ["b", "c"]}
