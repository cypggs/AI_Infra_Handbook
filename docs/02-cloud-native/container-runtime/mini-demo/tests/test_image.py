"""test_image — 层摘要确定性、manifest、多架构选择。"""
from crt_mini.image import Layer, ImageConfig, Image, ManifestEntry, ManifestList, digest


def test_layer_digest_is_deterministic_and_content_addressed():
    a = Layer(files={"/a": "1"})
    b = Layer(files={"/a": "1"})
    c = Layer(files={"/a": "2"})
    assert a.digest == b.digest          # 相同内容 → 相同 digest
    assert a.digest != c.digest          # 不同内容 → 不同 digest
    assert a.digest.startswith("sha256:")


def test_layer_parent_affects_digest():
    a = Layer(files={"/x": "1"}, parent=None)
    b = Layer(files={"/x": "1"}, parent="sha256:parent1")
    assert a.digest != b.digest          # 父不同 → digest 不同


def test_image_manifest_lists_layers_in_order():
    l1 = Layer(files={"/1": "a"})
    l2 = Layer(files={"/2": "b"}, parent=l1.digest)
    img = Image(config=ImageConfig(entrypoint=["run"]), layers=[l1, l2])
    m = img.manifest
    assert m["layers"] == [l1.digest, l2.digest]
    assert m["config"] == img.config.digest


def test_manifest_list_selects_platform():
    amd = Image(config=ImageConfig(), layers=[Layer(files={"/os": "amd64"})])
    arm = Image(config=ImageConfig(), layers=[Layer(files={"/os": "arm64"})])
    ml = ManifestList(entries=[ManifestEntry("linux/amd64", amd), ManifestEntry("linux/arm64", arm)])
    assert ml.select("linux/amd64") is amd
    assert ml.select("linux/arm64") is arm
    assert ml.platforms == ["linux/amd64", "linux/arm64"]
    try:
        ml.select("linux/ppc64le")
    except KeyError:
        return
    assert False, "expected KeyError for unsupported platform"


def test_digest_is_stable_across_calls():
    assert digest("a", 1, [1, 2]) == digest("a", 1, [1, 2])
