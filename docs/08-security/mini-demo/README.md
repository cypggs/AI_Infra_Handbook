# AI Security Mini Demo

A tiny, stdlib-only security gateway that demonstrates core controls for AI systems:

- API key authentication with constant-time comparison
- Role-based access control (RBAC)
- Prompt injection / jailbreak guardrails
- PII redaction in outputs
- Append-only audit logging

## Install

```bash
cd docs/08-security/mini-demo
pip install -e ".[dev]"
```

## Run demo

```bash
python -m security_mini.demo
```

## Test

```bash
pytest tests/ -q
```

## Design

The demo intentionally avoids external services and LLM keys so it can run on CPU in a sandbox. It shows how a production **AI Security Gateway** sits in front of model/Agent/RAG calls to enforce identity, policy, and safety controls.
