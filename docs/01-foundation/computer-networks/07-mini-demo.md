# 7. 工程实践：用 Python 模拟网络核心机制

> 本章配套 Mini Demo 位于 `docs/01-foundation/computer-networks/mini-demo/`，CPU 即可运行。

## 7.1 为什么做模拟

真实 AI 集群的网络问题往往涉及 RDMA 网卡、交换机 PFC/ECN、内核协议栈、CNI 插件、NCCL 配置等多层因素，排错成本极高。一个纯 Python 的教学模拟器可以帮助我们建立直觉：

- 路由器如何根据最长前缀匹配转发包；
- TCP 如何通过滑动窗口、ACK、超时重传保证可靠性；
- 拥塞控制如何在高带宽网络中“快升慢降”；
- Ring / Tree all-reduce 如何把梯度汇聚到所有节点；
- DNS TTL 和负载均衡如何影响推理服务的入口流量。

> **注意**：模拟器是教学工具，不是真实协议栈。真实调优必须在真实网络上使用 `iperf`、`nccl-tests`、`tcpdump`、`ss`、`ethtool` 等工具验证。

## 7.2 代码结构

```text
mini-demo/
├── README.md
├── pyproject.toml
├── computer_networks_mini/
│   ├── __init__.py
│   ├── packet.py       # Packet 数据类
│   ├── router.py       # L3 路由器 + 最长前缀匹配
│   ├── transport.py    # 滑动窗口可靠传输
│   ├── congestion.py   # AIMD / CUBIC-like 拥塞控制
│   ├── topology.py     # 简单拓扑图（链路延迟/带宽）
│   ├── allreduce.py    # ring/tree all-reduce
│   ├── dns_lb.py       # DNS + L4 负载均衡
│   └── demo.py         # 入口脚本
└── tests/
    └── test_all.py
```

## 7.3 安装与运行

```bash
cd docs/01-foundation/computer-networks/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m computer_networks_mini.demo
```

## 7.4 关键代码片段

### 7.4.1 最长前缀匹配

```python
# computer_networks_mini/router.py
def longest_prefix_match(self, dst_ip: str) -> Optional[str]:
    dst = ip_to_int(dst_ip)
    for prefix, next_hop in self.forwarding_table:
        net, length = prefix_to_net(prefix)
        mask = (0xFFFFFFFF << (32 - length)) & 0xFFFFFFFF
        if (dst & mask) == net:
            return next_hop
    return None
```

### 7.4.2 滑动窗口与超时重传

```python
# computer_networks_mini/transport.py
def age_and_retransmit(self) -> List[Packet]:
    retrans: List[Packet] = []
    for seq, age in list(self._unacked.items()):
        age += 1
        self._unacked[seq] = age
        if age >= self.timeout:
            retrans.append(Packet(src_ip=self.name, dst_ip="peer",
                                  seq=seq, flags="DATA"))
            self._unacked[seq] = 0
    return retrans
```

### 7.4.3 简化的 CUBIC-like 窗口更新

```python
# computer_networks_mini/congestion.py
def on_ack(self, time_step: int) -> None:
    if self.cwnd < self.ssthresh:
        self.cwnd += 1.0  # 慢启动
    else:
        t = time_step - self.epoch_start
        target = self.max_cwnd + self.C * ((t - self.K) ** 3)
        if target > self.cwnd:
            self.cwnd += (target - self.cwnd) / self.cwnd
```

### 7.4.4 Ring all-reduce

```python
# computer_networks_mini/allreduce.py
for step in range(n - 1):
    snapshot = {node: list(v) for node, v in vectors.items()}
    for i, node in enumerate(nodes):
        prev_node = nodes[(i - 1) % n]
        recv_chunk = (i - 1 - step) % n
        vectors[node][recv_chunk] += snapshot[prev_node][recv_chunk]
```

## 7.5 运行输出示例

```text
Computer Networks Mini Demo — AI Infra Handbook

============================================================
1. IP 包交换与最长前缀匹配（LPM）
============================================================
  10.0.5.6             next-hop=10.1.0.1
  10.2.4.1             next-hop=10.2.0.1
  10.2.3.5             next-hop=10.2.3.1
  192.168.1.1          next-hop=None

============================================================
2. 滑动窗口可靠传输（ACK + 超时重传）
============================================================
  t= 0 in-flight=3 delivered=1
  t= 5 in-flight=4 delivered=1
  t=10 in-flight=4 delivered=5
  最终 delivered=10

============================================================
3. 拥塞控制：慢启动 + AIMD/CUBIC-like
============================================================
  最终 cwnd=11.42 ssthresh=9.84
  cwnd 序列: 2.0 3.0 4.0 5.0 6.0 7.0 8.0 8.1 8.2 8.4 ...

============================================================
4. Ring / Tree All-Reduce
============================================================
  输入: {'gpu-0': 1.0, 'gpu-1': 2.0, 'gpu-2': 3.0, 'gpu-3': 4.0}
  ring 结果: {'gpu-0': 2.5, 'gpu-1': 2.5, 'gpu-2': 2.5, 'gpu-3': 2.5}
  tree 结果: {'gpu-0': 2.5, 'gpu-1': 2.5, 'gpu-2': 2.5, 'gpu-3': 2.5}

============================================================
5. DNS TTL + L4 负载均衡
============================================================
  round-robin 分布: {'pod-0': 4, 'pod-1': 4, 'pod-2': 4}
  weighted 分布: {'pod-0': 7, 'pod-1': 3, 'pod-2': 2}
  consistent-hash 分布: {'pod-0': 2, 'pod-1': 5, 'pod-2': 5}
```

## 7.6 模拟器与真实网络的差异

| 维度 | 模拟器 | 真实网络 |
|---|---|---|
| 包格式 | Python 对象 | Ethernet / IP / TCP / UDP 帧 |
| 路由 | 简单 forwarding table | FIB/RIB、BGP/OSPF/IS-IS |
| 可靠传输 | 单连接滑动窗口 | 完整 TCP 状态机、SACK、RTT 采样 |
| 拥塞控制 | 简化 CUBIC-like | Linux `tcp_cubic.c` 完整实现 |
| 拓扑 | 加权图 | Spine-Leaf、fat-tree、3D-torus + 交换机缓冲区 |
| All-reduce | 算法模拟 | NCCL channel、bootstrap、topology detection |
| DNS/LB | 简化 TTL/策略 | CoreDNS、ipvs、Envoy、Anycast |

## 7.7 下一步

理解了这些机制之后，下一章把视角切换到生产环境：在真实 AI 集群里如何部署 RoCE/InfiniBand、如何调 CNI、如何做 NCCL 参数优化、如何排障。
