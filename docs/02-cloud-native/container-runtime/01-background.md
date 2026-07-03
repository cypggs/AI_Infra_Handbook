# 1. 背景：从 chroot 到 OCI 标准化

> 一句话理解：容器**不是**某一天被发明出来的——它的每一项底层技术（chroot、namespace、cgroup、联合文件系统）都早就在 Linux 里存在了十几年；Docker 2013 年的真正贡献，是把这些散落的内核能力**加上一个可分发、可复现的镜像格式和极简 UX**，组合成一个让"一次构建、到处运行"真正落地的产品，随后又亲手把自己拆解成 containerd/runc 并推动 OCI 标准化——容器运行时的历史，就是一部"从单体到分层、从私有到标准"的演进史。

## 1.1 隔离的原始需求：一台机器跑多个互不干扰的东西

早在云原生这个词出现之前，系统管理员就有一个朴素诉求：**一台物理机/一台主机上跑多个服务或多个用户，且彼此不能互相窥视、互相拖垮。** 这催生了三条技术脉络：

### 脉络一：文件系统隔离 —— chroot（1979）→ BSD Jail（2000）→ Solaris Zones（2004）

- **`chroot`（1979，Bill Joy，为 Seventh Edition Unix 而做）**：最早的"容器"雏形。它通过 `chroot(2)` 系统调用**改变进程的根目录视图**——进程以为 `/` 就是某个子目录，看不到外面的文件系统。
  - 局限：`chroot` **只隔离文件系统**，不隔离进程、网络、用户。root 进程仍能逃逸（"chroot jail" 并不安全）。
  - 但它确立了"给进程一个受限的根目录视图"这一容器最核心的思想。
- **FreeBSD Jail（2000）**：在 chroot 基础上扩展，隔离了进程树、网络、用户，是第一个"接近容器"的系统级隔离方案。
- **Solaris Zones / Containers（2004）**：Sun 公司的企业级容器方案，提供强隔离与资源管理，在金融/电信领域长期使用。

> 这些方案证明了一件事：**不需要虚拟机也能做到进程隔离**——前提是内核能提供足够细粒度的隔离原语。Linux 内核随后沿这个方向补齐了自己的能力。

### 脉络二：资源限制 —— cgroups（2007）

进程即使隔离了文件系统，仍然共享 CPU、内存、IO 带宽。一个失控的进程可以吃光整机资源（即"吵闹的邻居"问题）。2007 年，Google 工程师 Paul Menage 和 Rohit Seth 向 Linux 内核提交了 **cgroups（control groups）** 补丁：

- cgroups 把进程分组，并对每个组施加 **CPU、内存、块设备 IO、网络、设备访问** 等资源的**限制与计量**。
- 这是容器"轻量隔离"的另一条腿——`chroot`/namespace 管"看得见什么"，cgroups 管"能用多少"。

### 脉络三：命名空间隔离 —— namespaces（2002–2013）

Linux 内核从 2.4.19（2002）开始陆续加入 **namespaces** 机制，逐个把"全局系统资源"变成"每进程一份的视图"：

| namespace | 加入年份 | 隔离的对象 |
|---|---|---|
| **mnt**（mount） | 2002 | 挂载点视图（文件系统） |
| **uts**（UNIX Timesharing） | 2006 | 主机名 / 域名（hostname） |
| **ipc** | 2006 | System V IPC、POSIX 消息队列 |
| **pid** | 2008 | 进程号（进程只看到自己命名空间内的 PID） |
| **net** | 2009 | 网络栈（网卡、路由、iptables、端口） |
| **user** | 2013（kernel 3.8） | 用户/组 ID 映射（容器内 root ≠ 宿主 root） |
| **cgroup** | 2016（kernel 4.6） | cgroup 视图 |
| **time** | 2020（kernel 5.6） | 系统时钟单调偏移 |

> **关键认知**：到 2013 年前后，Linux 内核**已经具备了构建容器所需的全部原语**——namespace（隔离可见性）+ cgroup（限制资源）+ 联合文件系统（overlayfs/aufs，分层镜像）。缺的不是技术，而是**把它们组合好用**的产品。

## 1.2 LXC（2008）：第一次"组装"，但太难用

**LXC（Linux Containers，2008，IBM 的 Daniel Lezcano 和 Stéphane Graber）** 是第一个把这些内核原语**组装成一个易用工具**的项目：用一条命令就能创建一个带网络、文件系统、资源限制的"Linux 容器"。

- LXC 的意义：证明了 "namespace + cgroup + 模板镜像" 的组合**可以工作**。
- LXC 的问题：它本质是"轻量虚拟机"——你需要**手动配置网络、手动准备 rootfs、手动管理生命周期**，体验接近"装一个精简版 Linux"。门槛高、不可移植、没有好的分发机制。

早期 Docker（0.x）**底层就调用 LXC** 来创建容器，直到 Docker 后来用 Go 重写了 libcontainer（即后来的 runc），才摆脱对 LXC 的依赖。所以准确地说：**Docker 把 LXC 的能力产品化了，而不是发明了隔离。**

