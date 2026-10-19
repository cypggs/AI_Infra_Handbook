# 3. 架构设计：Linux 内核全景

Linux 内核是一个巨大的软件，但我们可以用一张图先抓住它的骨架。理解架构的好处是：遇到问题你能判断“这事归哪个子系统管”。

## 3.1 Linux 内核整体架构

```mermaid
flowchart TD
    A[用户空间<br/>应用程序 / 库 / Shell] -->|系统调用 / io_uring| B[系统调用接口<br/>System Call Interface]
    B --> C[VFS<br/>虚拟文件系统]
    B --> D[进程调度<br/>CFS / RT / Deadline / sched_ext]
    B --> E[内存管理<br/>MM]
    B --> F[网络协议栈<br/>Network Stack]
    B --> G[进程间通信<br/>IPC]
    B --> X[eBPF 虚拟机<br/>可编程挂接点]
    X -.-> D
    X -.-> F
    X -.-> C
    C --> H[具体文件系统<br/>ext4 / xfs / btrfs]
    H --> I[块层 / I/O 调度器<br/>Block Layer / io_uring]
    I --> J[设备驱动<br/>SSD / HDD / NVMe]
    E --> K[页缓存<br/>Page Cache]
    E --> L[swap / zram]
    F --> M[网卡驱动<br/>NIC Driver]
    D --> N[CPU]
    E --> N
    M --> O[网络硬件<br/>NIC / RDMA]
```

这张图简化了很多，但足够建立直觉：

- **系统调用接口**：用户空间和内核的分界线；除了同步系统调用，还有 **io_uring** 这条异步批量提交 I/O 的旁路（见 3.7）；
- **VFS**：统一不同文件系统的抽象层；
- **进程调度**：决定哪个进程/线程在 CPU 上运行；
- **内存管理**：虚拟内存、物理内存、swap；
- **网络协议栈**：socket、TCP/IP、网卡驱动；
- **块层/I/O 调度器**：管理磁盘 I/O 请求；
- **eBPF 虚拟机**：横跨多个子系统的可编程挂接层，2025-2026 年已成为内核一等公民；
- **设备驱动**：让内核能操作具体硬件。

## 3.2 系统调用接口

系统调用接口是内核暴露给用户空间的大门。所有 `libc` 函数（如 `fopen`、`malloc`、`pthread_create`）最终都会调用到这里。

Linux 的系统调用号定义在 `arch/x86/entry/syscalls/syscall_64.tbl` 等架构相关文件中。

进入内核的方式（x86-64）：

1. 用户程序把系统调用号放到 `rax` 寄存器；
2. 参数放到 `rdi`、`rsi`、`rdx` 等寄存器；
3. 执行 `syscall` 指令；
4. CPU 切换到内核态，内核根据系统调用号找到处理函数；
5. 处理完后通过 `sysret` 返回用户态。

## 3.3 虚拟文件系统（VFS）

VFS 是 Linux 文件系统的抽象层。它让内核可以用统一的接口支持 ext4、xfs、btrfs、nfs、procfs、sysfs 等完全不同的文件系统。

VFS 定义了四个核心对象：

| 对象 | 含义 |
|---|---|
| superblock | 文件系统的整体信息 |
| inode | 文件的元数据（权限、大小、时间、块位置） |
| dentry | 目录项，加速路径查找 |
| file | 打开的文件实例，包含读写位置 |

当你 `open("/data/model.bin")` 时：

1. VFS 根据路径找到 dentry；
2. dentry 指向 inode；
3. inode 指向具体文件系统的数据块；
4. 返回一个 file descriptor 给用户空间。

## 3.4 进程调度子系统

Linux 的进程调度器决定：在任意时刻，哪个进程在哪个 CPU 上运行。

主要调度类：

| 调度类 | 用途 |
|---|---|
| CFS（Completely Fair Scheduler） | 普通进程，默认调度类 |
| RT（Real-Time） | 实时进程，SCHED_FIFO / SCHED_RR |
| Deadline | 截止时间调度，SCHED_DEADLINE |
| **sched_ext** | **用 eBPF 实现的调度类（6.12+），可热加载自定义调度策略** |
| Idle / Stop | 特殊用途 |

CFS 是绝大多数 AI 程序的调度类。它的核心思想是：**尽量让每个进程获得公平的 CPU 时间**。它用红黑树维护进程的 `vruntime`（虚拟运行时间），总是选择 vruntime 最小的进程运行。

sched_ext 是 2024 年底合入主线、2025-2026 年快速成熟的新机制：调度决策被导出为一组 BPF 回调（`ops.select_cpu`、`ops.enqueue`、`ops.dispatch` 等），社区已经出现 scx_rusty、scx_layered、Google 的 BPF-CCX 等生产级 BPF 调度器，用于负载分层、缓存亲和和大核/小核分配等场景。2026 年的三个关键里程碑：**7.0 落地 SCHED_DEADLINE server**（sched_ext 任务也能获得 deadline 保证）；**7.1/7.2 逐步铺入 sub-scheduler 基础设施**；**7.3（2026-10 发布）完成 per-cgroup sub-scheduler**——不同 cgroup 可以运行不同的 BPF 调度器，并支持基于 capability 的 CPU 委派。此外 7.2 让主调度器具备了 LLC 缓存感知（尽量把共享数据的任务放在同一缓存域）。

## 3.5 内存管理子系统

Linux 内存管理负责：

- 虚拟地址到物理地址的映射（页表）；
- 物理内存的分配与回收；
- Swap 和 OOM；
- Page cache；
- HugePages；
- NUMA 内存策略。

