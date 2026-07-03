# 4. Runtime 工作流程：从一条命令到运行中的进程

> 一句话理解：本章把 `docker run`（以及 K8s 的 `crictl runp`）拆成**逐阶段时序**——引用解析 → 拉 manifest → 逐层下载+解包成快照 → 用 snapshotter 拼出 rootfs → 写 OCI config.json → runc create（建 namespace/cgroup/mount，不启动）→ runc start（exec 用户进程）→ shim 接管；每一步都对应一个你能观测、能踩坑的真实现象（镜像拉不动、COW 爆盘、OOMKill、exec 失败）。

## 4.1 全景：一次 `docker run` 的生命周期

```
docker run --name web -p 8080:80 nginx:1.27
  │
  ① CLI → dockerd（REST）
  ② dockerd → containerd：解析引用、检查本地镜像
  ③ 缺镜像：Transfer Service 从 registry pull
        ├─ GET manifest（nginx:1.27）
        ├─ 解析出 config digest + N 个 layer digest
        └─ 逐层 GET blob → 写入 Content Store（按 digest 去重）
  ④ Snapshotter 解包层 → 构建快照树 → 准备 rootfs（merged）
  ⑤ containerd fork containerd-shim-runc-v2（每容器一个 shim）
  ⑥ shim 调 runc create：读 config.json → clone(namespaces) → cgroup → mount rootfs → 建 PID 1（挂起，未 exec）
  ⑦ shim 调 runc start：exec 用户进程（nginx）→ 进入 Running
  ⑧ shim 持续 reap/转发日志/上报状态；容器对外通过 -p 8080:80 映射端口
```

下面逐步拆解。

## 4.2 阶段一：引用解析（reference resolution）

镜像引用（reference）有几种形态：

| 形态 | 含义 |
|---|---|
| `nginx` | 缺省 registry（docker.io）+ 缺省 tag（latest）→ `docker.io/library/nginx:latest` |
| `nginx:1.27` | 指定 tag |
| `nginx@sha256:abc123...` | **digest 引用**（内容寻址，不可变，最精确） |
| `myreg.com/team/app:v2` | 私有 registry + tag |

解析流程：

1. 规范化引用（补全 registry/library/tag）。
2. 查本地镜像库（containerd 的 metadata store）：digest 命中 → 跳过拉取。
3. 未命中 → 向 registry 请求 manifest。

> **生产陷阱**：用 tag（`nginx:1.27`）而非 digest 部署，存在"漂移"风险——维护者可以把 `1.27` tag 重新指向另一个镜像（修复 CVE 的 patch 版本），导致两次部署拉到不同内容。**生产应尽量用 digest（`nginx@sha256:...`）或镜像签名锁定内容**（见第 8 章）。K8s 默认用 tag，需要部署流程主动把 tag 解析成 digest 再下发（"digest pinning"）。

## 4.3 阶段二：拉取 manifest（拉取清单）

客户端向 registry 请求 manifest：

```
GET /v2/library/nginx/manifests/1.27
Accept: application/vnd.oci.image.manifest.v1+json,
        application/vnd.docker.distribution.manifest.v2+json
```

返回的 manifest 大致长这样（OCI image-spec）：

```json
{
  "schemaVersion": 2,
  "mediaType": "application/vnd.oci.image.manifest.v1+json",
  "config": {
    "mediaType": "application/vnd.oci.image.config.v1+json",
    "digest": "sha256:<config-digest>",
    "size": 12345
  },
  "layers": [
    { "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip", "digest": "sha256:<layer-1-digest>", "size": 31234567 },
    { "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip", "digest": "sha256:<layer-2-digest>", "size": 8910 },
    ...
  ]
}
```

manifest 告诉客户端：这个镜像由 **一个 config + N 个层**组成，每个都用 digest 引用。

### 多架构镜像：manifest list / index

`docker run --platform linux/arm64 nginx` 时，registry 返回的是一个 **manifest list（OCI 叫 image index）**——它不直接列层，而是列出各架构对应的子 manifest：

```json
{
  "schemaVersion": 2,
  "mediaType": "application/vnd.oci.image.index.v1+json",
  "manifests": [
    { "digest": "sha256:<amd64-manifest>", "platform": { "os": "linux", "architecture": "amd64" } },
    { "digest": "sha256:<arm64-manifest>", "platform": { "os": "linux", "architecture": "arm64" } }
  ]
}
```

