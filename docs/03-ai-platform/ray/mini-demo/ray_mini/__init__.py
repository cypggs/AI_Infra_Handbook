"""Mini deterministic Ray-core simulator.

Models the *observable* mechanisms of Ray Core for teaching:
  - ownership + ObjectRef (future) resolution
  - hybrid scheduling (locality vs spread, top-k, spread threshold)
  - per-node Plasma-like object store (primary/evictable copies, 80% spilling)
  - lineage reconstruction (task-generated objects rebuildable; ray.put & small
    inline objects fate-share with their owner)
  - a simple autoscaler (pending demand -> scale up; idle -> scale down)

It is NOT a real distributed runtime: execution is synchronous and single
threaded, "time" advances by explicit ticks, and there is no real network.
See README.md for the production-diff table.
"""

from .model import Config, ObjectRef, Task, SimResult
from .runtime import MiniRay, OwnerDiedError, ObjectLostError

__all__ = [
    "Config",
    "ObjectRef",
    "Task",
    "SimResult",
    "MiniRay",
    "OwnerDiedError",
    "ObjectLostError",
]
