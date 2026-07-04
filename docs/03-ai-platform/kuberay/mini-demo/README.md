# KubeRay Mini Demo

This mini demo simulates the KubeRay control plane without requiring a real Kubernetes cluster or Ray runtime.

## What it demonstrates

- `RayCluster` reconciliation: creation of head service, serve service, head pod, and worker pods.
- Pod readiness modeled with a `FakeClock`.
- Worker group scaling (simulating autoscaler behavior).
- `RayJob` lifecycle: cluster creation, submitter job creation, job completion, and cluster cleanup.

## Run

```bash
cd docs/03-ai-platform/kuberay/mini-demo
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
python -m kuberay_mini.demo
```

## Structure

```
mini-demo/
├── pyproject.toml
├── kuberay_mini/
│   ├── __init__.py
│   └── demo.py       # FakeClock, FakeApiServer, Informer, WorkQueue, Reconcilers, Controller
└── tests/
    ├── __init__.py
    └── test_demo.py  # pytest cases
```

## Note

This is a teaching simulation. It does not run real Ray processes or talk to a real Kubernetes API server.
