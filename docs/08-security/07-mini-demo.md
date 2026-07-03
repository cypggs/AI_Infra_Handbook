# Mini Demo

本章介绍 `docs/08-security/mini-demo/` 中的 AI 安全迷你示例。它用纯 Python 标准库演示一个 AI 安全网关的核心控制：API Key 认证、RBAC 授权、提示注入检测、PII 脱敏与审计日志。

## 场景

一个名为 `SecureGateway` 的网关挡在所有模型调用之前：

- 验证请求携带的 API Key。
- 根据角色判断是否有权执行某个 action。
- 检测提示注入/越狱模式。
- 模拟 LLM 返回结果，并对输出中的 PII 进行脱敏。
- 把所有决策写入 append-only 审计日志。

## 目录结构

```text
mini-demo/
├── pyproject.toml
├── README.md
├── security_mini/
│   ├── __init__.py
│   ├── config.py         # 示例 key、角色、模式配置
│   ├── auth.py           # API Key 认证（HMAC 比较）
│   ├── policy.py         # RBAC 策略
│   ├── guardrails.py     # 提示注入检测
│   ├── pii.py            # PII 识别与脱敏
│   ├── audit.py          # JSONL 审计日志
│   ├── gateway.py        # 网关编排
│   └── demo.py           # 入口示例
└── tests/
    ├── __init__.py
    ├── test_auth.py
    ├── test_policy.py
    ├── test_guardrails.py
    ├── test_pii.py
    ├── test_audit.py
    └── test_gateway.py
```

## 安装

```bash
cd docs/08-security/mini-demo
pip install -e ".[dev]"
```

## 运行 Demo

```bash
python -m security_mini.demo
```

输出示例：

```json
[
  {
    "prompt": "What is the weather today?",
    "allowed": true,
    "principal": "developer-alice",
    "decision": "allow",
    "reason": "request processed",
    "response": "The weather in Beijing is sunny, 28°C. Contact [REDACTED] for details."
  },
  {
    "prompt": "hello",
    "allowed": false,
    "principal": "anonymous",
    "decision": "deny",
    "reason": "invalid api key",
    "response": ""
  },
  ...
]
```

## 测试

```bash
pytest tests/ -q
```

当前测试覆盖：

- 合法/非法 API Key 认证。
- 不同角色的权限允许与拒绝。
- 提示注入与越狱检测。
- 邮箱、电话、SSN 的识别与脱敏。
- 端到端网关的 allow/deny/block 路径。
- 审计日志的追加与读取。

## 关键代码片段

### 1. 基于 HMAC 的 API Key 认证

```python
import hmac

def authenticate(api_key: str):
    for key_id, meta in API_KEYS.items():
        if hmac.compare_digest(api_key, key_id):
            return Principal(name=meta["name"], role=meta["role"], api_key_id=key_id)
    return None
```

### 2. RBAC 策略

```python
import fnmatch

def is_allowed(role: str, action: str) -> bool:
    return any(fnmatch.fnmatch(action, pat) for pat in ROLE_PERMISSIONS.get(role, []))
```

> 注：Demo 为了简化使用精确 action 匹配；生产环境可结合 OPA/OpenFGA 实现更细粒度授权。

### 3. 提示注入检测

```python
class PromptGuard:
    def check(self, prompt: str):
        for pattern in self._patterns:
            if pattern.search(prompt):
                return GuardResult(allowed=False, reason=f"matched {pattern.pattern}")
        return GuardResult(allowed=True, reason="input accepted")
```

### 4. PII 脱敏

```python
class PIIRedactor:
    REDACTION_TOKEN = "[REDACTED]"

    def redact(self, text: str) -> str:
        for compiled in self._patterns.values():
            text = compiled.sub(self.REDACTION_TOKEN, text)
        return text
```

### 5. 审计日志

```python
class AuditLogger:
    def log(self, event: AuditEvent) -> None:
        with self._lock:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
```

## 与生产系统的差异

| 方面 | Mini Demo | 生产系统 |
|---|---|---|
| 认证 | 内存中的 API Key | OIDC/OAuth2 + SPIFFE/SPIRE |
| 授权 | 简单 RBAC | OPA / OpenFGA / Cedar |
| Guardrails | 正则匹配 | Llama Guard、NeMo Guardrails、LLM-as-judge |
| PII | 正则 | Presidio、云端 DLP |
| 审计 | 本地 JSONL | SIEM、WORM 存储 |
| 网络 | 无 | mTLS、Service Mesh、 egress 控制 |
| 密钥管理 | 硬编码 | Vault / Cloud Secret Manager |

## 扩展练习

1. 把 `PromptGuard` 接入 Llama Guard 或 OpenAI Moderation API，替换正则。
2. 把 `AuditLogger` 写入远程不可变存储（如 S3 Object Lock）。
3. 增加细粒度 action 资源匹配（例如 `llm:chat:model=gpt-4`）。
4. 集成 Vault 实现 API Key 动态签发与轮换。
5. 在网关层增加 rate limit 与 token 成本上限。

## 小结

Mini Demo 展示了 AI 安全的最小闭环：**认证 → 授权 → 输入过滤 → 输出脱敏 → 审计**。它是理解后续生产实践章节的动手沙盒。
