# 2. 核心思想：Kernel、系统调用与进程模型

Linux 看似复杂，但底层只回答三个问题：

1. **谁在用 CPU？**（进程调度）
2. **谁在用内存？**（内存管理）
3. **怎么和外部世界交互？**（I/O、网络、文件系统）

本章先建立几个核心概念的直觉。

## 2.1 Kernel Space vs User Space

Linux 把内存分成两个世界：

- **Kernel Space（内核空间）**：操作系统内核运行的区域，拥有最高权限，可以直接访问硬件；
- **User Space（用户空间）**：普通应用程序运行的区域，权限受限，不能直接访问硬件。

```mermaid
flowchart LR
    A[用户空间<br/>应用程序] -->|系统调用| B[内核空间<br/>操作系统]
    B -->|返回结果| A
```

用户空间的程序想读文件、开网络连接、申请内存，都必须通过 **系统调用（system call）** 进入内核空间。

这种隔离有两个好处：

1. **安全**：用户程序不能随便破坏系统；
2. **稳定**：一个用户程序崩溃不会导致整个系统崩溃。

## 2.2 系统调用：用户与内核的“电话”

系统调用是用户程序请求内核服务的唯一正规渠道。

常见系统调用：

| 系统调用 | 作用 |
|---|---|
| `fork` | 创建新进程 |
| `execve` | 加载并执行新程序 |
| `read` / `write` | 读写文件或 socket |
| `open` / `close` | 打开/关闭文件 |
| `mmap` | 内存映射文件或分配内存 |
| `brk` / `sbrk` | 调整堆内存大小 |
| `clone` | 创建线程或 namespace |
| `exit` | 终止进程 |

系统调用的开销：每次系统调用都要从用户态切换到内核态，再切回来，这涉及上下文切换和特权级切换。频繁的系统调用会成为性能瓶颈。

## 2.3 进程、线程与协程

### 进程（Process）

进程是操作系统资源分配的基本单位。每个进程有独立的：

- 地址空间（虚拟内存）；
- 打开的文件描述符；
- 信号处理；
- cgroup 和 namespace 归属。

### 线程（Thread）

线程是 CPU 调度的基本单位。同一进程内的多个线程共享：

- 地址空间；
- 文件描述符；
- 代码段和数据段。

但每个线程有自己的：

- 程序计数器；
- 寄存器；
- 栈。

在 Linux 里，线程本质上也是进程，只是它们共享很多资源。`clone()` 系统调用可以控制共享哪些资源。

### 协程（Coroutine）

协程是用户态的轻量级调度单位，由程序自己管理，不经过操作系统。Python 的 asyncio、Go 的 goroutine、C++20 的 co_await 都是协程。

| 概念 | 调度者 | 切换开销 | 地址空间 |
|---|---|---|---|
| 进程 | 操作系统 | 大 | 独立 |
| 线程 | 操作系统 | 中 | 共享 |
| 协程 | 用户程序 / 运行时 | 小 | 共享 |

## 2.4 文件即一切（Everything is a File）

Unix/Linux 的一个核心设计哲学是：**几乎所有东西都是文件。**

- 普通文件是文件；
- 目录是文件；
- 设备（`/dev/sda`、`/dev/nvidia0`）是文件；
- 进程信息（`/proc/<pid>/status`）是文件；
- 网络 socket 也是文件描述符。

这种统一抽象让 Linux 可以用同一套接口（open/read/write/close/ioctl）操作 wildly different 的东西。

## 2.5 Namespace：进程的“视图隔离”

Linux Namespace 让一组进程看到“自己的一份系统视图”。

| Namespace | 隔离内容 |
|---|---|
| PID | 进程 ID |
| Mount | 文件系统挂载点 |
| Network | 网络设备、IP、路由 |
| UTS | 主机名和域名 |
| IPC | System V IPC 和 POSIX message queues |
| User | 用户和组 ID |
| Cgroup | cgroup 根目录 |
| Time | 系统时间（较新） |

容器（Docker/Kubernetes Pod）就是利用 namespace 实现的隔离。注意：**namespace 提供的是视图隔离，不是资源限制**。资源限制由 cgroup 负责。

## 2.6 Cgroup：资源的“硬边界”

cgroup（control group）是 Linux 用来对进程组做资源限制和统计的机制。

主要资源子系统：

| 子系统 | 控制内容 |
|---|---|
| cpu | CPU 使用（shares、quota、period） |
| cpuacct | CPU 使用统计 |
| memory | 内存限制和统计 |
| blkio | 块设备 I/O 限制 |
| pids | 进程数限制 |
| devices | 设备访问权限 |
| net_cls / net_prio | 网络流量标记和优先级 |

cgroup v1 把各子系统挂载到不同目录；cgroup v2 统一了层级结构，功能更强大，是未来的标准。

Kubernetes 的 CPU limit/request、memory limit/request，最终都翻译成 cgroup 配置。

## 2.7 权限模型

Linux 权限基于：

- **用户（User）** 和 **组（Group）**；
- **读（r）、写（w）、执行（x）** 三种权限；
- 文件所有者、所属组、其他用户三类主体。

现代 Linux 还有更细粒度的安全机制：

- **SELinux**：基于标签的强制访问控制（MAC）；
- **AppArmor**：基于路径的强制访问控制；
- **Capabilities**：把 root 权限拆分成多个独立能力（如 `CAP_SYS_ADMIN`、`CAP_NET_ADMIN`）。

容器安全经常涉及这些机制。

## 2.8 延迟 vs 吞吐

Linux 设计经常要在延迟和吞吐之间取舍：

- **延迟（Latency）**：一个请求从发起到完成的时间；
- **吞吐（Throughput）**：单位时间内完成的请求数量。

AI 训练通常追求**吞吐**（尽量多算数据）；AI 推理通常追求**低延迟**（尽快响应一个请求）。Linux 的调度器、I/O 调度器、网络参数都要根据场景调整。

## 2.9 核心概念速查表

| 概念 | 一句话解释 |
|---|---|
| Kernel Space | 内核运行的特权内存区域 |
| User Space | 普通程序运行的受限内存区域 |
| System Call | 用户程序请求内核服务的接口 |
| Process | 资源分配的基本单位，有独立地址空间 |
| Thread | CPU 调度的基本单位，共享进程资源 |
| Coroutine | 用户态轻量级调度单位 |
| Namespace | 进程的视图隔离机制 |
| Cgroup | 进程组的资源限制和统计机制 |
| File Descriptor | 内核中打开文件或资源的引用 |
| Capability | 细粒度的 root 权限拆分 |

## 2.10 本节小结

Linux 的核心思想可以总结为：

1. **内核空间和用户空间分离**，通过系统调用交互；
2. **进程是资源单位，线程是调度单位**；
3. **一切皆文件**，统一了 I/O 接口；
4. **Namespace 做隔离，Cgroup 做限制**；
5. **延迟和吞吐是永恒的权衡**。

下一节，我们把镜头拉近，看 Linux 内核的整体架构。
