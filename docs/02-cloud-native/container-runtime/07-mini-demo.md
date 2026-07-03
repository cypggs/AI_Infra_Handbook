# 7. Mini-Demo：用纯 Python 模拟容器运行时核心机制

> 一句话理解：我们在一个单进程、确定性、零依赖的 Python 模拟器里，把容器运行时的**镜像分层与内容寻址、overlayfs 联合挂载与 copy-on-write、namespace 隔离、cgroup 限制（CPU throttle / 内存 OOM）、OCI create/start 生命周期、多架构 manifest list** 六大机制跑给你看——没有真实 Linux 内核调用，但每一个设计权衡都是真的。

前面六章我们把容器运行时从"设计动机 → 架构 → 源码"讲透了。但容器运行时的精髓是**数据流与生命周期**：镜像层怎么去重、rootfs 怎么联合挂载、COW 什么时候触发、CPU 什么时候被节流、容器怎么从 created 变 running。这些用文字描述总隔着一层。本章的 Mini-Demo 把这些动态过程变成**可运行、可断言、可反复重现**的代码，让你用 0.05 秒看明白真实运行时要花几小时才能观察到的东西。

> 配套代码位于 `docs/02-cloud-native/container-runtime/mini-demo/`，`README.md` 有完整运行说明，`tests/` 有 40 个通过的 pytest 用例。

## 7.1 为什么不用真实容器做演示

教学演示最"真实"的选择当然是装个 Docker、起真实容器。但对**理解机制**而言，真实运行时反而是糟糕的媒介：

| 问题 | 真实运行时 | 本模拟器 |
|---|---|---|
| 平台门槛 | 需要 Linux（namespace/cgroup 是 Linux 内核特性） | macOS/CPU 即可，`python -m crt_mini.demo` |
| 观测 | 要 `docker history`、翻 `/sys/fs/cgroup`、抓 strace | 每步的状态变化直接打印 |
| 内核交互 | namespace/cgroup 由内核强制，行为难"拆开看" | 用 Python 对象显式建模，每一步可见 |
| 确定性 | cgroup 计时受负载影响 | 无随机数，反复运行结果完全一致 |
| 可断言 | 写 e2e 测试要真实环境、几分钟跑一次 | pytest 0.05 秒跑完 40 例 |

真实运行时教会你**操作**，模拟器教会你**原理**。本章属于后者——当你能在模拟器里预测每一步的输出，再去操作真实容器时，你会在 `dive` 的每一层、`/sys/fs/cgroup` 的每一行里看到熟悉的结构。

## 7.2 整体设计：一个高层运行时驱动的分层模型

真实容器运行时是**分层**的（高层运行时 → 低层运行时 → 内核）。本模拟器**保留了分层，去掉了内核**：用 Python 类显式建模每一层的数据与行为，让因果一目了然。

```python
# engine.py — HighLevelRuntime.run()：docker run 的全链路
def run(self, ref, name, platform="linux/amd64", **limits) -> Container:
    image = self.pull(ref, platform=platform)            # ① pull：拉 manifest → 存层 → 解包快照
    top_snap = f"{ref}:{image.layers[-1].digest}"
    active_key = f"{name}:rootfs"
    self.snapshotter.prepare(active_key, parent=top_snap) # ② prepare：在层链顶建可写快照（upperdir）
    config = OCIConfig(args=..., snapshot_key=active_key, **limits)  # ③ 生成 OCI config.json
    c = Container(name, config, self.snapshotter, ...)    # ④ 低层运行时 Container
    c.create()                                            # ⑤ runc create：建 ns/cgroup/rootfs，不 exec
    c.start()                                             # ⑥ runc start：exec 用户进程 → running
    self.containers[name] = c
    return c
```

这个执行顺序**忠实反映了真实 `docker run` 的因果链**（见第 4 章）：拉镜像 → 解包成 rootfs → 生成 OCI config → create → start。区别只是真实运行时每步落到内核系统调用，而这里用 Python 对象显式建模。

### 模块与真实组件的对应

