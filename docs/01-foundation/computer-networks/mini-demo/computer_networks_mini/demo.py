"""Entry-point demo for computer networks mini simulator."""
from __future__ import annotations

import random

from computer_networks_mini import (
    CongestionController,
    DNSResolver,
    LoadBalancer,
    ReliableTransport,
    Router,
    Topology,
    ring_allreduce,
    tree_allreduce,
)


def demo_routing():
    print("=" * 60)
    print("1. IP 包交换与最长前缀匹配（LPM）")
    print("=" * 60)
    router = Router(name="spine-0")
    router.add_route("10.0.0.0/8", "10.1.0.1")
    router.add_route("10.2.0.0/16", "10.2.0.1")
    router.add_route("10.2.3.0/24", "10.2.3.1")
    destinations = ["10.0.5.6", "10.2.4.1", "10.2.3.5", "192.168.1.1"]
    for dst in destinations:
        next_hop = router.longest_prefix_match(dst)
        print(f"  {dst:20} next-hop={next_hop}")
    print()


def demo_reliable_transport():
    print("=" * 60)
    print("2. 滑动窗口可靠传输（ACK + 超时重传）")
    print("=" * 60)
    sender = ReliableTransport(name="sender", window_size=4, timeout=3)
    receiver = ReliableTransport(name="receiver", window_size=4, timeout=3)
    # 10 packets, simulate 30% random drop
    delivered = []
    for t in range(25):
        packets = sender.send_window() + sender.age_and_retransmit()
        acks = []
        for pkt in packets:
            if random.random() < 0.3:
                continue  # dropped
            ack = receiver.receive(pkt)
            if ack:
                acks.append(ack)
        for ack in acks:
            if random.random() < 0.3:
                continue
            sender.receive(ack)
        if t % 5 == 0:
            print(f"  t={t:2} in-flight={sender.in_flight()} delivered={receiver.delivered_count()}")
        if receiver.delivered_count() >= 10:
            break
    print(f"  最终 delivered={receiver.delivered_count()}")
    print()


def demo_congestion():
    print("=" * 60)
    print("3. 拥塞控制：慢启动 + AIMD/CUBIC-like")
    print("=" * 60)
    ctrl = CongestionController(cwnd=1.0, ssthresh=8.0, beta=0.7)
    for t in range(60):
        if t in {15, 35, 55}:
            ctrl.on_loss(t)
        else:
            ctrl.on_ack(t)
    print(f"  最终 cwnd={ctrl.cwnd:.2f} ssthresh={ctrl.ssthresh:.2f}")
    print("  cwnd 序列:", " ".join(f"{w:.1f}" for w in ctrl.history[:20]), "...")
    print()


def demo_allreduce():
    print("=" * 60)
    print("4. Ring / Tree All-Reduce")
    print("=" * 60)
    nodes = ["gpu-0", "gpu-1", "gpu-2", "gpu-3"]
    values = {"gpu-0": 1.0, "gpu-1": 2.0, "gpu-2": 3.0, "gpu-3": 4.0}
    topo_ring = Topology.ring(nodes)
    result_ring = ring_allreduce(values, topo_ring)
    topo_tree = Topology.fat_tree_like(leaves=nodes, spines=["spine-0", "spine-1"])
    result_tree = tree_allreduce(values, topo_tree)
    print(f"  输入: {values}")
    print(f"  ring 结果: {result_ring}")
    print(f"  tree 结果: {result_tree}")
    print()


def demo_dns_lb():
    print("=" * 60)
    print("5. DNS TTL + L4 负载均衡")
    print("=" * 60)
    dns = DNSResolver()
    dns.add_record("llm-gateway.example.com", "10.0.0.10", ttl=3)
    for t in range(5):
        dns.current_time = t
        print(f"  t={t} resolve={dns.resolve('llm-gateway.example.com')}")

    keys = [f"req-{i}" for i in range(12)]
    rr = LoadBalancer(backends=["pod-0", "pod-1", "pod-2"], strategy="round-robin")
    wh = LoadBalancer(
        backends=["pod-0", "pod-1", "pod-2"],
        strategy="weighted",
        weights={"pod-0": 5, "pod-1": 3, "pod-2": 2},
    )
    ch = LoadBalancer(backends=["pod-0", "pod-1", "pod-2"], strategy="consistent-hash")
    print(f"  round-robin 分布: {rr.distribution(keys)}")
    print(f"  weighted 分布: {wh.distribution(keys)}")
    print(f"  consistent-hash 分布: {ch.distribution(keys)}")
    print()


def main():
    random.seed(42)
    print()
    print("Computer Networks Mini Demo — AI Infra Handbook")
    print()
    demo_routing()
    demo_reliable_transport()
    demo_congestion()
    demo_allreduce()
    demo_dns_lb()


if __name__ == "__main__":
    main()
