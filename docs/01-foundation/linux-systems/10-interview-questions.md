# 10. 面试题

## 初级

### Q1：Linux 里进程和线程有什么区别？

进程是资源分配的基本单位，有独立的地址空间、文件描述符表等；线程是 CPU 调度的基本单位，共享进程的资源，但有自己的栈和寄存器。Linux 里线程本质上也是进程，通过 `clone()` 控制共享哪些资源。

### Q2：什么是系统调用？为什么它开销大？

系统调用是用户空间请求内核服务的接口。开销来自用户态/内核态切换、特权级切换、上下文保存和恢复。频繁系统调用会成为瓶颈。

### Q3：什么是文件描述符？

文件描述符是内核中打开文件或资源的引用，是一个非负整数。它指向内核的 `file` 结构，普通文件、socket、pipe、设备都通过文件描述符操作。

### Q4：`top` 里的 `us`、`sy`、`id`、`wa` 分别代表什么？

- `us`：用户态 CPU 时间；
- `sy`：内核态 CPU 时间；
- `id`：空闲；
- `wa`：等待 I/O。

### Q5：进程有哪些状态？

R（运行/就绪）、S（可中断睡眠）、D（不可中断睡眠）、T（停止）、Z（僵尸）、I（空闲）。

## 中级

### Q6：解释 CFS 调度器的基本原理。

CFS（Completely Fair Scheduler）用红黑树维护进程的 `vruntime`，总是选择 vruntime 最小的进程运行。nice 值影响 vruntime 增长速度，nice 越低，进程越容易获得 CPU。

### Q7：NUMA 是什么？为什么对 AI 训练重要？

NUMA（Non-Uniform Memory Access）指多路服务器上 CPU 访问本地内存比远程内存更快。AI 训练需要高内存带宽，错误的 NUMA 绑定会显著降低性能，因此常用 `numactl` 绑定 CPU 和内存节点。

### Q8：cgroup v1 和 v2 有什么区别？

cgroup v1 各子系统独立挂载；cgroup v2 统一层级，接口更一致，支持 `memory.high` 等更细粒度控制。Kubernetes 1.25+ 默认 cgroup v2。

### Q9：什么是 page cache？它和 direct I/O 有什么区别？

page cache 是内核用来缓存磁盘数据的内存。buffered I/O 走 page cache，适合随机读；direct I/O 绕过 page cache，适合大文件顺序读写。

### Q10：为什么容器里进程被 OOM kill，但 `free` 显示还有内存？

容器受 cgroup memory limit 约束，超出容器自己的 `memory.max` 就会触发 cgroup OOM，即使节点还有空闲内存。

## 高级

### Q11：一次 `read()` 系统调用的完整流程是什么？

用户程序 → glibc → `syscall` 指令 → `do_syscall_64` → `sys_read` → VFS → 具体文件系统（如 ext4）→ page cache 或块层 → 设备驱动 → 数据拷贝回用户空间 → 返回用户态。

### Q12：什么是 CPU throttle？怎么排查？

CPU throttle 是 cgroup 的 CPU quota 用完后，内核强制进程等待下一个周期。表现为延迟抖动。可以用 `cat /sys/fs/cgroup/cpu.stat` 查看 `nr_throttled` 和 `throttled_usec`。

### Q13：如何降低分布式训练中的网络延迟？

- 使用 RDMA/InfiniBand 替代 TCP；
- 正确配置 IRQ affinity，把网卡中断绑定到非业务 CPU；
- 启用 RPS/RFS/XPS 优化软中断分布；
- 考虑 busy polling；
- 调整 NCCL 环境变量和拓扑配置。

### Q14： HugePages 为什么能提升大模型训练性能？

HugePages 减少页表项数量和 TLB miss。大模型访问的内存地址空间大，TLB miss 开销高，使用 HugePages 可以提升地址转换效率和内存访问速度。

### Q15：设计一个 AI 推理服务的 Linux 性能基线采集方案。

应包括：

- 应用指标：QPS、P50/P99 latency、错误率；
- CPU：使用率、上下文切换、irq、softirq、throttle；
- 内存：RSS、page cache、swap、OOM；
- I/O：磁盘吞吐、I/O wait、fsync 延迟；
- 网络：吞吐、重传、RTT；
- GPU：利用率、显存、PCIe 带宽；
- 用 Prometheus + Grafana 持续采集，配合 `perf` / `bpftrace` 做深入分析。

## 本节小结

面试题覆盖了从概念到系统调用、调度、内存、I/O、网络、cgroup 和生产排障的多个层次。理解机制比背命令更重要。