客户端按当前机器架构（`linux/amd64`）选对应子 manifest，再走单架构流程。这是多架构镜像（Mac M 系列跑 amd64 镜像、x86 集群拉 amd64）的根基。

## 4.4 阶段三：逐层下载 + 写入 Content Store

拿到 manifest 后，客户端逐个拉取 **config** 和每个 **layer** 的 blob：

```
GET /v2/library/nginx/blobs/sha256:<config-digest>
GET /v2/library/nginx/blobs/sha256:<layer-1-digest>
...
```

下载的内容写入 **Content Store**（按 digest 寻址、去重）：

- 相同 digest 的层**只存一份**——即使被多个镜像共享。
- Content Store 里的层是**压缩的归档（tar.gz / zstd）**，未解包。

> **拉不动镜像的常见原因**：(1) registry 限速/网络问题；(2) 某一层特别大（基础镜像太胖）——第 8/9 章讲镜像优化；(3) 鉴权失败（pull secret 配错）。K8s 里 `ContainerCreating` 卡住、事件报 `ImagePullBackOff` 多半是这一阶段失败。

## 4.5 阶段四：解包层 → 构建快照树（Snapshotter）

Content Store 里是压缩归档，**运行容器需要解开的文件系统**。这是 **Snapshotter** 的工作。

### 快照（snapshot）的"父-子"链

Snapshotter 把每个层解压成一个**只读快照**，层与层之间形成父子链：

```
snapshot（可写，容器专属）   ← upperdir
   ↑ parent
snapshot layer-3 (解开)       ← lowerdir 最上
   ↑ parent
snapshot layer-2 (解开)
   ↑ parent
snapshot layer-1 (解开)       ← 基础镜像，lowerdir 最下
```

创建容器时，Snapshotter 在链顶加一个**可写快照**（COW 的 upperdir），把整条链 overlay 联合挂载成 `rootfs`，交给 runc。

### 为什么这样设计：复用与按需

- 同一基础镜像的多个容器 → 共享 lowerdir 快照链 → 磁盘只存一份。
- 拉新镜像时，只对"未解包的新层"做解包——已存在的层快照直接复用。

### 可替换的 snapshotter

overlayfs 是默认，但 snapshotter 是可替换的接口：

| snapshotter | 特点 | 场景 |
|---|---|---|
| **overlayfs** | 默认，最快，COW | 99% 场景 |
| **btrfs / zfs** | 用文件系统原生 subvolume | 需要原生快照语义 |
| **native** | 全量复制（无 COW） | 测试/简单环境 |
| **stargz** | 惰性拉取（按需读层，不用全下完） | 冷启动优化 |
| **nydus** | 阿里 Dragonfly 出品，按需下载 + 内容寻址 | 大镜像（模型镜像）冷启动 |

> stargz/nydus 是"惰性拉取"方案——镜像不下载完就能启动容器，首次访问文件时才从 registry 拉那部分。对**带模型权重的超大镜像**（几十 GB）冷启动是杀手锏。containerd 2.x 的 Transfer Service 原生支持这类流式 snapshotter。

## 4.6 阶段五：生成 OCI config.json

containerd 综合**镜像 config**（从镜像拉的，含 Env/Cmd/Entrypoint）+ **运行时参数**（`docker run` 传的，如 `-e`、`-p`、`--memory`、`--network`）→ 生成一份 **OCI runtime-spec 的 `config.json`**，描述这个容器具体怎么创建：

```jsonc
{
  "ociVersion": "1.2.0",
  "process": {
    "terminal": false,
    "user": { "uid": 101, "gid": 101 },
    "args": ["/docker-entrypoint.sh", "nginx", "-g", "daemon off;"],
    "env": ["PATH=...", "NGINX_VERSION=1.27"],
    "cwd": "/",
    "capabilities": { "bounding": ["CAP_NET_BIND_SERVICE"], ... },
    "noNewPrivileges": true
  },
  "root": { "path": "rootfs", "readonly": false },
  "hostname": "web",
  "mounts": [
    { "destination": "/proc", "type": "proc" },
    { "destination": "/dev", "type": "tmpfs" },
    { "destination": "/sys", "type": "sysfs" },
    ...
  ],
  "linux": {
    "namespaces": [
      { "type": "pid" }, { "type": "ipc" }, { "type": "uts" },
      { "type": "mount" }, { "type": "network" }, { "type": "user" }
    ],
    "cgroupsPath": "/system.slice/docker-<id>.scope",
    "resources": {
      "memory": { "limit": 536870912 },
      "cpu": { "shares": 1024 }
    },
    "seccomp": { "defaultAction": "SCMP_ACT_ERRNO", "syscalls": [...] }
  }
}
```

