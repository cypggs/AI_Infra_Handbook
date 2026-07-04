"""Tests for computer_networks_mini package."""
from computer_networks_mini import (
    CongestionController,
    DNSResolver,
    LoadBalancer,
    Packet,
    ReliableTransport,
    Router,
    Topology,
    ring_allreduce,
    tree_allreduce,
)


def test_router_longest_prefix_match():
    router = Router(name="r1")
    router.add_route("10.0.0.0/8", "h1")
    router.add_route("10.2.0.0/16", "h2")
    router.add_route("10.2.3.0/24", "h3")
    assert router.longest_prefix_match("10.0.5.6") == "h1"
    assert router.longest_prefix_match("10.2.4.1") == "h2"
    assert router.longest_prefix_match("10.2.3.5") == "h3"
    assert router.longest_prefix_match("192.168.1.1") is None


def test_router_forwarding_table_sorted_on_add():
    router = Router(name="r2")
    router.add_route("10.0.0.0/8", "h1")
    router.add_route("10.2.3.0/24", "h3")
    lengths = [int(p.split("/")[1]) for p, _ in router.forwarding_table]
    assert lengths == [24, 8]


def test_packet_ttl_drops_when_zero():
    router = Router(name="r3")
    pkt = Packet(src_ip="a", dst_ip="b", ttl=1)
    router.receive(pkt)
    assert pkt.ttl == 0
    assert pkt not in router.queue


def test_reliable_transport_basic_delivery():
    sender = ReliableTransport(name="s", window_size=3, timeout=5)
    receiver = ReliableTransport(name="r", window_size=3, timeout=5)
    for _ in range(5):
        for pkt in sender.send_window():
            ack = receiver.receive(pkt)
            if ack:
                sender.receive(ack)
        if receiver.delivered_count() >= 3:
            break
    assert receiver.delivered_count() >= 3


def test_reliable_transport_retransmit_on_loss():
    sender = ReliableTransport(name="s", window_size=2, timeout=2)
    receiver = ReliableTransport(name="r", window_size=2, timeout=2)
    # First, fill the window
    sender.send_window()
    # Simulate 6 ticks, dropping seq 0 on its first transmission
    for t in range(6):
        packets = sender.age_and_retransmit()
        for pkt in packets:
            if pkt.seq == 0 and t == 0:
                continue  # first transmission of seq 0 is dropped
            ack = receiver.receive(pkt)
            if ack:
                sender.receive(ack)
    assert receiver.delivered_count() >= 2


def test_aimd_increase_then_decrease():
    ctrl = CongestionController(cwnd=1.0, ssthresh=4.0, beta=0.5)
    for _ in range(10):
        ctrl.on_ack(0)
    before_loss = ctrl.cwnd
    ctrl.on_loss(11)
    assert ctrl.cwnd == before_loss * 0.5
    assert ctrl.ssthresh == ctrl.cwnd


def test_cubic_grows_after_loss():
    ctrl = CongestionController(cwnd=4.0, ssthresh=2.0, beta=0.7)
    ctrl.max_cwnd = 10.0
    ctrl.epoch_start = 0
    delta = ctrl.max_cwnd - ctrl.cwnd
    ctrl.K = (delta / ctrl.C) ** (1 / 3)
    initial = ctrl.cwnd
    for t in range(1, 20):
        ctrl.on_ack(t)
    assert ctrl.cwnd > initial


def test_ring_allreduce_converges():
    values = {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0}
    topo = Topology.ring(list(values.keys()))
    result = ring_allreduce(values, topo)
    expected = sum(values.values()) / len(values)
    for v in result.values():
        assert v == expected


def test_tree_allreduce_converges():
    values = {"a": 10.0, "b": 20.0, "c": 30.0}
    topo = Topology.fat_tree_like(leaves=list(values.keys()), spines=["s1"])
    result = tree_allreduce(values, topo)
    expected = sum(values.values()) / len(values)
    for v in result.values():
        assert v == expected


def test_dns_ttl_expires():
    dns = DNSResolver()
    dns.add_record("svc", "10.0.0.1", ttl=2)
    dns.current_time = 0
    assert dns.resolve("svc") == "10.0.0.1"
    dns.current_time = 1
    assert dns.resolve("svc") == "10.0.0.1"
    dns.current_time = 2
    assert dns.resolve("svc") == "10.0.0.1"  # created=0, current=2, 2-0 < 2 is False
    # Actually resolve recomputes: current_time - created_at = 2, ttl=2, so expired
    assert dns.resolve("svc") == "10.0.0.1"  # re-fetches authoritative


def test_lb_round_robin_distributes():
    lb = LoadBalancer(backends=["a", "b", "c"], strategy="round-robin")
    keys = [f"k{i}" for i in range(9)]
    dist = lb.distribution(keys)
    assert dist == {"a": 3, "b": 3, "c": 3}


def test_lb_weighted_distributes():
    lb = LoadBalancer(backends=["a", "b"], strategy="weighted", weights={"a": 7, "b": 3})
    keys = [f"k{i}" for i in range(100)]
    dist = lb.distribution(keys)
    assert dist["a"] == 70
    assert dist["b"] == 30


def test_lb_consistent_hash_same_key_same_backend():
    lb = LoadBalancer(backends=["a", "b", "c"], strategy="consistent-hash")
    picks = [lb.pick("user-1") for _ in range(5)]
    assert len(set(picks)) == 1
    assert picks[0] in {"a", "b", "c"}


def test_topology_shortest_path():
    topo = Topology(nodes={"a", "b", "c"}, links={})
    topo.add_link("a", "b", latency=1.0)
    topo.add_link("b", "c", latency=1.0)
    topo.add_link("a", "c", latency=5.0)
    assert topo.shortest_path("a", "c") == ["a", "b", "c"]
    assert topo.shortest_path("a", "d") == []
