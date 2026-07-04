# 9. 最佳实践

把前面几章的知识沉淀成可以落进 SOP 和架构评审的检查清单。

## 9.1 AI 集群网络架构设计检查清单

### 9.1.1 计算网络（GPU 数据面）

| 检查项 | 建议 |
|---|---|
| 拓扑选择 | 中小型集群 Spine-Leaf；超大规模考虑 fat-tree / 3D-torus + OCS。 |
| 网络类型 | 预算充足选 InfiniBand；追求性价比选 RoCEv2；推理入口用标准 TCP/IP。 |
| 收敛比 | 非阻塞或接近非阻塞；训练场景收敛比 ≥ 1:1。 |
| MTU | 全链路 Jumbo frame（9000/9216）。 |
| 路由对称 | 避免 ECMP 非对称导致 PFC/ECN 异常。 |
| 多租户隔离 | 物理 fabric 隔离优于 VLAN；训练/推理/存储分平面。 |

### 9.1.2 Kubernetes 网络

| 检查项 | 建议 |
|---|---|
| CNI | 训练 Pod 用 Multus 加数据网；普通服务用 Cilium/Calico。 |
| kube-proxy | 大规模用 ipvs 或 Cilium eBPF replacement。 |
| DNS | NodeLocal DNSCache + CoreDNS HPA + 合理 TTL。 |
| Service | headless Service 用于训练 Pod；ClusterIP 用于推理网关。 |
| Ingress/Gateway | Gateway API 优于 Ingress；L4 用 MetalLB/BGP。 |

### 9.1.3 RDMA / NCCL

| 检查项 | 建议 |
|---|---|
| NUMA | GPU、NIC、CPU 同 NUMA；用 `nvidia-smi topo -m` 验证。 |
| GDR | 启用 GPU Direct RDMA；设置 `NCCL_NET_GDR_LEVEL=SYS`。 |
| PFC/ECN | 交换机、网卡、操作系统三方配置一致。 |
| NCCL 参数 | 先跑 `nccl-tests` 基线，再逐步调整 `NCCL_ALGO`、`NCCL_BUFFSIZE`。 |
| 诊断日志 | 训练异常时开启 `NCCL_DEBUG=INFO`。 |

## 9.2 性能基准

### 9.2.1 单链路带宽

```bash
# RDMA
ib_write_bw -d mlx5_0 --report_gbits -F

# TCP
iperf3 -c <host> -t 30 -P 8
```

### 9.2.2 集合通信带宽

```bash
# all_reduce 测试
mpirun -np 16 ./build/all_reduce_perf -b 8M -e 1G -f 2 -g 1
```

验收标准：

- 单机多卡：≥ 95% 理论 NVLink/NIC 带宽。
- 多机同 Leaf：≥ 90% 线速。
- 跨 Spine：≥ 80% 线速。

### 9.2.3 推理入口延迟

```bash
# 端到端延迟分解
curl -o /dev/null -s -w '\nDNS: %{time_namelookup}s\nConnect: %{time_connect}s\nTTFB: %{time_starttransfer}s\nTotal: %{time_total}s\n' \
  https://your-llm-api.example.com/v1/chat/completions
```

## 9.3 可观测性指标体系

| 层级 | 指标 | 工具 |
|---|---|---|
| 物理层 | 端口 up/down、光功率、温度 | 交换机 SNMP、Redfish |
| 链路层 | 带宽利用率、PFC pause 次数 | `ethtool -S`、交换机 CLI |
| 网络层 | 丢包、延迟、RTT、ECN 标记 | `ss -tin`、`tcpdump` |
| 传输层 | TCP retrans、cwnd、RTO | `sar -n TCP`、`bcc` |
| RDMA 层 | bandwidth、retry、out-of-order | `ibstat`、`perftest` |
| 应用层 | NCCL timeout、all-reduce 时间 | `nccl-tests`、训练框架 metric |
| 服务层 | QPS、P99 延迟、错误率 | Prometheus + Grafana |

## 9.4 安全最佳实践

| 场景 | 实践 |
|---|---|
| Pod 间通信 | 默认 deny 的 NetworkPolicy，按需放通。 |
| 服务网格 | 敏感推理服务启用 mTLS。 |
| 入口 | WAF + 限流 + DDoS 防护。 |
| 管理面 | API server、etcd 单独管理网，不暴露在数据面。 |
| 审计 | 记录网络策略变更、DNS 查询、LB 后端变更。 |

## 9.5 成本与扩展的 trade-off

| 选择 | 收益 | 代价 |
|---|---|---|
| InfiniBand | 最高性能、最低抖动 | 昂贵、供应商锁定 |
| RoCEv2 | 复用以太网、成本可控 | 需精细调优 PFC/ECN |
| 单平面网络 | 简单、省钱 | 训练/推理/存储互相干扰 |
| 多平面网络 | 隔离性好、可独立扩容 | 硬件和运维成本翻倍 |
|  Overlay（VXLAN） | 灵活、跨机房 | 额外头部开销、影响 RDMA |
| Underlay 路由 | 性能最好 | 配置复杂、IP 管理麻烦 |

## 9.6 一句话总结

**先把网络当成一个可度量、可隔离、可回滚的系统来设计，再谈带宽。**