| 模拟器模块 | 真实组件 | 关键职责 |
|---|---|---|
| `image.py` | OCI image-spec | Layer/ImageConfig/Image/ManifestList（内容寻址） |
| `content.py` | containerd Content Store | 按 digest 存 blob、去重 |
| `snapshot.py` | containerd overlayfs snapshotter | 解包层成快照、union 挂载、COW |
| `namespace.py` | Linux namespaces | pid/net/mnt/uts/ipc/user 隔离视图 |
| `cgroup.py` | Linux cgroup v2 | cpu.max/memory.max/pids.max + throttle/OOM |
| `runtime.py` | runc/libcontainer | create/start/exec 生命周期 |
| `engine.py` | containerd | pull + run 全链路 |
| `registry.py` | OCI registry | 示例镜像 + 多架构 |

## 7.3 机制一：镜像分层与内容寻址去重

OCI 镜像由多个**层（Layer）**组成，每层用内容的 SHA256 摘要寻址——这是镜像去重与复用的根基。模拟器用确定性 `digest()` 复现这一点：

```python
# image.py — Layer 的 digest 由 (parent, files) 内容寻址
@dataclass
class Layer:
    files: dict[str, str]
    parent: str | None = None
    digest: str = ""
    def __post_init__(self):
        self.digest = digest(self.parent, sorted(self.files.items()))
```

`pull` 时把每层存进 Content Store，**digest 相同的层只存一份**：

```python
# engine.py — pull 时按 digest 去重
for layer in image.layers:
    if self.content.has(layer.digest):
        shared_layers += 1        # 已存在 → 共享
    else:
        self.content.put(layer.digest, layer)
        new_layers += 1
```

**运行场景 1**（pull nginx 镜像，再 pull 一次）：

```
镜像 manifest: {'config': 'sha256:583accc12b9d7bac', 'layers': ['sha256:17a347b9...', 'sha256:c1d4bdc2...']}
Content Store blob 数: 2（config + 各层按 digest 去重）
重复 pull 同一镜像: new=0 shared=2（全部命中去重）
```

**为什么有教学价值**：它直观展示了"为什么 100 个容器共用 `pytorch` 基础镜像，磁盘上那个 2GB 的基础层只存一份"——因为内容寻址让 digest 相同的层天然去重，这是镜像"轻量"的根基。

## 7.4 机制二：overlayfs 联合挂载与 copy-on-write（COW 代价）

这是最容易被误解、也最有教学价值的部分。overlayfs 把多个只读层（lowerdir）+ 一个可写层（upperdir）**联合挂载**成统一视图；写一个已存在于下层的文件时，触发 **copy-on-write**——把整个文件从下层复制到上层再改。

```python
# snapshot.py — write 模拟 COW 记账
def write(self, key, path, content):
    snap = self.snaps[key]
    cow = {"copied_from_lower": False, "copied_bytes": 0, ...}
    if path not in snap.files:                       # upper 还没这个文件
        lower_view = self.merged(snap.parent)         # 看下层有没有
        if path in lower_view:
            cow["copied_from_lower"] = True
            cow["copied_bytes"] = len(lower_view[path])  # 整个文件被复制
    snap.files[path] = content
    return cow
```

`merged()` 则模拟联合挂载——下层自底向上叠加，上层覆盖：

```python
def merged(self, key):
    view = {}
    for snap in self._chain(key):     # 根(最低层) → 顶(最高层)
        view.update(snap.files)        # 后(上层)覆盖前(下层)
    return view
```

**运行场景 2**（运行 nginx 容器，写文件）：

```
容器 rootfs（union 视图）: ['/bin/sh', '/etc/nginx/nginx.conf', '/etc/os-release', '/usr/sbin/nginx']
写新文件 /var/log/access.log: COW={'copied_from_lower': False, ...}        ← 新文件，不复制
修改 /etc/nginx/nginx.conf（原 11 字节，只改 1 字节）: COW={'copied_from_lower': True, 'copied_bytes': 11, ...}
  → 关键：即使只改 1 字节，整个 11 字节文件被 copy-up 到 upper 层
```

**为什么这个对比有教学价值**：它直观揭示了 overlayfs 的一个**生产陷阱**——在镜像里放一个 5GB 模型文件，启动后改一行 metadata，upperdir 会多出 5GB。模拟器的 `copied_bytes=11`（整个旧文件大小）让"COW 复制整个文件"这一反直觉事实变得可见。这正是第 2、8、9 章反复强调"大文件/需写的数据放 volume，不要进镜像层"的原理。

