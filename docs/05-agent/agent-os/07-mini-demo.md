# 工程实践：Mini Agent OS

> 一句话理解：**Mini Agent OS 是一个纯 Python、零外部依赖的最小 Agent OS 原型，演示如何把多个 Agent 当作进程来 spawn、调度、在沙箱中执行、通过消息总线协作，并记录完整调度轨迹。**

本章说明 Mini Demo 的设计意图、目录布局、运行方式与关键代码。Demo 代码位于 `docs/05-agent/agent-os/mini-demo/`，包名为 `agent_os_mini`。

## 场景

Demo 模拟一个多 Agent 协作计算任务：

```text
计算 (a + b) * c，其中 a=2, b=3, c=4
```

任务被拆分为两个子任务：

1. `AdderAgent` 计算 `a + b`，得到中间结果。
2. `MultiplierAgent` 用中间结果乘以 `c`，得到最终答案。

`CoordinatorAgent` 负责协调：

- 把 `a`、`b`、`c` 写入共享工作区。
- 依次 spawn 出 `AdderAgent` 与 `MultiplierAgent`。
- 通过消息总线接收子 Agent 的结果。
- 拿到最终结果后终止所有进程。

在这个过程里，Kernel 负责 spawn/schedule/terminate，Scheduler 选择下一个可运行进程，Sandbox 只允许调用 `calculate` 工具并限制调用次数，Workspace 与 Message Bus 负责状态与结果传递，Observer 记录完整事件轨迹。

## 目录结构

```
docs/05-agent/agent-os/mini-demo/
├── README.md
├── pyproject.toml
├── agent_os_mini/
│   ├── __init__.py
│   ├── kernel.py         # spawn、schedule、terminate、registry
│   ├── process.py        # AgentProcess 生命周期与状态机
│   ├── scheduler.py      # RoundRobin / Priority 调度器
│   ├── sandbox.py        # 能力/策略执行沙箱
│   ├── workspace.py      # 共享 + per-process blackboard
│   ├── message_bus.py    # inbox/outbox IPC
│   ├── observer.py       # 事件 trace
│   └── demo.py           # run_demo() 入口
└── tests/
    └── ...               # pytest 覆盖
```

## 运行方式

```bash
cd docs/05-agent/agent-os/mini-demo
pip install -e ".[dev]"
agent-os-demo
```

`pyproject.toml` 中定义了 console script：

```toml
[project.scripts]
agent-os-demo = "agent_os_mini.demo:run_demo"
```

也可以直接调用 Python：

```python
from agent_os_mini.demo import run_demo
run_demo()
```

## 关键代码片段

### process.py：进程状态机

```python
from enum import Enum, auto

class ProcessState(Enum):
    READY = auto()
    RUNNING = auto()
    WAITING = auto()
    TERMINATED = auto()

class AgentProcess:
    def __init__(self, pid, role, step_fn, workspace, bus, observer, priority=0):
        self.pid = pid
        self.role = role
        self.step_fn = step_fn
        self.workspace = workspace
        self.bus = bus
        self.observer = observer
        self.priority = priority
        self.state = ProcessState.READY
        self.result = None
        self.metadata = {}
        self._steps_taken = 0

    def step(self):
        self.state = ProcessState.RUNNING
        outcome = self.step_fn(self)
        self._steps_taken += 1
        if self.state == ProcessState.RUNNING:
            self.state = ProcessState.READY
        return outcome

    def terminate(self):
        self.state = ProcessState.TERMINATED
```

### kernel.py：内核

```python
class Kernel:
    def __init__(self, scheduler, sandbox, observer, workspace, bus):
        self.scheduler = scheduler
        self.sandbox = sandbox
        self.observer = observer
        self.workspace = workspace
        self.bus = bus
        self.bus._on_deliver = self._wakeup_process
        self._processes = {}
        self._pid_counter = 0

    def _next_pid(self):
        self._pid_counter += 1
        return f"p{self._pid_counter}"

    def spawn(self, role, step_fn, priority=0):
        pid = self._next_pid()
        process = AgentProcess(pid, role, step_fn, self.workspace, self.bus, self.observer, priority)
        self._processes[pid] = process
        self.bus.register(pid)
        self.scheduler.add(process)
        self.observer.log("kernel_spawn", "kernel", pid=pid, role=role)
        return process

    def terminate(self, process):
        process.terminate()
        self.scheduler.remove(process)
        self.bus.unregister(process.pid)
        self.observer.log("kernel_terminate", "kernel", pid=process.pid)

    def step_once(self):
        process = self.scheduler.next()
        if process is None:
            return None
        self.observer.log("kernel_schedule", "kernel", pid=process.pid, role=process.role)
        outcome = process.step()
        if process.is_terminated():
            self.scheduler.remove(process)
        return outcome

    def run(self, max_steps=100):
        for step in range(max_steps):
            if not any(p.is_ready() for p in self._processes.values()):
                break
            self.step_once()
```

