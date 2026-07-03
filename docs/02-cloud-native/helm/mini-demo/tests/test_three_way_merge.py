import pytest
from helm_mini.kube import three_way_merge


def test_chart_unchanged_field_preserves_manual_change():
    # 经典案例：手动 scale 到 10，chart 没改 replicas -> 保留 10
    old = {"spec": {"replicas": 2, "image": "old"}}
    live = {"spec": {"replicas": 10, "image": "old"}}
    new = {"spec": {"replicas": 2, "image": "new"}}
    merged = three_way_merge(old, live, new)
    assert merged["spec"]["replicas"] == 10   # 手动改动保留
    assert merged["spec"]["image"] == "new"   # chart 改动应用


def test_chart_changed_field_overrides_manual():
    old = {"spec": {"replicas": 2}}
    live = {"spec": {"replicas": 10}}
    new = {"spec": {"replicas": 4}}   # chart 这次主动改成 4
    merged = three_way_merge(old, live, new)
    assert merged["spec"]["replicas"] == 4


def test_chart_removed_field_cleaned_when_unchanged_by_user():
    old = {"a": 1, "b": 2}
    live = {"a": 1, "b": 2}
    new = {"a": 1}                     # chart 删了 b
    merged = three_way_merge(old, live, new)
    assert "b" not in merged           # 用户没改 -> 删除


def test_chart_removed_field_kept_when_user_changed():
    old = {"a": 1, "b": 2}
    live = {"a": 1, "b": 99}           # 用户把 b 改成 99
    new = {"a": 1}                     # chart 删了 b
    merged = three_way_merge(old, live, new)
    assert merged["b"] == 99           # 用户改动保留


def test_user_added_field_preserved():
    old = {"replicas": 2}
    live = {"replicas": 2, "foo": "bar"}   # 用户加了个 label
    new = {"replicas": 2}
    merged = three_way_merge(old, live, new)
    assert merged["foo"] == "bar"


def test_chart_added_field_applied():
    old = {"a": 1}
    live = {"a": 1}
    new = {"a": 1, "b": 2}             # chart 新增 b
    merged = three_way_merge(old, live, new)
    assert merged["b"] == 2


def test_nested_dict_recursive_merge():
    old = {"spec": {"a": 1, "b": 2}}
    live = {"spec": {"a": 1, "b": 2, "c": 3}}   # 用户加 spec.c
    new = {"spec": {"a": 9, "b": 2}}            # chart 改 a，没动 b
    merged = three_way_merge(old, live, new)
    assert merged["spec"]["a"] == 9             # chart 改动
    assert merged["spec"]["b"] == 2
    assert merged["spec"]["c"] == 3             # 用户加的保留


def test_list_treated_as_replace():
    # list：old==new 时保留 live（用户改的 list），old!=new 用 new
    old = {"env": [{"name": "A"}]}
    live = {"env": [{"name": "X"}]}     # 用户改了 list
    new = {"env": [{"name": "A"}]}      # chart 没改 list
    merged = three_way_merge(old, live, new)
    assert merged["env"] == [{"name": "X"}]   # 保留用户的（本 demo 简化语义）


def test_empty_old_treated_as_new_install():
    old = {}
    live = {}
    new = {"spec": {"replicas": 3}}
    merged = three_way_merge(old, live, new)
    assert merged == {"spec": {"replicas": 3}}