## 7.5 机制三：namespace 隔离

容器进程被塞进一组 namespace，"看到的"世界被改写。模拟器用 `NamespaceSet` 显式建模——每个容器有独立的 pid/net/mnt/uts/ipc/user 命名空间，只看到自己 namespace 的成员：

```python
# namespace.py — NamespaceSet.isolated() 给每个容器一组新 ns
@classmethod
def isolated(cls):
    ns = cls()
    for t in ("pid", "net", "mnt", "uts", "ipc", "user"):
        setattr(ns, t, Namespace(type=t))
    return ns
```

**运行场景 3**（两个容器 + Pod 共享网络）：

```
web-1 隔离的 ns 类型: ['pid', 'net', 'mnt', 'uts', 'ipc', 'user']
web-2 隔离的 ns 类型: ['pid', 'net', 'mnt', 'uts', 'ipc', 'user']
web-1 看到的 uts(hostname): ['web-1', ...]      ← 各自隔离
web-2 看到的 uts(hostname): ['web-2', ...]
web-1 的 uts 与 web-2 是否同一对象: False（隔离）
共享 net 后 web-1 与 web-2 net 同一对象: True（Pod 共享网络栈）
```

`shared_with` 演示了 K8s Pod 的核心机制：**一个 Pod 内的多个容器共享 net/ipc namespace**（对应 pause 容器持有 Pod 的 namespace，业务容器加入它）。这就是"Pod 内容器 localhost 互通、共享网络栈"的实现原理（见第 4、5 章）。

## 7.6 机制四：cgroup 限制——CPU throttle 与内存 OOM

cgroup 给容器施加资源限制。模拟器复现了 CFS bandwidth control（CPU 节流）和 memory OOM 两个最常踩的生产坑：

```python
# cgroup.py — CPU：每周期配额 quota，超出则节流
def tick(self, cpu_used_us):
    self.nr_periods += 1
    if self.cpu_quota_us > 0 and cpu_used_us > self.cpu_quota_us:
        self.nr_throttled += 1
        self.throttled_usec += cpu_used_us - self.cpu_quota_us
        self.cpu_used_us += self.cpu_quota_us   # 只有配额部分真正执行
        return "throttled"
    self.cpu_used_us += cpu_used_us
    return "ok"

# 内存：超出 memory.max → OOM，分配被拒
def consume_memory(self, bytes_):
    self.memory_current += bytes_
    if self.memory_max > 0 and self.memory_current > self.memory_max:
        self.oom_kills += 1
        self.memory_current -= bytes_   # 回滚
        return "oom"
    return "ok"
```

**运行场景 4**（CPU 0.5 核但每周期要 80000us；内存上限 4096）：

```
cpu.max=50000 100000，3 个周期各要 80000us
  → nr_throttled=3，throttled_usec=90000                     ← CPU 节流

memory.max=4096：先分配 2048 -> ok；再分配 4096（累计超限） -> oom
  → oom_kills=1，容器状态=stopped，exit_code=137              ← OOMKill
```

**为什么这个对比有教学价值**：

- **CPU throttle** 解释了"AI 推理服务周期性变慢"的根因——`limits.cpu` 设小了，内核 CFS 每 100ms 周期节流。生产排查就是看 `/sys/fs/cgroup/.../cpu.stat` 的 `nr_throttled`，模拟器把这个指标直接暴露。
- **OOM** 解释了 `kubectl describe` 里 `OOMKilled` + `exit_code=137` 的来源——`limits.memory` 超了，内核杀进程。注意 OOM 后容器状态自动变 `stopped`、exit_code=137（137 = 128 + 9，SIGKILL），与真实行为一致。

> `memory.max=4096` 对应 K8s `resources.limits.memory`；`cpu.max=50000 100000`（0.5 核）对应 `resources.limits.cpu: 500m`。这两个映射是面试常考点（见第 10 章 Q15/Q16）。

## 7.7 机制五：OCI create/start 两阶段生命周期