### scheduler.py：RoundRobin 调度器

```python
class RoundRobinScheduler:
    def __init__(self, observer):
        self.observer = observer
        self._ready = []
        self._index = 0

    def add(self, process):
        if process not in self._ready:
            self._ready.append(process)

    def remove(self, process):
        if process in self._ready:
            self._ready.remove(process)

    def next(self):
        ready = [p for p in self._ready if p.is_ready()]
        if not ready:
            return None
        process = ready[self._index]
        self._index = (self._index + 1) % len(ready)
        return process
```

### sandbox.py：沙箱与策略

```python
class PolicyViolation(Exception):
    pass

class Sandbox:
    def __init__(self, observer, allowed_tools=None, max_calls=2):
        self.observer = observer
        self.allowed_tools = allowed_tools or set()
        self.max_calls = max_calls
        self._calls_used = {}
        self._tools = {}

    def register_tool(self, name, fn):
        self._tools[name] = fn

    def authorize(self, pid, tool_name):
        if tool_name not in self.allowed_tools:
            return PolicyDecision(allowed=False, reason=f"tool {tool_name!r} not in allowlist")
        used = self._calls_used.get(pid, 0)
        if used >= self.max_calls:
            return PolicyDecision(allowed=False, reason=f"call budget exceeded")
        return PolicyDecision(allowed=True)

    def call(self, pid, tool_name, *args, **kwargs):
        decision = self.authorize(pid, tool_name)
        self.observer.log("sandbox_decision", "sandbox", pid=pid, tool=tool_name, allowed=decision.allowed)
        if not decision.allowed:
            raise PolicyViolation(decision.reason)
        self._calls_used[pid] = self._calls_used.get(pid, 0) + 1
        return self._tools[tool_name](*args, **kwargs)
```

### workspace.py：共享黑板

```python
class Workspace:
    def __init__(self):
        self._shared = {}
        self._private = {}

    def write_shared(self, key, value):
        self._shared[key] = value

    def read_shared(self, key, default=None):
        return self._shared.get(key, default)

    def write_private(self, pid, key, value):
        self._private.setdefault(pid, {})[key] = value

    def read_private(self, pid, key, default=None):
        return self._private.get(pid, {}).get(key, default)

    def shared_snapshot(self):
        return dict(self._shared)
```

### message_bus.py：消息总线

```python
@dataclass
class Message:
    sender: str
    recipient: str
    topic: str
    payload: Any

class MessageBus:
    def __init__(self, on_deliver=None):
        self._inboxes = {}
        self._outboxes = {}
        self._on_deliver = on_deliver

    def register(self, pid):
        self._inboxes.setdefault(pid, [])
        self._outboxes.setdefault(pid, [])

    def send(self, sender, recipient, topic, payload):
        msg = Message(sender, recipient, topic, payload)
        self._outboxes[sender].append(msg)
        self._inboxes[recipient].append(msg)
        if self._on_deliver:
            self._on_deliver(recipient)
        return msg

    def inbox(self, pid):
        return list(self._inboxes[pid])
```

### demo.py：入口

```python
def _calculate(operation, x, y):
    if operation == "add":
        return x + y
    if operation == "multiply":
        return x * y
    raise ValueError(f"unsupported operation: {operation}")

def _make_coordinator_step(kernel, a, b, c):
    def step(process):
        phase = process.metadata.setdefault("phase", "init")
        process.workspace.write_shared("a", a)
        process.workspace.write_shared("b", b)
        process.workspace.write_shared("c", c)

        if phase == "init":
            process.workspace.write_shared("task", "add")
            adder = kernel.spawn("adder", _make_adder_step(kernel))
            process.metadata["adder_pid"] = adder.pid
            process.metadata["phase"] = "wait_add"
            process.state = ProcessState.WAITING
            return {"action": "spawn_adder", "adder": adder.pid}

        if phase == "wait_add":
            for msg in process.bus.inbox(process.pid):
                if msg.topic == "add_result":
                    process.workspace.write_shared("intermediate", msg.payload)
                    process.bus.clear_inbox(process.pid)
                    process.workspace.write_shared("task", "multiply")
                    multiplier = kernel.spawn("multiplier", _make_multiplier_step(kernel))
                    process.metadata["multiplier_pid"] = multiplier.pid
                    process.metadata["phase"] = "wait_multiply"
                    process.state = ProcessState.WAITING
                    return {"action": "spawn_multiplier", "sum": msg.payload}
            process.state = ProcessState.WAITING
            return {"action": "waiting_for_adder"}

        if phase == "wait_multiply":
            for msg in process.bus.inbox(process.pid):
                if msg.topic == "multiply_result":
                    process.workspace.write_shared("final", msg.payload)
                    process.result = msg.payload
                    process.metadata["phase"] = "done"
                    kernel.terminate_all()
                    return {"action": "done", "result": msg.payload}
            process.state = ProcessState.WAITING
            return {"action": "waiting_for_multiplier"}

        kernel.terminate_all()
        return {"action": "already_done", "result": process.result}
    return step

def _make_adder_step(kernel):
    def step(process):
        a = process.workspace.read_shared("a")
        b = process.workspace.read_shared("b")
        total = kernel.sandbox.call(process.pid, "calculate", "add", a, b)
        process.workspace.write_shared("intermediate", total)
        coordinator = next(p for p in kernel._processes.values() if p.role == "coordinator")
        process.bus.send(process.pid, coordinator.pid, "add_result", total)
        process.terminate()
        return {"action": "add", "result": total}
    return step

def run_demo(a=2, b=3, c=4):
    observer = Observer()
    workspace = Workspace()
    bus = MessageBus()
    sandbox = Sandbox(observer, allowed_tools={"calculate"}, max_calls=2)
    sandbox.register_tool("calculate", _calculate)
    scheduler = RoundRobinScheduler(observer)
    kernel = Kernel(scheduler, sandbox, observer, workspace, bus)

    coordinator = kernel.spawn("coordinator", _make_coordinator_step(kernel, a, b, c), priority=1)
    coordinator.workspace.write_private(coordinator.pid, "task", f"calculate ({a}+{b})*{c}")

    kernel.run(max_steps=50)
    # 打印 schedule trace、sandbox decisions、workspace state 与最终结果
    ...
```