### 页表与 TLB

每个进程有自己的页表，记录虚拟页到物理页的映射。CPU 通过 MMU（Memory Management Unit）做地址转换。

为了加速地址转换，CPU 有 **TLB（Translation Lookaside Buffer）** 缓存最近用过的页表项。TLB miss 会导致额外的内存访问，降低性能。

### HugePages

标准页大小是 4KB。大页（HugePages）可以是 2MB 或 1GB。大页的好处：

- 减少页表项数量；
- 减少 TLB miss；
- 大模型训练常用来 pin 住大段内存。

## 3.6 网络子系统

Linux 网络协议栈从底到上大致是：

```
应用层 → Socket API → TCP/UDP/IP → Netfilter → 网卡驱动 → 网卡硬件
```

现代 AI 基础设施对网络有两个优化方向：

1. **内核 bypass**：DPDK、RDMA、XDP 绕过内核协议栈，直接操作网卡；
2. **内核优化**：busy polling、RPS/RFS、XPS、IRQ affinity，减少中断和上下文切换。

## 3.7 块层与 I/O 调度器

块层处理所有块设备（磁盘、SSD）的 I/O 请求。

传统 I/O 调度器：

| 调度器 | 特点 |
|---|---|
| noop | 几乎不做调度，适合 SSD/NVMe |
| deadline | 保证每个请求有截止时间，适合混合读写 |
| cfq | 按进程队列轮转，公平分配带宽 |

现代 NVMe 通常用 `none` 或 `mq-deadline`，因为 SSD 延迟低、并行度高，复杂的调度反而成为瓶颈。

### io_uring：异步 I/O 的“新正门”

传统 I/O 要么走同步系统调用（`read`/`write`），要么走 `epoll + 非阻塞` 的事件循环。两者都有开销：前者每次都要陷入内核，后者每次 ready 后还要再发起一次系统调用。

**io_uring**（5.1 引入，2025-2026 年持续增强）用一对共享环形队列（submission queue / completion queue）解决这个问题：

```mermaid
flowchart LR
    A[用户程序<br/>把 SQE 写入提交环] --> B[内核<br/>批量消费 SQE]
    B --> C[执行 I/O<br/>无需每次陷入内核]
    C -->|写入完成环 CQE| A
```

- **批量提交、批量收割**：一次系统调用提交成百上千个 I/O；
- **内核轮询（SQPOLL）**：高 IOPS 场景下连系统调用都可以省掉；
- **multishot poll/recv**（5.13 起）：一次注册，多次收割，替代 epoll 监听；
- **NVMe uring_cmd 透传**：绕过块层直接向 NVMe 设备发命令，被 FAST'24 论文验证为高效的 I/O 路径；
- **zcrx 零拷贝 socket**（6.19 起持续增强）：把零拷贝收发推进到内核默认网络路径；
- **struct_ops 可编程事件循环**（7.1）：可以用 BPF 定制 `io_uring_enter` 的执行逻辑，把“事件循环”也变成可扩展点；
- 安全持续加固：2026 年修复了 multishot recv 丢失 EOF（CVE-2026-23473）、FUSE io_uring 门控（CVE-2026-90095）等问题。

今天的高性能推理网关（如部分 vLLM 前后置代理）、数据库（PostgreSQL 17+ 提供 io_uring 实验选项 `io_method`）和存储组件都在向 io_uring 迁移。liburing 2.15（2026-06）是当前稳定用户态库。

## 3.8 中断与软中断

当硬件有事件需要内核处理（如网卡收到包、磁盘 I/O 完成），会触发 **中断（Interrupt）**。

- **硬中断（Hardware IRQ）**：硬件直接触发，处理要非常快；
- **软中断（Soft IRQ）**：硬中断把大部分工作延后到软中断处理；
- **Tasklet / Workqueue**：更灵活的延后处理机制。

网络高吞吐场景下，中断处理可能成为瓶颈。常用优化：

- **RPS（Receive Packet Steering）**：把软中断分发到多个 CPU；
- **RFS（Receive Flow Steering）**：把同一条流的处理绑定到同一个 CPU；
- **XPS（Transmit Packet Steering）**：优化发送端；
- **IRQ affinity**：把硬中断绑定到特定 CPU。

## 3.9 现代 Linux 发行版组件

一个现代服务器 Linux 系统还包含：

| 组件 | 作用 |
|---|---|
| systemd | 初始化系统和服务管理 |
| journald | 系统日志 |
| udev | 设备文件动态管理 |
| SELinux / AppArmor | 强制访问控制 |
| NetworkManager / systemd-networkd | 网络配置 |
| chrony / ntpd | 时间同步 |

AI 平台工程师经常需要和 systemd unit、cgroup 集成、journal 日志打交道。

## 3.10 本节小结

Linux 内核可以分成几个核心子系统：

1. **系统调用接口**：用户空间和内核的分界线（以及 io_uring 异步旁路）；
2. **VFS**：统一文件系统抽象；
3. **进程调度**：CFS/RT/Deadline/sched_ext；
4. **内存管理**：虚拟内存、页表、TLB、HugePages；
5. **网络协议栈**：socket、TCP/IP、网卡驱动；
6. **块层/I/O 调度器**：磁盘 I/O 管理；
7. **中断/软中断**：硬件事件处理；
8. **eBPF 挂接层**：横跨调度、网络、文件系统的可编程扩展点；
9. **systemd 等用户态组件**：服务管理与初始化。

下一节，我们深入进程与系统调用。