这份 config 是 runc 的**唯一输入**。它精确告诉 runc：开哪些 namespace、设多大内存、挂哪些虚拟文件系统、允许哪些 capability、过滤哪些系统调用（seccomp）。

> 这一步把"镜像（声明用户意图）"和"运行参数（运行时定制）"合并成"可执行的 OCI bundle"——runc 只管照着执行，不关心上层是 Docker 还是 K8s。

## 4.7 阶段六：runc create —— 建好环境，但不启动

containerd 先 fork 一个 **containerd-shim**，shim 调用 `runc create`：

runc/libcontainer 做的事（顺序很重要）：

1. **读 config.json**，初始化容器配置。
2. **创建 namespaces**：通过 `clone(CLONE_NEWPID|CLONE_NEWNET|CLONE_NEWNS|CLONE_NEWIPC|CLONE_NEWUTS|CLONE_NEWUSER, ...)` 或 `unshare` 创建一组新的 namespace。
3. **设置 cgroups**：在 `cgroupsPath` 下写 `cpu.max`、`memory.max`、`pids.max` 等，把容器进程加入该 cgroup。
4. **挂载 rootfs**：把 overlayfs 的 merged 目录（Snapshotter 准备好的）作为根；挂载 `/proc`、`/sys`、`/dev` 等虚拟文件系统。
5. **收窄权限**：drop capabilities（只留 config 允许的）、应用 seccomp 过滤、可选 AppArmor/SELinux profile。
6. **创建容器主进程**，但**让它阻塞在等待启动信号**——此时容器进程已存在（在 namespace/cgroup 里），但用户的 `args`（nginx）还没 exec。

> `create` 与 `start` 分离是 runtime-spec 的刻意设计：先 create，让上层（shim/containerd）有机会做"绑定"（如绑定网络、注册监控），再统一 start。K8s 的 Pod 沙箱也用这个语义——先把 Pod 的网络/容器都 create 好，再统一 start。

## 4.8 阶段七：runc start —— exec 用户进程

shim 调用 `runc start`，runc 给那个阻塞的容器进程**发启动信号**，它才真正 `exec` 用户命令（`nginx -g 'daemon off;'`）。容器进入 **Running** 状态。

此后 **runc 退出**——它的工作（创建容器）做完了。容器进程的父进程是 **shim**，shim 接管后续职责：

- **reap 子进程**：容器内 PID 1 自己 fork 出的子进程，退出时由 PID 1 reap；但如果 PID 1 不做 reap（很多程序不做），僵尸进程的清理落到 shim。
- **转发信号**：`docker stop` / `kubectl delete` → shim 给容器 PID 1 发 SIGTERM（宽限期后 SIGKILL）。
- **收集退出码**：容器退出，shim 记下 exit code，上报给 containerd → K8s 显示 `ExitCode`。
- **转发 stdout/stderr**：shim 把容器输出写到日志文件/驱动 → `docker logs` / `kubectl logs`。
- **处理 exec**：`kubectl exec` → shim 用 `setns` 把新进程加入容器的 namespace。

## 4.9 阶段八：网络——端口映射 / Pod 网络

容器进了 net namespace，但它"看不见"宿主机网络。怎么让外面访问 `-p 8080:80`？

### Docker：iptables DNAT / userland proxy

Docker 默认用 **iptables DNAT**（或 nftables）把宿主 `8080` 端口的流量 NAT 到容器 net namespace 里的 `80`；某些场景用 userland proxy（`docker-proxy`）。

### Kubernetes：CNI

K8s 把网络交给 **CNI（Container Network Interface）** 插件（Calico/Cilium/Flannel/Weave）。CNI 在 Pod 沙箱创建时：

1. 给 Pod net namespace 分配一个 Pod IP；
2. 配置 veth pair（一头在 Pod net ns，一头在宿主）；
3. 配路由/网络策略（NetworkPolicy）。