## 1.3 Docker（2013）：把散落的原语变成"产品"

2013 年 3 月，dotCloud 公司的 Solomon Hykes 在 PyCon 展示了 Docker，并把它开源。Docker 之所以**引爆**行业，不是因为新内核技术，而是因为它在三件事上做到了前所未有的好：

### 贡献一：不可变、内容寻址的"镜像"格式

Docker 定义了一种**分层（layered）、内容寻址（content-addressed）、不可变（immutable）**的镜像格式：

- 一个镜像 = 多个**只读层（layer）**叠加，每层对应 Dockerfile 的一条指令；
- 每层用内容的 SHA256 摘要**寻址与去重**——相同层只存一份，相同基础镜像的容器共享底层；
- **联合文件系统**（aufs → overlay → overlayfs）把这些只读层 + 一个可写层"联合挂载"成统一的根文件系统视图。

这让镜像变得**可分发、可缓存、可复现**——这是 `tar` 包、虚拟机镜像（一个巨大的 qcow2 文件）都做不到的。

### 贡献二：极简的 UX

```bash
docker build -t myapp .      # 从 Dockerfile 构建
docker run -p 8080:80 myapp  # 一行启动，端口映射
docker push myapp            # 推到 registry
docker pull myapp            # 别人一行拉取运行
```

对比 LXC 的手动配置，Docker 的 `build / run / push / pull` 把"应用打包 → 运行 → 分发"压缩成几条命令。这是它"病毒式传播"的直接原因。

### 贡献三：Docker Hub —— 分发的生态

镜像仓库（registry）+ 一个公共的 Docker Hub，让"拉一个 nginx / redis / python / pytorch 就能跑"成为现实。生态网络效应一旦形成，就再难被取代。

> **结论**：Docker 的核心创新是**"镜像 + 分发 + UX"**，而不是内核隔离。理解这一点，才能理解为什么后来 Docker 的"运行时"部分会被剥离出去——因为隔离本身是 Linux 内核的公共能力，不该被一家产品垄断。

## 1.4 成功的隐患：Docker 是个"庞然大物"

2013–2015 的 Docker 是一个**单体（monolithic）daemon**：`dockerd` 一个进程包揽了镜像构建、镜像管理、网络、卷、容器生命周期、REST API、安全……几乎所有事情。这在早期很方便，但随着 K8s 等编排系统的兴起，问题暴露：

1. **太重、太难被编排系统集成**：K8s 想精确控制容器生命周期，但 dockerd 是个黑盒。
2. **安全**：root 守护进程掌控一切，攻击面大。
3. **不可替换**：Docker 既是构建工具、又是运行时、又是镜像格式的事实标准，社区担心被单一公司锁定。

业界开始要求：**把"运行容器"这件事标准化、解耦、可替换**。

## 1.5 2015：拆分与标准化 —— runC 捐赠、OCI 成立

2015 年是容器历史的关键转折年，三件事重塑了格局：

### （1）Docker 把 libcontainer 重命名为 runC 并捐赠

Docker 把自己用 Go 重写的、不再依赖 LXC 的运行时核心 **libcontainer** 重命名为 **runC**，作为独立项目，并以自由软件许可发布。runC 成为** OCI Runtime Specification 的参考实现**——即"如何用 namespace/cgroup/overlayfs 创建一个容器"的标准答案。

### （2）OCI（Open Container Initiative）成立

2015 年 6 月，在 Docker CoreOS 等推动下，Linux 基金会下成立 **OCI**，目标是制定**两个开放标准**：

- **Runtime Specification（runtime-spec）**：定义"如何运行一个容器"——传入一个 `config.json`（OCI bundle），运行时负责创建 namespace、cgroup、挂载 rootfs、启动进程。任何符合该规范的运行时（runc / crun / youki / runsc）应产生一致的结果。
- **Image Specification（image-spec）**：定义"镜像长什么样"——manifest、config、layers、内容寻址、manifest list（多架构）。任何符合规范的镜像都能被任何运行时拉取运行。

> OCI 的意义：把 Docker 的"私有镜像格式 + 私有运行时"变成**公共标准**。从此镜像和运行时都可以解耦替换——这是整个云原生生态能繁荣的根基。

### （3）Docker 把 containerd 捐赠给 CNCF

Docker 从 dockerd 中**剥离出 containerd**（高层运行时核心：管理镜像、容器生命周期、镜像拉取、快照），2017 年捐赠给 CNCF，2019 年毕业。containerd 被设计成**可嵌入、可被编排系统直接调用**的精简运行时。

至此，原本的"单体 dockerd"被拆成清晰的层次：

```
docker CLI  ── 用户接口（可选）
   │
dockerd     ── Docker Engine（构建/网络/卷/REST API，可选层）
   │
containerd  ── 高层运行时：镜像管理 + 容器生命周期 + CRI（CNCF 项目）
   │
runc        ── 低层运行时：OCI Runtime Spec 参考实现（实际创建容器）
   │
Linux 内核   ── namespace + cgroup + overlayfs（真正的隔离）
```

