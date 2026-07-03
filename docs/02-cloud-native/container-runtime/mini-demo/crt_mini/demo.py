"""Mini-Demo 入口：跑 6 个场景，演示容器运行时核心概念。

运行：python -m crt_mini.demo
对应文档：docs/02-cloud-native/container-runtime/07-mini-demo.md
"""
from __future__ import annotations

from .registry import Registry
from .engine import HighLevelRuntime


def _banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def scenario_1_pull_and_dedup(rt: HighLevelRuntime) -> None:
    _banner("场景 1：镜像分层与内容寻址去重（pull）")
    img = rt.pull("docker.io/library/nginx:1.27")
    print(f"镜像 manifest: {img.manifest}")
    print(f"层数: {len(img.layers)}（每层 digest 唯一）")
    print(f"Content Store blob 数: {rt.content.size()}（config + 各层按 digest 去重）")

    # 同基础层（Debian 12）的另一个镜像：base 层 digest 相同 → 去重
    img2 = rt.pull("docker.io/library/alpine-py:3.12")
    # 注意：这两个镜像的 base 层内容不同（os-release 不同），所以不会真正共享；
    # 演示"去重"语义要看 digest 相同的情况，下面用同镜像再 pull 一次：
    rt.pull("docker.io/library/nginx:1.27")
    ev = [e for e in rt.observer if e["event"] == "pull"][-1]
    print(f"重复 pull 同一镜像: new={ev['new_layers']} shared={ev['shared_layers']}（全部命中去重）")


def scenario_2_union_and_cow(rt: HighLevelRuntime) -> None:
    _banner("场景 2：overlayfs 联合挂载与 copy-on-write（COW 代价）")
    c = rt.run("docker.io/library/nginx:1.27", "web")
    snap = rt.snapshotter
    merged_before = snap.merged(c.config.snapshot_key)
    print(f"容器 rootfs（union 视图）: {sorted(merged_before.keys())}")

    # 写一个全新文件：不触发 COW
    cow1 = c.write_file("/var/log/access.log", "1.2.3.4 - GET /")
    print(f"\n写新文件 /var/log/access.log: COW={cow1}")

    # 修改一个已存在于下层的"大文件"（nginx.conf 只改 1 字节）：触发整文件 copy-up
    big = "/etc/nginx/nginx.conf"
    big_size = len(merged_before[big])
    cow2 = c.write_file(big, "daemon on;")  # 改了 daemon off -> on
    print(f"修改已有文件 {big}（原 {big_size} 字节，只改 1 字节）: COW={cow2}")
    print(f"  → 关键：即使只改 1 字节，整个 {big_size} 字节文件被 copy-up 到 upper 层")


def scenario_3_namespace_isolation(rt: HighLevelRuntime) -> None:
    _banner("场景 3：namespace 隔离（每个容器只看到自己的世界）")
    c1 = rt.run("docker.io/library/nginx:1.27", "web-1")
    c2 = rt.run("docker.io/library/nginx:1.27", "web-2")
    c1.namespaces.uts.add("web-1-hostname")
    c2.namespaces.uts.add("web-2-hostname")
    print(f"web-1 隔离的 ns 类型: {c1.namespaces.isolated_types()}")
    print(f"web-2 隔离的 ns 类型: {c2.namespaces.isolated_types()}")
    print(f"web-1 看到的 uts(hostname): {c1.namespaces.uts.visible()}")
    print(f"web-2 看到的 uts(hostname): {c2.namespaces.uts.visible()}")
    print(f"web-1 的 uts 与 web-2 是否同一对象: {c1.namespaces.uts is c2.namespaces.uts}（隔离）")
    # Pod 内共享 net/ipc（pause 容器语义）
    c1.namespaces.shared_with(c2.namespaces, types=("net",))
    print(f"共享 net 后 web-1 与 web-2 net 同一对象: {c1.namespaces.net is c2.namespaces.net}（Pod 共享网络栈）")


