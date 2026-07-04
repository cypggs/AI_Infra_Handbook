"""Deterministic tests for the distributed systems mini-demo."""
from __future__ import annotations

from distributed_systems_mini import demo
from distributed_systems_mini.logical_clock import LamportClock
from distributed_systems_mini.network import FakeClock, InProcessNetwork
from distributed_systems_mini.quorum_store import QuorumKVStore
from distributed_systems_mini.raft import LogEntry, RaftNode
from distributed_systems_mini.two_phase_commit import Cohort, Coordinator
from distributed_systems_mini.vector_clock import VectorClock


# --------------------------------------------------------------------------- #
# Lamport clock
# --------------------------------------------------------------------------- #
def test_lamport_monotonic_and_causal_order():
    a = LamportClock()
    b = LamportClock()

    a_send_ts = a.send()
    b.receive(a_send_ts)
    b_reply_ts = b.send()
    a.receive(b_reply_ts)

    assert a_send_ts <= b.time
    assert b_reply_ts <= a.time
    assert a.time > a_send_ts
    assert b.time > 0


# --------------------------------------------------------------------------- #
# Vector clock
# --------------------------------------------------------------------------- #
def test_vector_clock_concurrent_conflict():
    a = VectorClock("a")
    b = VectorClock("b")
    a.increment()
    a.increment()
    b.increment()
    b.increment()
    b.increment()

    assert a.compare(b) == "concurrent"
    merged = a.merge(b)
    assert merged.vector == {"a": 2, "b": 3}


def test_vector_clock_merge_commutative_and_idempotent():
    a = VectorClock("a")
    b = VectorClock("b")
    a.increment()
    a.increment()
    b.increment()
    b.increment()
    b.increment()

    m1 = a.merge(b)
    m2 = b.merge(a)
    assert m1.vector == m2.vector

    m3 = a.merge(a)
    assert m3.vector == a.vector


# --------------------------------------------------------------------------- #
# Raft helpers
# --------------------------------------------------------------------------- #
def _make_raft_cluster(node_ids):
    clock = FakeClock()
    net = InProcessNetwork(clock)
    nodes = {
        nid: RaftNode(nid, [i for i in node_ids if i != nid], clock, net)
        for nid in node_ids
    }
    for n in nodes.values():
        net.register(n.id, n.step)
    return clock, net, nodes


def _run_until_leader(clock, net, nodes, max_ticks=2000):
    for _ in range(max_ticks):
        clock.advance(1)
        for n in nodes.values():
            n.tick()
        net.deliver_pending()
        leaders = [n for n in nodes.values() if n.state == "leader"]
        if len(leaders) == 1:
            return leaders[0]
    return None


def test_raft_leader_election_in_three_node_cluster():
    node_ids = ["A", "B", "C"]
    clock, net, nodes = _make_raft_cluster(node_ids)
    leader = _run_until_leader(clock, net, nodes)

    assert leader is not None
    assert leader.term > 0
    assert sum(1 for n in nodes.values() if n.state == "leader") == 1


def test_raft_log_replication_and_commit():
    node_ids = ["A", "B", "C"]
    clock, net, nodes = _make_raft_cluster(node_ids)
    leader = _run_until_leader(clock, net, nodes)

    assert leader.propose("cmd1")
    for _ in range(500):
        clock.advance(1)
        for n in nodes.values():
            n.tick()
        net.deliver_pending()
        if leader.commit_index >= 1:
            break

    assert leader.commit_index == 1
    for n in nodes.values():
        assert len(n.log) >= 1
        assert n.log[0] == LogEntry(leader.term, "cmd1")


def test_raft_leader_failure_triggers_reelection():
    node_ids = ["A", "B", "C"]
    clock, net, nodes = _make_raft_cluster(node_ids)
    leader = _run_until_leader(clock, net, nodes)

    net.isolate({leader.id})
    survivors = {nid: n for nid, n in nodes.items() if nid != leader.id}
    new_leader = None
    for _ in range(2000):
        clock.advance(1)
        for n in survivors.values():
            n.tick()
        net.deliver_pending()
        leaders = [n for n in survivors.values() if n.state == "leader"]
        if len(leaders) == 1:
            new_leader = leaders[0]
            break

    assert new_leader is not None
    assert new_leader.id != leader.id