## 1.6 CRI 与 dockershim 的终局

### CRI（Container Runtime Interface，K8s v1.5，2016）

为了让 K8s 能调用任意符合接口的容器运行时，K8s 在 v1.5（2016）引入 **CRI** ——一个 gRPC 接口，定义了 kubelet 与容器运行时之间的契约（`RuntimeService` 管容器生命周期、`ImageService` 管镜像）。任何运行时只要实现 CRI，就能被 K8s 调用。

### dockershim：临时的桥梁，终被移除

早期 K8s 只支持 Docker，但 Docker 不直接实现 CRI。于是 K8s 在 kubelet 里塞了一个 **dockershim** —— 适配层，把 CRI 调用翻译成 Docker 的 API。

问题：dockershim 维护成本高、限制了 K8s 演进、维护了一个只为兼容 Docker 的特殊路径。而 Docker 镜像本就符合 OCI 规范，**用 containerd 或 CRI-O 直接运行 Docker 镜像毫无问题**。

**K8s v1.24（2022 年 5 月）正式移除 dockershim**。这意味着：

- K8s 节点上不再需要 dockerd，**默认运行时是 containerd**（GKE/EKS/AKS 等托管集群默认）；
- CRI-O（Red Hat/OpenShift 生态主导）是另一个主流选择；
- **Docker 构建的镜像（OCI 兼容）仍可在 K8s 上正常运行**——移除的是 dockershim 这个运行时适配层，不是镜像。这是社区反复澄清、却仍被误解的一点。

> 对 AI 平台工程师的实际影响：你仍然可以用 `docker build` 构建镜像，K8s 节点用 containerd 运行它。区别只是节点上不再有 `dockerd`，调试要用 `crictl` / `nerdctl` 而不是 `docker`。

## 1.7 演进时间线总结

| 年份 | 事件 | 意义 |
|---|---|---|
| 1979 | `chroot` 进入 Unix | 文件系统隔离的最早雏形 |
| 2002–2013 | Linux namespaces 逐个加入内核 | 进程级隔离的内核基础逐步完备 |
| 2007 | cgroups 进入 Linux 内核 | 资源限制的内核基础 |
| 2008 | LXC 发布 | 第一次把 namespace+cgroup 组装成工具 |
| 2013 | Docker 开源 | 镜像+UX+分发引爆容器化 |
| 2015 | runC 捐赠、OCI 成立、containerd 剥离 | 运行时标准化与解耦 |
| 2016 | K8s v1.5 引入 CRI | 编排与运行时接口标准化 |
| 2017 | containerd 捐赠 CNCF | 运行时成为社区资产 |
| 2019 | containerd 从 CNCF 毕业 | 生产可用，成为事实默认 |
| 2022 | K8s v1.24 移除 dockershim | containerd/CRI-O 成默认，Docker Engine 退出 K8s 节点 |
| 2024 | OCI Runtime Spec v1.2、Image Spec v1.1；containerd 2.x | 标准持续演进（zstd 压缩、subject/reference-types、cgroup v2） |

## 本章小结

容器运行时的历史不是"某个人发明了容器"，而是**三股技术脉络（文件系统隔离、资源限制、命名空间）经过十几年在内核里的沉淀，被 Docker 在 2013 年用一个'镜像 + 极简 UX + 分发生态'的产品组合引爆**。但单体 Docker 的不可替代性引发了社区对锁定的担忧，于是 2015 年发生了关键的"拆分与标准化"：runC 被捐赠、OCI 制定 runtime/image 两大规范、containerd 剥离并最终成为 CNCF 毕业项目。K8s 用 CRI 接口把"运行容器"这件事彻底抽象化，并在 v1.24 移除 dockershim，让 containerd/CRI-O 成为默认。今天我们说"容器运行时"，指的就是这套**分层、标准、可替换**的体系——`Docker CLI / nerdctl / crictl`（接口）→ `containerd / CRI-O`（高层运行时）→ `runc / crun / youki`（低层运行时）→ Linux 内核（真正的隔离）。理解这条演进史，你才能理解为什么容器运行时"既简单（就是几个系统调用）又复杂（背后是十几年标准化与解耦的工程智慧）"。

**参考来源**

- [Open Container Initiative（OCI）官网](https://opencontainers.org/)
- [OCI Runtime Specification](https://github.com/opencontainers/runtime-spec)
- [OCI Image Specification](https://github.com/opencontainers/image-spec)
- [runC 仓库](https://github.com/opencontainers/runc)
- [containerd 仓库与架构文档](https://github.com/containerd/containerd)
- [Kubernetes CRI 文档](https://kubernetes.io/zh-cn/docs/concepts/architecture/cri/)
- [Kubernetes v1.24 dockershim 移除公告](https://kubernetes.io/blog/2022/02/17/dockershim-faq/)
- [LXC 项目](https://linuxcontainers.org/)
- [FreeBSD Jail 文档](https://docs.freebsd.org/en/books/handbook/jails/)
