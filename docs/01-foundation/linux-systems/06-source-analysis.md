# 6. 源码分析：一个系统调用的完整链路

Linux 内核源码很大，但不需要全读完。本节教你怎么抓住一条主线：从一个 `read()` 系统调用出发，穿过系统调用入口、VFS、page cache、文件系统，最后回到用户空间。

## 6.1 Linux 源码怎么读

### 源码结构

```
linux/
├── arch/          # 架构相关代码
├── kernel/        # 进程调度、系统调用、中断等核心
├── mm/            # 内存管理
├── fs/            # 文件系统
├── net/           # 网络
├── block/         # 块层
├── drivers/       # 设备驱动
├── include/       # 头文件
├── init/          # 初始化
└── tools/         # 工具
```

AI Infra 工程师读源码时，重点看：

- `kernel/sched/`：调度器；
- `mm/`：内存管理；
- `fs/`：文件系统；
- `kernel/cgroup/`：cgroup 实现。

### 阅读方法

1. 先用 `lxr` / `elixir` / GitHub 搜索找到入口函数；
2. 跟着函数调用链走，不要一开始就看所有细节；
3. 用 `grep` 找关键数据结构；
4. 看注释和 commit message；
5. 遇到看不懂的宏和条件编译先跳过，抓主线。

## 6.2 `read()` 系统调用的完整链路

### 用户态入口：glibc

你的程序调用 `read(fd, buf, count)`，glibc 会把它包装成系统调用：

```c
// 简化示意
mov rax, 0        // __NR_read
mov rdi, fd
mov rsi, buf
mov rdx, count
syscall
```

### 内核态入口

x86-64 上，`syscall` 指令会跳转到 `entry_SYSCALL_64`：

```asm
// arch/x86/entry/entry_64.S
ENTRY(entry_SYSCALL_64)
    swapgs
    mov    %rsp, PER_CPU_VAR(rsp_scratch)
    mov    PER_CPU_VAR(cpu_current_top_of_stack), %rsp
    ...
    call   do_syscall_64
```

`do_syscall_64` 在 `arch/x86/entry/common.c` 中，根据 `rax` 里的系统调用号找到处理函数：

```c
// arch/x86/entry/common.c
void do_syscall_64(struct pt_regs *regs)
{
    regs->ax = sys_call_table[regs->ax](regs);
}
```

`sys_call_table` 定义在 `arch/x86/entry/syscalls/syscall_64.c`。

### sys_read

系统调用表指向 `ksys_read`：

```c
// fs/read_write.c
ssize_t ksys_read(unsigned int fd, char __user *buf, size_t count)
{
    struct fd f = fdget(fd);
    ...
    ret = vfs_read(f.file, buf, count, &pos);
    ...
}
```

### VFS 层

`vfs_read` 调用具体文件系统的 `read` 方法：

```c
// fs/read_write.c
ssize_t vfs_read(struct file *file, char __user *buf, size_t count, loff_t *pos)
{
    ...
    ret = file->f_op->read(file, buf, count, pos);
    // 或者 aio_read / read_iter
}
```

### 文件系统层：以 ext4 为例

ext4 的 `read_iter` 会走到 `generic_file_read_iter`：

```c
// mm/filemap.c
ssize_t generic_file_read_iter(struct kiocb *iocb, struct iov_iter *iter)
{
    ...
    if (iocb->ki_flags & IOCB_DIRECT) {
        // Direct I/O，绕过 page cache
        return generic_file_direct_read(iocb, iter, ...);
    }
    // Buffered I/O，先查 page cache
    return generic_file_buffered_read(iocb, iter, ...);
}
```

### Page Cache

如果走 buffered I/O，内核会调用 `pagecache_get_page` 查找缓存页：

```c
// mm/filemap.c
struct page *pagecache_get_page(struct address_space *mapping, pgoff_t index,
                                fgp_t fgp_mask, gfp_t gfp_mask)
{
    ...
    page = find_get_entry(mapping, index);
    if (radix_tree_exceptional_entry(page))
        ...
}
```

