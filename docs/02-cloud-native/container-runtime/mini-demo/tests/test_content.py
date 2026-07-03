"""test_content — Content Store 内容寻址去重。"""
from crt_mini.content import ContentStore
from crt_mini.image import Layer


def test_put_dedups_by_key():
    cs = ContentStore()
    layer = Layer(files={"/a": "1"})
    assert cs.put(layer.digest, layer) is True   # 新增
    assert cs.put(layer.digest, layer) is False  # 去重，跳过
    assert cs.size() == 1


def test_has_and_get():
    cs = ContentStore()
    cs.put("sha256:k1", "blob")
    assert cs.has("sha256:k1")
    assert not cs.has("sha256:nope")
    assert cs.get("sha256:k1") == "blob"


def test_list():
    cs = ContentStore()
    cs.put("sha256:k1", 1)
    cs.put("sha256:k2", 2)
    assert set(cs.list()) == {"sha256:k1", "sha256:k2"}
