"""test_engine — 高层运行时：pull 去重、run 全链路、多架构选择。"""
from crt_mini.engine import HighLevelRuntime
from crt_mini.registry import Registry


def _rt():
    return HighLevelRuntime(Registry())


def test_pull_stores_layers_in_content_store():
    rt = _rt()
    rt.pull("docker.io/library/nginx:1.27")
    # config 概念 + 2 层 → content store 至少有 2 个 blob
    assert rt.content.size() == 2
    # 解包成 committed 快照
    committed = [s for s in rt.snapshotter.snaps.values() if s.kind == "committed"]
    assert len(committed) == 2


def test_pull_dedups_identical_layers():
    rt = _rt()
    rt.pull("docker.io/library/nginx:1.27")
    size_before = rt.content.size()
    img = rt.pull("docker.io/library/nginx:1.27")  # 再 pull 同镜像
    size_after = rt.content.size()
    assert size_before == size_after  # 全部命中去重
    last_pull = [e for e in rt.observer if e["event"] == "pull"][-1]
    assert last_pull["new_layers"] == 0
    assert last_pull["shared_layers"] == len(img.layers)


def test_run_creates_and_starts_container():
    rt = _rt()
    c = rt.run("docker.io/library/nginx:1.27", "web")
    assert c.state == "running"
    assert c.id == "web"
    # run = pull + prepare rootfs + create + start，rootfs 来自镜像层
    assert "/usr/sbin/nginx" in c.rootfs
    assert rt.snapshotter.snaps["web:rootfs"].kind == "active"


def test_run_passes_resource_limits_to_cgroup():
    rt = _rt()
    c = rt.run("docker.io/library/nginx:1.27", "web",
               cpu_quota_us=50_000, memory_max=8192, pids_max=64)
    assert c.cgroup.cpu_max == "50000 100000"
    assert c.cgroup.memory_max == 8192
    assert c.cgroup.pids_max == 64


def test_multiarch_pull_selects_platform():
    rt = _rt()
    amd = rt.pull("myreg/ai-server:v1", platform="linux/amd64")
    arm = rt.pull("myreg/ai-server:v1", platform="linux/arm64")
    assert amd.layers[0].files["/etc/os-release"] == "Linux/amd64"
    assert arm.layers[0].files["/etc/os-release"] == "Linux/arm64"
    selects = [e for e in rt.observer if e["event"] == "select-platform"]
    assert {s["platform"] for s in selects} == {"linux/amd64", "linux/arm64"}


def test_unknown_ref_raises():
    rt = _rt()
    try:
        rt.pull("does/not:exist")
    except KeyError:
        return
    assert False, "expected KeyError"