> 这就是"没有 CNI，K8s 集群起不来"的根源——Pod 网络完全依赖 CNI 插件配置。容器运行时只负责创建 net namespace 并把 IP 配进去（CRI 调用 CNI），网络怎么通是 CNI 的事（详见 [Kubernetes](/02-cloud-native/kubernetes/) 第 5 章 CNI 一节）。

## 4.10 一个 K8s Pod 的完整时序（对照）

在 K8s 节点上，kubelet 通过 CRI 把上面流程跑一遍，但多了 Pod 语义：

```
kubelet 收到 Pod 调度（bind 到本节点）
  │
  ① CRI: RunPodSandbox()
       ├─ 拉取 pause 镜像（registry.k8s.io/pause）
       ├─ 创建 pause 容器（持有一个 net/ipc namespace）
       └─ 调用 CNI 给 Pod 分配 IP、配网络
  ② 对 Pod 里每个业务容器：CRI: CreateContainer()
       ├─ PullImage（若本地无）
       ├─ 用 Snapshotter 准备 rootfs
       ├─ 生成 OCI config（容器加入 pause 的 net/ipc namespace → localhost 互通）
       └─ runc create（建好，不启动）
  ③ CRI: StartContainer() → runc start → 容器 Running
  ④ 循环 PLEG（PLEG = Pod Lifecycle Event Generator）：监控容器状态变化
```

关键细节：**Pause 容器先创建并持有 Pod 的 net/ipc namespace，业务容器创建时加入它的 namespace**——这就是"一个 Pod 内容器 localhost 互通、共享网络栈"的实现机制。Pause 本身几乎不耗资源，但它"占位"namespace，即使业务容器重启，Pod 的 IP 不变。

## 4.11 常见故障在时序的哪一步

把上面的时序和真实排障对应起来，你能精准定位问题：

| 现象 | 卡在哪个阶段 | 根因方向 |
|---|---|---|
| K8s Pod `ImagePullBackOff` | 阶段三（拉取） | registry 鉴权/网络/镜像名错 |
| `ContainerCreating` 长时间 | 阶段四（解包） | 镜像太大、磁盘满、overlayfs 挂载失败 |
| `OOMKilled` | 阶段六后（运行） | cgroup `memory.max` 设太小 |
| 容器周期性变慢 | 运行中 | cgroup CPU throttle（查 `cpu.stat`） |
| `exec` 进容器失败 | shim | shim 进程异常、namespace 已销毁 |
| 容器退出但 Pod 卡 Terminating | shim/网络 | 容器不响应 SIGTERM、CNI 清理失败 |
| 节点重启后容器全没了 | （非 shim 问题） | containerd 配置 `no start` / 镜像本地未持久 |

## 本章小结

一次容器创建是**严格有序**的：引用解析 → 拉 manifest → 逐层下载 blobs 进 Content Store → Snapshotter 解包成快照链并拼出 rootfs → 生成 OCI config.json → runc create（建 namespace/cgroup/mount、收窄权限，但不启动）→ runc start（exec 用户进程）→ runc 退出、shim 接管 reap/日志/信号/exec。K8s 在这条链外包了一层 Pod 语义：先 `RunPodSandbox`（用 pause 容器持有 Pod 的 net/ipc namespace，CNI 配网络），再对每个业务容器走 create→start。把这条时序刻进脑子，你就能把 `ImagePullBackOff`、`OOMKilled`、CPU throttle、exec 失败这些生产现象精准定位到某一阶段、某一个组件——这是从"会用容器"到"能排障容器"的分水岭。下一章我们逐一深入这条链上的核心模块。

**参考来源**

- [OCI Runtime Specification（生命周期 create/start）](https://github.com/opencontainers/runtime-spec/blob/main/runtime.md)
- [OCI Image Specification（manifest/config）](https://github.com/opencontainers/image-spec)
- [containerd Snapshots 设计](https://github.com/containerd/containerd/blob/main/docs/snapsholders.md)
- [containerd Snapshotter 接口](https://github.com/containerd/containerd/blob/main/docs/snapsholders.md)
- [Kubernetes CRI 架构与 Pod 沙箱](https://kubernetes.io/zh-cn/docs/concepts/architecture/cri/)
- [The `pause` 容器的作用](https://www.alibabacloud.com/blog/the-pause-container)（多来源解析）
- [stargz / nydus 惰性拉取](https://github.com/containerd/stargz-snapshotter)