def test_raft_committed_entry_survives_minority_failure():
    node_ids = ["A", "B", "C", "D", "E"]
    clock, net, nodes = _make_raft_cluster(node_ids)
    leader = _run_until_leader(clock, net, nodes)

    leader.propose("cmd1")
    for _ in range(500):
        clock.advance(1)
        for n in nodes.values():
            n.tick()
        net.deliver_pending()
        if leader.commit_index >= 1:
            break

    assert leader.commit_index == 1

    # Isolate the leader plus one follower: a minority of the 5-node cluster.
    failed = {leader.id, [p for p in node_ids if p != leader.id][0]}
    net.isolate(failed)
    survivors = {nid: n for nid, n in nodes.items() if nid not in failed}
    new_leader = None
    for _ in range(2500):
        clock.advance(1)
        for n in survivors.values():
            n.tick()
        net.deliver_pending()
        leaders = [n for n in survivors.values() if n.state == "leader"]
        if len(leaders) == 1:
            new_leader = leaders[0]
            break

    assert new_leader is not None
    assert any(e.command == "cmd1" for e in new_leader.log)


# --------------------------------------------------------------------------- #
# Two-phase commit
# --------------------------------------------------------------------------- #
def _make_2pc(vote_map, timeout=10):
    clock = FakeClock()
    net = InProcessNetwork(clock)
    cohorts = {cid: Cohort(cid, vote_yes=v) for cid, v in vote_map.items()}
    coord = Coordinator("coord", list(vote_map.keys()), clock, net, timeout=timeout)
    net.register("coord", coord.step)
    for cohort in cohorts.values():

        def handler(msg, c=cohort, network=net):
            resp = c.step(msg)
            if resp is not None:
                network.send(resp.src, resp.dst, resp)

        net.register(cohort.id, handler)
    return clock, net, coord, cohorts


def _run_2pc_to_decision(clock, net, coord):
    net.deliver_pending()
    while coord.state == "preparing":
        clock.advance(1)
        coord.tick()
        net.deliver_pending()


def test_two_phase_commit_happy_path():
    clock, net, coord, cohorts = _make_2pc({"c1": True, "c2": True})
    coord.start_transaction("v1")
    _run_2pc_to_decision(clock, net, coord)

    assert coord.state == "committed"
    assert all(c.decision == "committed" for c in cohorts.values())


def test_two_phase_commit_aborts_on_no_vote():
    clock, net, coord, cohorts = _make_2pc({"c1": True, "c2": False})
    coord.start_transaction("v1")
    _run_2pc_to_decision(clock, net, coord)

    assert coord.state == "aborted"
    assert any(c.decision == "aborted" for c in cohorts.values())


def test_two_phase_commit_blocks_on_cohort_timeout():
    clock, net, coord, cohorts = _make_2pc({"c1": True, "c2": True}, timeout=5)
    # Unregister c2 so its vote never arrives.
    net.unregister("c2")
    coord.start_transaction("v1")
    _run_2pc_to_decision(clock, net, coord)

    assert coord.state == "aborted"


# --------------------------------------------------------------------------- #
# Quorum KV store
# --------------------------------------------------------------------------- #
def _make_store(N=5, W=3, R=2):
    clock = FakeClock()
    net = InProcessNetwork(clock)
    return QuorumKVStore(N, W, R, clock, net)


def test_quorum_write_then_read_consistent():
    store = _make_store()
    store.set_reachable({"client", "node0", "node1", "node2", "node3", "node4"})

    assert store.put("k", "v1")
    val, ver, stale = store.get("k")
    assert val == "v1"
    assert ver == 1
    assert not stale


def test_quorum_split_brain_write_rejected():
    store = _make_store()
    store.set_reachable({"client", "node0", "node1"})
    assert not store.put("k", "vA")

    store.set_reachable({"client", "node2", "node3"})
    assert not store.put("k", "vB")


def test_quorum_stale_read_detected():
    store = _make_store()
    store.set_reachable({"client", "node0", "node1", "node2", "node3", "node4"})
    assert store.put("k", "v1")

    store.set_reachable({"client", "node0", "node1", "node2"})
    assert store.put("k", "v2")

    store.set_reachable({"client", "node3", "node4"})
    val, ver, stale = store.get("k")
    assert stale
    assert ver == 1
    assert val == "v1"


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
def test_demo_runs_without_exception():
    demo.run_all()
