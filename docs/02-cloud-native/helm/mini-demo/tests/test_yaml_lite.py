import pytest
from helm_mini.yaml_lite import dump, load_all, dump_scalar


def test_scalar_types_roundtrip():
    src = """
a: 1
b: hello
c: "vllm:0.6.3"
d: true
e: null
f: 3.14
g: ""
"""
    obj = load_all(src)[0]
    assert obj == {"a": 1, "b": "hello", "c": "vllm:0.6.3",
                   "d": True, "e": None, "f": 3.14, "g": ""}


def test_colon_in_value_is_quoted():
    assert dump_scalar("vllm:0.6.3").startswith('"')
    assert load_all('x: "vllm:0.6.3"')[0]["x"] == "vllm:0.6.3"


def test_nested_map_roundtrip():
    obj = {"spec": {"replicas": 2, "selector": {"matchLabels": {"app": "x"}}}}
    assert load_all(dump(obj))[0] == obj


def test_list_of_scalars_roundtrip():
    obj = {"items": ["a", "b", 3, True]}
    assert load_all(dump(obj))[0] == obj


def test_list_of_inline_maps_roundtrip():
    obj = {
        "containers": [
            {"name": "server", "image": "x:1", "ports": [
                {"name": "http", "containerPort": 8000, "protocol": "TCP"}]},
        ]
    }
    assert load_all(dump(obj))[0] == obj


def test_multidoc():
    text = dump({"kind": "A", "metadata": {"name": "a"}}) + "\n---\n" + \
        dump({"kind": "B", "metadata": {"name": "b"}})
    docs = load_all(text)
    assert len(docs) == 2
    assert [d["kind"] for d in docs] == ["A", "B"]


def test_resource_policy_value_preserved():
    obj = {"metadata": {"name": "x", "annotations": {"helm.sh/resource-policy": "keep"}}}
    assert load_all(dump(obj))[0] == obj


def test_deeply_nested_realistic_deployment():
    obj = {
        "apiVersion": "apps/v1", "kind": "Deployment",
        "metadata": {"name": "r"},
        "spec": {"replicas": 2, "template": {"spec": {"containers": [
            {"name": "c", "image": "i:1",
             "env": [{"name": "A", "value": "1"}, {"name": "B", "value": "2"}],
             "resources": {"limits": {"nvidia.com/gpu": 1}, "requests": {"cpu": "4"}}},
        ]}}},
    }
    assert load_all(dump(obj))[0] == obj