OCI Runtime Spec 把容器创建刻意分成 `create`（建环境不启动）和 `start`（exec 用户进程）两阶段。模拟器忠实复现：

```python
# runtime.py — Container.create / start
def create(self):
    self.rootfs = dict(self.snapshotter.merged(self.config.snapshot_key))  # 挂 rootfs
    self.cgroup.acquire_pid()         # init 进程槽位
    self.pid_ns_counter = 1           # PID 1 留给入口进程
    self.state = "created"            # 注意：还没 exec 用户命令

def start(self):
    self.state = "running"
    self.namespaces.pid.add(("process", 1, self.config.args))  # exec → PID 1
```

`exec` 则模拟 `runc exec` / `kubectl exec`——`setns` 进容器再起一个新进程：

```python
def exec(self, args):
    ok = self.cgroup.acquire_pid()     # 占一个 PID
    if ok != "ok":
        return {"pid": None, "reason": ok}  # pids.max 超了会被拒
    self.pid_ns_counter += 1
    return {"pid": self.pid_ns_counter}
```

**运行场景 5**（手动走完整生命周期）：

```
初始状态: creating
create 后: state=created（namespace/cgroup/rootfs 已就绪，但用户进程尚未 exec）
  rootfs 文件数: 4
start 后: state=running（PID 1 = ['/usr/sbin/nginx', '-g', 'daemon off;']）
exec /bin/sh: 新 PID=2（setns 进容器再起进程）
stop 后: state=stopped, exit_code=0
```

**为什么两阶段是设计而不是冗余**：K8s 的 Pod 沙箱正是用这个语义——先把 Pod 的网络/容器都 `create` 好（pause 容器先起、CNI 配网络），再统一 `start`。把 create 与 start 分离，让上层有机会在"容器进程真正运行前"完成绑定。模拟器把这个语义直接暴露在 `state` 转换里。

## 7.8 机制六：多架构 manifest list

现代镜像常是多架构的（一个 image index 指向各架构的子 manifest）。模拟器复现了 `--platform` 选择：

```python
# image.py — ManifestList.select 按 platform 选子镜像
def select(self, platform):
    for e in self.entries:
        if e.platform == platform:
            return e.image
    raise KeyError(f"no manifest for platform {platform}")
```

**运行场景 6**（`myreg/ai-server:v1` 支持 amd64/arm64）：

```
manifest list 支持平台: ['linux/amd64', 'linux/arm64']
  --platform linux/amd64: 选到的镜像 base 层 = Linux/amd64
  --platform linux/arm64: 选到的镜像 base 层 = Linux/arm64
```

**为什么有教学价值**：它揭示了"x86 集群 + ARM 推理（Graviton/Ampere）共用一个镜像 tag"的原理——客户端按当前架构从 image index 选对应子 manifest，拉到的是架构匹配的层。这是第 8 章多架构构建（buildx）的运行时侧对应。

## 7.9 测试：把演示输出变成可回归的契约

40 个 pytest 用例不只是"跑通"，而是把每个机制的关键不变量固化为**契约**。例如：

```python
# test_snapshot.py — COW 必须复制整个文件
def test_write_existing_file_triggers_full_copy_up():
    snap = _two_layer_snapshotter()
    snap.prepare("active", parent="app")
    old = snap.merged("active")["/etc/config"]
    cow = snap.write("active", "/etc/config", "X")    # 只覆盖 1 字节
    assert cow["copied_from_lower"] is True
    assert cow["copied_bytes"] == len(old)            # 整个旧文件大小
    assert cow["written_bytes"] == 1

# test_cgroup.py — CPU 超配额必须节流
def test_cpu_throttle_when_quota_exceeded():
    cg = Cgroup(name="/job", cpu_quota_us=50_000)
    assert cg.tick(80_000) == "throttled"
    assert cg.nr_throttled == 1

# test_runtime.py — OOM 必须停容器 + exit 137
def test_oom_stops_container():
    c = _make_container(memory_max=4096)
    c.create(); c.start()
    assert c.use_memory(4096) == "oom"
    assert c.state == "stopped"
    assert c.exit_code == 137

# test_engine.py — pull 同镜像必须全部去重
def test_pull_dedups_identical_layers():
    rt = _rt()
    rt.pull("docker.io/library/nginx:1.27")
    n = rt.content.size()
    rt.pull("docker.io/library/nginx:1.27")          # 再 pull
    assert rt.content.size() == n                     # 不增长
```

