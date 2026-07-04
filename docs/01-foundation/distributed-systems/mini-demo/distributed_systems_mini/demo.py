"""Entry-point script demonstrating distributed systems mechanisms."""
from __future__ import annotations

from distributed_systems_mini.logical_clock import LamportClock
from distributed_systems_mini.network import FakeClock, InProcessNetwork
from distributed_systems_mini.quorum_store import QuorumKVStore
from distributed_systems_mini.raft import RaftNode
from distributed_systems_mini.two_phase_commit import Cohort, Coordinator, TwoPCMessage
from distributed_systems_mini.vector_clock import VectorClock


def _run_raft_election(node_ids=("a", "b", "c")):
    clock = FakeClock()
    net = InProcessNetwork(clock)
    nodes = [
        RaftNode(nid, [p for p in node_ids if p != nid], clock, net)
        for nid in node_ids
    ]
    for _ in range(500):
        for n in nodes:
            n.tick()
        net.deliver_pending()
        clock.advance(1)
    leader = next(n for n in nodes if n.is_leader)
    return leader, nodes


def scenario_lamport():
    print("\n=== Lamport Logical Clock ===")
    a = LamportClock()
    b = LamportClock()
    c = LamportClock()
    t1 = a.send()
    b.receive(t1)
    t2 = b.send()
    c.receive(t2)
    a.tick()
    print(f"a={a.time}, b={b.time}, c={c.time}")


def scenario_vector():
    print("\n=== Vector Clock Conflict & Merge ===")
    a = VectorClock("a").increment()
    b = VectorClock("b").increment()
    a.increment()
    b.increment()
    b.increment()
    print(f"a vector: {a.vector}, b vector: {b.vector}, relation: {a.compare(b)}")
    merged = a.merge(b)
    print(f"merged: {merged.vector}")


def scenario_raft():
    print("\n=== Raft Leader Election & Log Replication ===")
    leader, nodes = _run_raft_election()
    print(f"leader is {leader.node_id}, term={leader.term}")
    leader.propose("set x=42")
    clock = leader.clock
    net = leader.network
    for _ in range(200):
        for n in nodes:
            n.tick()
        net.deliver_pending()
        clock.advance(1)
    print(f"committed entries: {leader.applied_entries()}")


def scenario_raft_failure():
    print("\n=== Raft Leader Failure & Re-election ===")
    leader, nodes = _run_raft_election()
    leader.propose("set x=42")
    for _ in range(200):
        for n in nodes:
            n.tick()
        leader.network.deliver_pending()
        leader.clock.advance(1)

    old_leader = leader
    old_leader.network.isolate({old_leader.node_id})
    remaining = [n for n in nodes if n is not old_leader]
    clock = old_leader.clock
    net = old_leader.network
    for _ in range(500):
        for n in remaining:
            n.tick()
        net.deliver_pending()
        clock.advance(1)
    new_leader = next((n for n in remaining if n.is_leader), None)
    print(f"new leader: {new_leader.node_id if new_leader else None}")
    print(f"surviving committed entries: {remaining[0].applied_entries()}")


def scenario_2pc():
    print("\n=== Two-Phase Commit ===")
    clock = FakeClock()
    net = InProcessNetwork(clock)
    cohort_ids = ["c1", "c2", "c3"]
    coord = Coordinator("coord", cohort_ids, clock, net)
    cohorts = {cid: Cohort(cid, vote_yes=True) for cid in cohort_ids}

    def _cohort_handler(msg, c, network):
        resp = c.step(msg)
        if resp is not None:
            network.send(resp.src, resp.dst, resp)

    net.register("coord", coord.step)
    for c in cohorts.values():
        net.register(c.id, lambda msg, c=c: _cohort_handler(msg, c, net))

    coord.start_transaction("hello")
    for _ in range(30):
        coord.tick()
        net.deliver_pending()
        clock.advance(1)
    print(f"happy path coordinator state: {coord.state}")

    # Abort path: one cohort votes no.
    clock2 = FakeClock()
    net2 = InProcessNetwork(clock2)
    coord2 = Coordinator("coord", cohort_ids, clock2, net2)
    cohorts2 = {"c1": Cohort("c1", vote_yes=True), "c2": Cohort("c2", vote_yes=False), "c3": Cohort("c3", vote_yes=True)}
    net2.register("coord", coord2.step)
    for c in cohorts2.values():
        net2.register(c.id, lambda msg, c=c: _cohort_handler(msg, c, net2))
    coord2.start_transaction("world")
    for _ in range(30):
        coord2.tick()
        net2.deliver_pending()
        clock2.advance(1)
    print(f"abort path coordinator state: {coord2.state}")


def scenario_quorum():
    print("\n=== Quorum Read/Write ===")
    clock = FakeClock()
    net = InProcessNetwork(clock)
    client = QuorumKVStore(3, 2, 2, clock, net, node_prefix="replica")
    ok = client.put("x", 42)
    print(f"write ok={ok}")
    value, version, stale = client.get("x")
    print(f"read value={value}, version={version}, stale={stale}")

    # Split brain: client can only reach one replica.
    client.set_reachable({"replica0"})
    ok2 = client.put("y", 100)
    print(f"split-brain write (minority reachable) ok={ok2}")


def run_all():
    scenario_lamport()
    scenario_vector()
    scenario_raft()
    scenario_raft_failure()
    scenario_2pc()
    scenario_quorum()
    print("\nAll demo scenarios completed.")


def main():
    run_all()


if __name__ == "__main__":
    main()
