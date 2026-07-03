# Ray Mini Demo

A deterministic, pure-CPU simulator of Ray Core mechanisms for the AI Infrastructure Handbook.

## What it simulates

| Mechanism | File | Production Ray counterpart |
|---|---|---|
| Ownership + ObjectRef resolution | `runtime.py` | CoreWorker ownership model |
| Hybrid scheduling | `scheduler.py` | Default `HybridScheduler` (`RAY_scheduler_spread_threshold`) |
| Per-node object store + spilling | `object_store.py` | Plasma / object spilling |
| Lineage reconstruction | `runtime.py` | Task retry + lineage reconstruction |
| Demand-based autoscaling | `autoscaler.py` | Ray Autoscaler / KubeRay |

## Run

```bash
pip install -e ".[dev]"
pytest tests/ -v
python -m ray_mini.demo
```

## Production differences

| Aspect | Mini Demo | Real Ray |
|---|---|---|
| Execution | Synchronous, single-threaded ticks | Real distributed processes, async RPCs |
| Network | In-memory object copies | gRPC / shared-memory / RDMA |
| Object store capacity | Abstract "units" | Bytes (default 30% RAM, capped at 200 GB Linux / 2 GB macOS) |
| Scheduling | Deterministic score function | Distributed spillback scheduling, resource reports |
| Fault detection | Explicit `fail_node()` call | Heartbeats, GCS failure detection |
| Actor model | Stub state object | Full actor worker pool, method calls, concurrency |
| Ownership | Driver owns all refs | Each CoreWorker owns its submitted refs |

## Scenarios

1. **Ownership + reconstruction** — task-generated objects rebuild after a worker dies; `ray.put` objects fate-share with the owner.
2. **Hybrid scheduling** — pack for locality until utilization crosses `spread_threshold`, then spread within the top-k group.
3. **Autoscaler** — add nodes when pending demand exceeds capacity; remove idle nodes after timeout.
4. **Object-store spilling** — eager spilling at 80% threshold plus LRU eviction.
