# 计算机网络 Mini Demo

本目录包含一个 CPU 可运行的计算机网络机制模拟器，用于帮助理解 AI Infra 中最常遇到的网络概念。

> **注意**：这是一个教学模拟器，不是真实网络设备或协议栈。它用于建立直觉，真实调优需要在真实网络环境中使用 `iperf`、`nccl-tests`、`tcpdump` 等工具。

## 模拟内容

| 模块 | 文件 | 模拟的机制 |
|---|---|---|
| 包与路由 | `computer_networks_mini/packet.py` / `router.py` | IP 包、forwarding table、最长前缀匹配 |
| 可靠传输 | `computer_networks_mini/transport.py` | 滑动窗口、ACK、超时重传 |
| 拥塞控制 | `computer_networks_mini/congestion.py` | AIMD / CUBIC-like 拥塞窗口 |
| 拓扑与 all-reduce | `computer_networks_mini/topology.py` / `allreduce.py` | 简单网络拓扑、ring/tree all-reduce |
| DNS 与负载均衡 | `computer_networks_mini/dns_lb.py` | DNS TTL/A 记录、轮询/加权/一致性哈希 LB |
| 入口脚本 | `computer_networks_mini/demo.py` | 展示所有模块的运行效果 |

## 安装与运行

```bash
cd docs/01-foundation/computer-networks/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m computer_networks_mini.demo
```

## 与真实网络的差异

| 模拟器 | 真实网络 |
|---|---|
| Python 对象模拟包 | 真实 Ethernet/IP/TCP/UDP 帧 |
| 简单 forwarding table | 真实 FIB/RIB、BGP/OSPF 路由协议 |
| 单连接滑动窗口 | 真实 TCP 状态机、SACK、RTT 估计 |
| 简化 CUBIC-like 公式 | Linux `tcp_cubic.c` 完整实现 |
| 拓扑是加权图 | 真实 Spine-Leaf/fat-tree/3D-torus + 交换机缓冲区 |
| 简化的 ring/tree all-reduce | NCCL 真实 channel、topology detection、bootstrap |
| 简化 DNS/LB | 真实 CoreDNS、ipvs、Envoy、Anycast |

## 推荐阅读顺序

1. 先阅读本章文档，理解路由、可靠传输、拥塞控制、all-reduce、DNS/LB 的概念；
2. 运行 `demo.py`，观察模拟输出；
3. 打开源码，看每个机制是怎么被简化模拟的；
4. 回到生产环境，用真实工具验证。