为什么这很重要：当你将来改动模拟器（比如加 `cgroup v2 io` 控制器、加 user namespace 的 uid 映射），`pytest` 会立刻告诉你有没有破坏已有机制。这就是**测试即文档**——断言比注释更可靠。

```bash
$ pytest tests/ -q
........................................                 [100%]
40 passed in 0.05s
```

## 7.10 模拟器与真实运行时的本质差异（诚实的边界）

为避免过度自信，必须讲清模拟器**故意省略**了什么：

| 维度 | 模拟器 | 真实运行时 | 为什么省略 / 影响 |
|---|---|---|---|
| **隔离机制** | Python `Namespace` 对象 | 真实 `clone(CLONE_NEW*)` 系统调用 | 失去了"内核强制"——模拟器里"隔离"只是约定，真实容器也共享内核（这正是 gVisor/Kata 存在的理由） |
| **资源限制** | 数据结构累加/比较 | 真实 cgroupfs，内核强制节流/OOM | 模拟器无法体现"进程真的被暂停"的物理效果 |
| **文件系统** | Python dict 模拟 union | 真实 overlayfs 内核挂载 | 真实的 whiteout 文件、多个 lowerdir 叠加细节未模拟 |
| **进程** | 模拟的 PID 计数器 | 真实 `fork/exec`、PID 1、信号处理 | PID 1 的 reap、信号转发、僵尸进程等真实问题未体现 |
| **网络** | 完全不模拟 | CNI 真实组网、iptables/路由 | 端口映射、CNI、Service 网络行为完全没有 |
| **镜像** | 内存中的示例数据 | 真实 registry、压缩层、digest 校验 | 真实的拉取限速、压缩解压、zstd/estargz 未模拟 |

**结论**：模拟器是理解容器运行时**机制与设计权衡**的最佳工具，但它**不能替代**真实运行时的操作经验。学完本章后，强烈建议在装了 Docker 的机器上：用 `dive` 拆开一个真实镜像看每层体积、用 `docker run` + `cat /sys/fs/cgroup/.../cpu.stat` 看真实节流、用 `crictl` 在 K8s 节点看一次容器创建——对照模拟器的输出，你会对两者都有更深的理解。

## 本章小结

本章用 `docs/02-cloud-native/container-runtime/mini-demo/` 这个约 500 行核心逻辑的模拟器，把前六章的抽象概念变成了**可运行、可断言、可重现**的动态过程。六个机制各对应一个演示场景与一组测试：**镜像分层与去重**（内容寻址让相同层只存一份）、**overlayfs 联合挂载与 COW**（union 视图 + 改 1 字节复制整个文件的代价）、**namespace 隔离**（6 种 ns + Pod 共享网络栈）、**cgroup 限制**（CPU throttle + 内存 OOM，含 exit 137）、**OCI create/start 两阶段生命周期**（+ exec/stop）、**多架构 manifest list**（按 platform 选择）。模拟器通过"显式建模每一层"保留了真实运行时的设计权衡，同时用确定性换取了可教学、可测试的清晰性。它的价值不在"替代真实运行时"，而在让你在 0.05 秒内看明白真实运行时要花几小时才能观察到的动态过程——当你能在模拟器里预测每一步，真实运行时的每一次 `dive`、每一次查 `cpu.stat`、每一次 `OOMKilled` 都会变得可读。

**参考来源**

- 本手册配套代码：`docs/02-cloud-native/container-runtime/mini-demo/`（含 `README.md` 与 40 个测试）
- [OCI Runtime Specification（生命周期 create/start）](https://github.com/opencontainers/runtime-spec/blob/main/runtime.md)
- [OCI Image Specification（manifest/layers）](https://github.com/opencontainers/image-spec)
- [Linux cgroups v2 文档（cpu.max/memory.max）](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
- [overlayfs 内核文档](https://docs.kernel.org/filesystems/overlayfs.html)
- [Liz Rice — Containers from scratch（从零实现容器的灵感来源）](https://github.com/lizrice/containers-from-scratch)
