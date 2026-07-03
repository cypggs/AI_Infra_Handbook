"""test_snapshot — 联合挂载、快照链、copy-on-write 代价。"""
from crt_mini.snapshot import Snapshotter
from crt_mini.image import Layer


def _two_layer_snapshotter():
    snap = Snapshotter()
    base = Layer(files={"/etc/os-release": "Alpine", "/bin/sh": "#!sh", "/lib/libc": "musl"})
    app = Layer(files={"/usr/bin/python3": "#!py", "/etc/config": "BASE"}, parent=base.digest)
    snap.commit_layer("base", base, parent=None)
    snap.commit_layer("app", app, parent="base")
    return snap


def test_merged_overlays_upper_on_lower():
    snap = _two_layer_snapshotter()
    snap.prepare("active", parent="app")
    view = snap.merged("active")
    # 下层 base + app 的所有文件都出现在联合视图里
    assert view["/etc/os-release"] == "Alpine"
    assert view["/usr/bin/python3"] == "#!py"


def test_write_new_file_no_cow():
    snap = _two_layer_snapshotter()
    snap.prepare("active", parent="app")
    cow = snap.write("active", "/var/log/x", "hello")
    assert cow["copied_from_lower"] is False
    assert cow["copied_bytes"] == 0
    assert snap.merged("active")["/var/log/x"] == "hello"


def test_write_existing_file_triggers_full_copy_up():
    """改一个存在于下层的文件（哪怕 1 字节），整个文件被 copy-up。"""
    snap = _two_layer_snapshotter()
    snap.prepare("active", parent="app")
    old = snap.merged("active")["/etc/config"]  # "BASE"，4 字节
    cow = snap.write("active", "/etc/config", "X")  # 只覆盖 1 字节
    assert cow["copied_from_lower"] is True
    assert cow["copied_bytes"] == len(old)        # 整个旧文件大小
    assert cow["written_bytes"] == 1
    assert snap.merged("active")["/etc/config"] == "X"


def test_commit_layer_is_idempotent():
    snap = Snapshotter()
    base = Layer(files={"/a": "1"})
    snap.commit_layer("base", base, parent=None)
    snap.commit_layer("base", base, parent=None)  # 同名 → 复用，不覆盖
    assert len(snap.snaps) == 1


def test_remove_snapshot():
    snap = _two_layer_snapshotter()
    snap.prepare("active", parent="app")
    snap.remove("active")
    assert "active" not in snap.snaps