def scenario_4_cgroup_limits(rt: HighLevelRuntime) -> None:
    _banner("场景 4：cgroup 限制——CPU throttle 与内存 OOM")
    # CPU throttle：cpu.max = 50000 100000（0.5 核），每周期用 80000us → 节流
    c_cpu = rt.run("docker.io/library/nginx:1.27", "cpu-job", cpu_quota_us=50_000)
    for _ in range(3):
        c_cpu.use_cpu(80_000)  # 每周期想用 80000us，但只有 50000us 配额
    print(f"cpu.max={c_cpu.cgroup.cpu_max}，3 个周期各要 80000us")
    print(f"  → nr_throttled={c_cpu.cgroup.nr_throttled}，throttled_usec={c_cpu.cgroup.throttled_usec}")

    # 内存 OOM：memory.max=4096，分配超过 → OOMKill
    c_mem = rt.run("docker.io/library/nginx:1.27", "mem-job", memory_max=4096)
    r1 = c_mem.use_memory(2048)
    r2 = c_mem.use_memory(4096)  # 累计 6144 > 4096 → OOM
    print(f"\nmemory.max=4096：先分配 2048 -> {r1}；再分配 4096（累计超限） -> {r2}")
    print(f"  → oom_kills={c_mem.cgroup.oom_kills}，容器状态={c_mem.state}，exit_code={c_mem.exit_code}")


def scenario_5_oci_lifecycle(rt: HighLevelRuntime) -> None:
    _banner("场景 5：OCI 生命周期——create 与 start 两阶段")
    from .runtime import OCIConfig
    img = rt.pull("docker.io/library/nginx:1.27")
    top = f"docker.io/library/nginx:1.27:{img.layers[-1].digest}"
    rt.snapshotter.prepare("manual:rootfs", parent=top)
    cfg = OCIConfig(args=["/usr/sbin/nginx", "-g", "daemon off;"], snapshot_key="manual:rootfs")
    from .runtime import Container
    c = Container("manual", cfg, rt.snapshotter, observer=rt.observer)
    print(f"初始状态: {c.state}")
    c.create()
    print(f"create 后: state={c.state}（namespace/cgroup/rootfs 已就绪，但用户进程尚未 exec）")
    print(f"  rootfs 文件数: {len(c.rootfs)}")
    c.start()
    print(f"start 后: state={c.state}（PID 1 = {c.config.args}）")
    exec_r = c.exec(["/bin/sh", "-c", "ls /etc"])
    print(f"exec /bin/sh: 新 PID={exec_r['pid']}（setns 进容器再起进程）")
    c.stop("TERM")
    print(f"stop 后: state={c.state}, exit_code={c.exit_code}")


def scenario_6_multiarch(rt: HighLevelRuntime) -> None:
    _banner("场景 6：多架构 manifest list（按 --platform 选择）")
    from .registry import Registry
    reg = rt.registry
    ml = reg.resolve("myreg/ai-server:v1")
    print(f"manifest list 支持平台: {ml.platforms}")
    for plat in ("linux/amd64", "linux/arm64"):
        img = rt.pull("myreg/ai-server:v1", platform=plat)
        print(f"  --platform {plat}: 选到的镜像 base 层 = {img.layers[0].files['/etc/os-release']}")


def run_demo() -> None:
    print("容器运行时概念模拟器（crt_mini）")
    print("纯 Python，确定性，不调用任何真实 Linux 系统调用。\n")

    rt = HighLevelRuntime(Registry())
    scenario_1_pull_and_dedup(rt)
    scenario_2_union_and_cow(rt)
    scenario_3_namespace_isolation(rt)
    scenario_4_cgroup_limits(rt)
    scenario_5_oci_lifecycle(rt)
    scenario_6_multiarch(rt)

    _banner("容器状态总览")
    for s in rt.status():
        print(f"  {s['name']}: state={s['state']}, cpu.max={s['cpu.max']}, "
              f"mem={s['memory.current']}/{s['memory.max']}, oom={s['oom_kills']}")
    print("\n演示结束。详见 docs/02-cloud-native/container-runtime/07-mini-demo.md")


if __name__ == "__main__":
    run_demo()
