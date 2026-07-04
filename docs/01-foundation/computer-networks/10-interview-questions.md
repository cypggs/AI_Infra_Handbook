# 10. 面试题

面试中计算机网络相关的问题，通常从基础协议开始，逐渐深入到 AI Infra 场景。本章按初、中、高级整理。

## 10.1 初级

### 1. TCP 和 UDP 有什么区别？AI 场景里分别什么时候用？

**参考答案**：TCP 可靠、面向连接、有拥塞控制，适合对象存储下载、控制面通信、HTTP/gRPC 推理服务；UDP 无连接、低开销，适合 RDMA RoCEv2 的底层、视频流、Telemetry。

### 2. 简述 TCP 三次握手和四次挥手。

**参考答案**：三次握手：SYN → SYN-ACK → ACK，同步序列号；四次挥手：FIN → ACK → FIN → ACK，关闭双向连接。

### 3. 什么是 DNS？A 记录和 CNAME 有什么区别？

**参考答案**：DNS 把域名解析为 IP。A 记录直接映射到 IPv4；CNAME 是别名，指向另一个域名。AI 服务入口常用 A 记录配合负载均衡，或用 CNAME 做 CDN/云厂商切换。

### 4. 什么是 NAT？容器网络为什么需要 NAT？

**参考答案**：NAT 把私有地址映射到公网地址。容器 Pod IP 通常是集群私网，访问外部需要通过节点做 SNAT。

### 5. 什么是 ARP？

**参考答案**：ARP 根据 IP 地址解析 MAC 地址，是 L2/L3 边界的关键协议。

## 10.2 中级

### 6. 解释 TCP 拥塞控制中的慢启动、拥塞避免、快速重传、快速恢复。

**参考答案**：慢启动指数增窗口到 ssthresh；拥塞避免线性增；快速重传在收到 3 个 dup ACK 时重传；快速恢复把 ssthresh 减半后继续线性增，而不是回到慢启动。

### 7. CUBIC 和 BBR 的主要区别是什么？

**参考答案**：CUBIC 以丢包为信号，窗口按立方函数增长；BBR 以带宽和 RTT 测量为信号，模型化发送速率，丢包不敏感，适合高带宽高延迟或存在随机丢包的网络。

### 8. 什么是网络中的 incast？AI 训练里什么时候会发生？

**参考答案**：多对一流量同时到达交换机，缓冲区溢出丢包。AI 训练里的 all-to-all、all-gather、参数服务器同步都可能触发 incast。

### 9. Kubernetes 中 kube-proxy 的三种模式有什么区别？

**参考答案**：iptables 通过规则链转发，简单但大流量遍历慢；ipvs 用内核虚拟服务器，性能好；eBPF（Cilium）绕过 iptables/conntrack，延迟最低。

### 10. 什么是 CNI？Calico 和 Cilium 的主要差异？

**参考答案**：CNI 是 K8s 容器网络接口标准。Calico 主打 BGP/IP-in-IP 和网络策略；Cilium 基于 eBPF，支持 L7 策略、可观测性、kube-proxy replacement。

### 11. 解释 RoCEv2 为什么需要 PFC 和 ECN。

**参考答案**：RoCEv2 基于 UDP/IP，本身不保证可靠。PFC 在 L2 pause 上游防丢包，ECN 让端侧感知拥塞并降速，共同构成无损以太网。

### 12. 负载均衡有哪些策略？各适合什么场景？

**参考答案**：轮询简单均匀；加权按容量分配；一致性哈希保证同一 key 落到同一后端，适合缓存亲和；最小连接适合长连接服务。

## 10.3 高级

### 13. 设计一个万卡 AI 训练集群的网络，你会怎么选型？

**参考答案要点**：
- 超大规模优先考虑 InfiniBand 或分 fabric 的 RoCE；
- 拓扑选 fat-tree 或 3D-torus + OCS；
- 训练、存储、管理三平面物理隔离；
- 收敛比 ≥ 1:1；
- 全网 ECN/PFC 一致性；
- 预留 NCCL SHARP 或交换机 in-network aggregation；
- 可观测覆盖从 NIC 到交换机到 NCCL。

### 14. 你如何定位 NCCL all-reduce 带宽不达标的问题？

**参考答案要点**：
1. 用 `nccl-tests` 复现，确认是 NCCL 层还是下层问题；
2. 单链路 `ib_write_bw` 验证 RDMA 带宽；
3. 检查 NUMA、GDR、PCIe 拓扑；
4. 检查交换机利用率、PFC pause、ECN 标记；
5. 调整 `NCCL_ALGO`、`NCCL_BUFFSIZE`、`NCCL_NET_GDR_LEVEL`；
6. 查看 `NCCL_DEBUG=INFO` 日志。

### 15. LLM 推理服务出现偶发 P99 延迟尖刺，如何从网络角度排查？

**参考答案要点**：
1. 分解延迟：DNS、TCP/TLS 握手、TTFB、服务处理；
2. 检查 DNS TTL、CoreDNS 负载、NodeLocal DNSCache；
3. 检查 LB 后端健康度、连接分布、长连接倾斜；
4. 抓包看是否有重传、乱序、ECN；
5. 检查 CNI 数据面是否有 eBPF 程序异常；
6. 关联宿主机 `sar -n TCP/UDP`、`ss -tin`。

### 16. 比较 Spine-Leaf 和 fat-tree，在 AI 集群里各有什么优劣？

**参考答案**：Spine-Leaf 扁平、任意两 Leaf 间路径固定、易扩展；fat-tree 是多级 Clos 的特例，提供全带宽 bisection，但层级更多、成本和布线复杂。AI 训练追求高 bisection bandwidth，常用 fat-tree 或其变体。

### 17. 如何在 Kubernetes 上给训练 Pod 同时接入管理网和 RDMA 数据网？

**参考答案**：使用 Multus 创建多个 NetworkAttachmentDefinition，eth0 走默认 CNI，eth1 走 SR-IOV / host-device / macvlan 绑定到物理 RDMA 网卡；Pod 内通过环境变量或 device plugin 指定 NCCL 使用的网卡。

### 18. 谈谈 RDMA 中的 QP、CQ、MR 分别是什么。

**参考答案**：QP（Queue Pair）是通信双方的发送/接收队列对；CQ（Completion Queue）用于接收完成通知；MR（Memory Region）是已注册到 RNIC 的内存，持有虚拟地址、物理地址和访问密钥。

## 10.4 场景设计题

### 19. 设计一个跨地域的 LLM 推理服务入口

**参考答案要点**：
- DNS 用 Geo/_LATENCY 路由，如 Route53、Cloudflare GeoDNS；
- 边缘部署 Anycast/LB，就近接入；
- 核心集群前再用 L7 Gateway 做限流、认证、batch 编排；
- 服务间用 mTLS；
- 监控按 region、model、backend 多维下钻。

### 20. 如何在多租户 GPU 集群里避免网络互相干扰？

**参考答案要点**：
- 物理 fabric 隔离训练/推理/存储；
- 训练租户内再用 VLAN/VXLAN 或 Cilium 网络策略隔离；
- 限制每个租户的 egress/ingress 带宽；
- 独立 QoS 和 ECN 优先级；
- 监控每个租户的 NCCL 流量和 retrans。
