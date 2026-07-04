# 6. 源码分析：TCP CUBIC 拥塞控制

网络源码很多，但不需要全读完。本节聚焦一个对 AI 推理和大数据传输都很关键的机制：Linux 内核中的 TCP CUBIC 拥塞控制算法。

## 6.1 为什么选择 CUBIC

CUBIC 是 Linux 多年来的默认 TCP 拥塞控制算法。它的设计目标是：

- 在高带宽、高 RTT 网络中快速恢复窗口；
- 在丢包后平滑降低窗口，减少抖动；
- 保持对 Reno 的友好性。

AI 场景：从对象存储拉取大模型 checkpoint、跨节点传输大日志、HTTP 推理服务的长连接，都可能受 CUBIC 影响。

## 6.2 CUBIC 的核心思想

CUBIC 把拥塞窗口 `cwnd` 看作时间 `t` 的立方函数：

```
W(t) = C * (t - K)^3 + Wmax
```

- `Wmax`：上一次丢包时的窗口大小；
- `K`：窗口从 `Wmax` 降到 0 所需的时间；
- `C`：常数，控制增长激进程度。

丢包后，窗口乘性减少（通常降到 0.7 * Wmax），然后按立方函数重新增长。

```mermaid
flowchart LR
    A[丢包] --> B[cwnd = β * Wmax]
    B --> C[按立方函数增长 cwnd]
    C --> D[接近 Wmax 时增长变慢]
    D --> E[超过 Wmax 后探索更高带宽]
```

## 6.3 Linux 源码入口

CUBIC 实现在 `net/ipv4/tcp_cubic.c`。

### 关键结构体

```c
// include/net/tcp.h
struct tcp_sock {
    u32 snd_cwnd;       // 拥塞窗口
    u32 snd_ssthresh;   // 慢启动阈值
    ...
};
```

### cubic 私有数据

```c
// net/ipv4/tcp_cubic.c
struct bictcp {
    u32    cnt;            // 每 ACK 增加 cwnd 的计数
    u32    last_max_cwnd;  // 上一次最大窗口
    u32    last_cwnd;      // 上一次 cwnd
    u32    last_time;      // 上一次更新时间
    u32    bic_origin_point;
    u32    bic_K;
    s32    bic_tcp_cwnd;
    u32    ack_cnt;
    ...
};
```

### 拥塞窗口更新

核心函数 `bictcp_update`：

```c
static inline void bictcp_update(struct bictcp *ca, u32 cwnd, u32 acked)
{
    u32 delta, bic_target, offs;
    u64 t;

    ca->ack_cnt += acked;

    if (ca->last_cwnd == cwnd &&
        (s32)(tcp_jiffies32 - ca->last_time) <= HZ / 20)
        return;

    ca->last_cwnd = cwnd;
    ca->last_time = tcp_jiffies32;

    if (ca->epoch_start == 0) {
        ca->epoch_start = tcp_jiffies32;
        ca->ack_cnt = acked;
        ca->tcp_cwnd = cwnd;

        if (ca->last_max_cwnd <= cwnd) {
            ca->bic_K = 0;
            ca->bic_origin_point = cwnd;
        } else {
            ca->bic_origin_point = ca->last_max_cwnd;
            delta = ca->last_max_cwnd - cwnd;
            do_div(delta, BICTCP_B);
            ca->bic_K = cube_root(delta);
        }
    }

    t = (s32)(tcp_jiffies32 - ca->epoch_start);
    t += msecs_to_jiffies(ca->delay_min);

    if (t > ca->bic_K)
        offs = t - ca->bic_K;
    else
        offs = ca->bic_K - t;

    delta = cube(offs);
    if (t > ca->bic_K)
        bic_target = ca->bic_origin_point + delta;
    else
        bic_target = ca->bic_origin_point - delta;

    if (bic_target > cwnd)
        ca->cnt = cwnd / (bic_target - cwnd);
    else
        ca->cnt = 100 * cwnd;
}
```

这段代码计算当前时间 `t` 距离 `K` 的偏移，然后根据立方函数计算目标窗口 `bic_target`，最后决定 `cnt`（每收到多少个 ACK 增加一次 cwnd）。

### 丢包处理

```c
static void bictcp_cong_avoid(struct sock *sk, u32 ack, u32 acked)
{
    ...
    if (tcp_in_slow_start(tp)) {
        // 慢启动阶段：指数增长
        acked = tcp_slow_start(tp, acked);
        if (!acked)
            return;
    }
    bictcp_update(ca, tp->snd_cwnd, acked);
    tcp_cong_avoid_ai(sk, ca->cnt, acked);
}
```

丢包后，CUBIC 进入拥塞避免阶段，按立方函数增长窗口。

## 6.4 与 AI 场景的关系

### 大文件传输

CUBIC 在高 BDP 链路上恢复窗口较快，但如果频繁丢包，窗口震荡会导致吞吐不稳定。

### 推理服务

长连接下，CUBIC 的窗口增长和降窗会影响延迟。BBR 或 QUIC 可能更适合低延迟推理。

### RDMA 网络

RoCEv2 不跑 TCP，但同样面临拥塞控制问题。数据中心常用 DCTCP 或基于 ECN 的拥塞控制。

## 6.5 阅读网络源码的建议

1. **抓主线**：不要陷入每个宏和分支；
2. **用工具**：elixir.bootlin.com、GitHub 搜索；
3. **看版本**：不同内核版本差异大；
4. **配合文档**：Kernel Documentation 和 RFC；
5. **动手实验**：用 `sysctl net.ipv4.tcp_congestion_control` 切换算法，观察 iperf 结果。

## 6.6 本节小结

- CUBIC 用立方函数控制拥塞窗口增长；
- 丢包后窗口乘性减少，然后按立方函数重新增长；
- Linux 实现在 `net/ipv4/tcp_cubic.c`，核心函数 `bictcp_update`；
- CUBIC 影响大文件传输和 TCP 长连接推理服务；
- RDMA 网络有独立的拥塞控制机制（PFC/ECN/DCTCP）。

下一节进入工程实践：用 Python 写一个网络机制模拟器。