命中 page cache 就直接把数据拷贝到用户空间（`copy_page_to_iter`）。没命中就发起 I/O：

```c
// mm/filemap.c
static int filemap_fault(...)
{
    // 分配物理页，向块层发请求，把文件内容读入 page cache
}
```

### 块层

块层把文件系统的请求转换成对块设备的请求。`submit_bio` 是关键入口：

```c
// block/blk-core.c
blk_qc_t submit_bio(struct bio *bio)
{
    ...
    return generic_make_request(bio);
}
```

`bio` 经过 I/O 调度器，最终发到设备驱动。

### 返回用户空间

数据读入 page cache 后，内核把数据从内核空间拷贝到用户空间的 `buf`。这里有一次内存拷贝。

最后，`ksys_read` 返回读取的字节数，控制权回到 glibc，再返回给用户程序。

## 6.3 CFS 核心数据结构

### sched_entity

每个可调度实体（进程/线程）都有一个 `sched_entity`：

```c
// include/linux/sched.h
struct sched_entity {
    struct load_weight      load;
    struct rb_node          run_node;
    u64                     vruntime;
    u64                     exec_start;
    u64                     sum_exec_runtime;
    ...
};
```

### cfs_rq

每个 CPU 的 CFS 运行队列：

```c
// kernel/sched/sched.h
struct cfs_rq {
    struct load_weight load;
    unsigned long runnable_weight;
    struct rb_root_cached tasks_timeline;
    ...
};
```

`tasks_timeline` 就是按 vruntime 排序的红黑树。

### 调度时机

`schedule()` 函数是调度器的总入口。它在以下时机被调用：

- 进程主动放弃 CPU（`sched_yield`、`sleep`）；
- 时间片用完；
- 从中断/系统调用返回时检查 TIF_NEED_RESCHED。

## 6.4 cgroup v2 的核心实现

### cgroup 文件系统

cgroup v2 统一挂载到 `/sys/fs/cgroup`：

```bash
mount -t cgroup2 none /sys/fs/cgroup
```

内核中，cgroup 是一个伪文件系统，类型为 `cgroup2_fs_type`。

### cgroup 子系统

每个控制器（cpu、memory、pids 等）注册到 cgroup：

```c
// kernel/cgroup/cgroup.c
struct cgroup_subsys {
    const char *name;
    struct cgroup_subsys_state *(*css_alloc)(...);
    ...
};
```

CPU 控制器在 `kernel/sched/core.c` 附近与调度器交互；memory 控制器在 `mm/memcontrol.c`。

### 资源限制如何生效

以 CPU quota 为例：

1. 用户写入 `cpu.max`；
2. cgroup 文件系统调用 cpu 控制器的 `write_u64`；
3. 更新 `cfs_bandwidth` 结构；
4. CFS 调度器在运行时检查该 cgroup 的 quota 是否用完；
5. 用完则 throttle，让出 CPU。

## 6.5 阅读内核源码的建议

1. **抓主线**：不要陷入每个宏和分支；
2. **用工具**：LXR、elixir.bootlin.com、GitHub 搜索；
3. **看版本**：不同内核版本差异大，确认你读的是对应版本；
4. **配合文档**：Kernel Documentation 比源码更容易入门；
5. **动手实验**：改一个内核参数或 bpftrace 脚本，验证你的理解。

## 6.6 本节小结

- `read()` 系统调用的链路：glibc → syscall → do_syscall_64 → vfs_read → ext4 → page cache → 块层 → 设备驱动；
- CFS 核心：sched_entity、cfs_rq、红黑树、vruntime；
- cgroup v2：统一层级、控制器注册、cfs_bandwidth 控制 CPU quota；
- 读内核源码要抓主线，配合文档和工具，不要陷入细节。

下一节进入工程实践：用 Python 写一个 Linux 机制模拟器。
