"""test_runtime — OCI create/start/exec 生命周期、COW、OOM 停容器。"""
from crt_mini.runtime import OCIConfig, Container
from crt_mini.snapshot import Snapshotter
from crt_mini.image import Layer


def _make_container(observer=None, readonly=False, **kw):
    snap = Snapshotter()
    base = Layer(files={"/etc/os-release": "Linux", "/bin/sh": "#!sh", "/app/big": "X" * 100})
    snap.commit_layer("base", base, parent=None)
    snap.prepare("active", parent="base")
    cfg = OCIConfig(
        args=["python3", "app.py"],
        snapshot_key="active",
        readonly_rootfs=readonly,
        **kw,
    )
    return Container("c1", cfg, snap, observer=observer)


def test_lifecycle_create_then_start():
    c = _make_container()
    assert c.state == "creating"
    c.create()
    assert c.state == "created"
    # create 后 rootfs 已就绪，但用户进程未运行
    assert "/etc/os-release" in c.rootfs
    assert c.namespaces.pid.visible() == []  # PID 1 尚未运行
    c.start()
    assert c.state == "running"
    assert c.pid_ns_counter == 1
    assert c.namespaces.pid.visible()  # start 后 PID 1 进入 pid namespace


def test_start_requires_created():
    c = _make_container()
    import pytest
    with pytest.raises(RuntimeError):
        c.start()  # 未 create


def test_exec_increments_pid():
    c = _make_container()
    c.create()
    c.start()
    r = c.exec(["/bin/sh"])
    assert r["pid"] == 2
    r2 = c.exec(["ls"])
    assert r2["pid"] == 3


def test_write_existing_file_copies_up():
    c = _make_container()
    c.create()
    c.start()
    cow = c.write_file("/app/big", "Y")  # 下层有 100 字节文件
    assert cow["copied_from_lower"] is True
    assert cow["copied_bytes"] == 100   # 整个文件 copy-up
    assert cow["written_bytes"] == 1


def test_write_new_file_no_copy_up():
    c = _make_container()
    c.create()
    c.start()
    cow = c.write_file("/var/new", "data")
    assert cow["copied_from_lower"] is False


def test_readonly_rootfs_blocks_write():
    c = _make_container(readonly=True)
    c.create()
    c.start()
    assert c.write_file("/x", "y") == {"error": "read-only rootfs"}


def test_oom_stops_container():
    c = _make_container(memory_max=4096)
    c.create()
    c.start()
    assert c.state == "running"
    c.use_memory(2048)
    res = c.use_memory(4096)  # 超限
    assert res == "oom"
    assert c.state == "stopped"
    assert c.exit_code == 137
    assert c.cgroup.oom_kills == 1


def test_stop_and_delete():
    c = _make_container()
    c.create()
    c.start()
    c.stop("TERM")
    assert c.state == "stopped"
    assert c.exit_code == 0
    c.delete()
    assert c.state == "deleted"