## 测试结果

运行 `pytest tests/ -q` 可看到对 kernel、process、scheduler、sandbox、workspace、message_bus、observer 的覆盖。

示例输出：

```text
$ agent-os-demo
=== Schedule Trace ===
[kernel] kernel_spawn: pid=p1 role=coordinator priority=1
[kernel] kernel_spawn: pid=p2 role=adder priority=0
[scheduler] scheduler_pick: pid=p1
[process] process_step: pid=p1 role=coordinator step=0
[kernel] kernel_schedule: pid=p2 role=adder
[process] process_step: pid=p2 role=adder step=0
[sandbox] sandbox_decision: pid=p2 tool=calculate allowed=True
[sandbox] sandbox_call: pid=p2 tool=calculate result=5 used=1
[kernel] kernel_terminate: pid=p2
[kernel] kernel_wakeup: pid=p1
[scheduler] scheduler_pick: pid=p1
[process] process_step: pid=p1 role=coordinator step=1
[kernel] kernel_spawn: pid=p3 role=multiplier priority=0
...
=== Sandbox Decisions ===
ALLOW pid=p2 tool=calculate reason=
ALLOW pid=p3 tool=calculate reason=

=== Workspace State ===
  a = 2
  b = 3
  c = 4
  task = multiply
  intermediate = 5
  final = 20

Final answer: 20
```

## 与生产系统的差异

这个 Demo 刻意保持最小化，生产落地时至少需要补齐：

| 方面 | Demo | 生产 |
|---|---|---|
| LLM 集成 | 无，Agent 是纯 Python 函数 | 真实 LLM、function calling、Token 实时统计 |
| 调度 | RoundRobin / Priority，单队列 | MLFQ、Token-aware、Fair Share、多租户抢占 |
| 隔离 | 同一 Python 进程内的对象 | 容器/VM/cgroups、网络隔离、Secret 管理 |
| 能力管理 | 内存 allowlist + 调用预算 | Registry、版本、命名空间、MCP Server 动态发现 |
| 工作区 | 内存字典 | 分布式 KV/对象存储、配额、ACL、持久化 |
| 消息总线 | 内存 inbox/outbox | A2A/MCP 兼容、持久化、死信队列、跨网络路由 |
| 可观测 | 内存事件列表 | OpenTelemetry、Prometheus、结构化日志、长期保留 |
| 恢复 | 无 checkpoint/rollback | 状态快照、分级恢复、circuit breaker |
| 安全治理 | 简单 allowlist | OPA/Rego、Governed MCP、HITL、审计合规 |
| 多租户 | 无 | 命名空间、配额、网络隔离、审计隔离 |

## 本章小结

- Mini Agent OS 通过 8 个文件演示了 Agent OS 的最小闭环：Kernel spawn → Scheduler 调度 → Sandbox 策略执行 → Workspace/MessageBus 协作 → Observer 记录 → Kernel terminate。
- 场景虽小，但覆盖了进程状态机、调度策略、能力白名单、共享黑板、IPC、事件 trace 等核心抽象。
- Demo 与生产系统的差距主要在 LLM 集成、隔离强度、调度复杂度、Registry 持久化、消息总线可靠性、可观测后端与恢复机制。

**参考来源**
- [AIOS: LLM Agent Operating System](https://arxiv.org/abs/2403.16971)
- [MCP Specification](https://modelcontextprotocol.io/specification/2025-03-26/architecture)
- [Governed MCP: From Technical Specifications to Multi-Agent Governance](https://arxiv.org/abs/2604.16870)
