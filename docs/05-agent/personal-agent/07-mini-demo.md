# 工程实践：Mini Personal Agent

> 一句话理解：**Mini Personal Agent 是一个纯 Python、零外部依赖的最小主动式个人智能体原型，演示个人记忆层（episode + 画像 + 召回）、个人数据连接器（邮件/日历/文件）、相关性门控的主动推送，以及 auto/ask/deny 三态权限门。**

本章说明 Mini Demo 的设计意图、目录布局、运行方式与关键代码。Demo 代码位于 `docs/05-agent/personal-agent/mini-demo/`，包名为 `personal_agent_mini`。

## 场景

Demo 提供 4 个端到端场景，覆盖个人智能体流水线的关键环节：

1. **日程冲突主动提醒**：日历里"产品评审会 14:00–15:00"与"牙医预约 14:30–15:15"重叠，Agent 在感知循环中检测冲突并推送提醒（proactive）。
2. **重要邮件摘要推送**：老板（画像中的重要联系人）发来紧急预算邮件 → 摘要推送；营销 newsletter 相关性打分 0 被静默过滤（attention economics）。
3. **跨天记忆召回**：3 天前用户说过"记住：咖啡偏好=燕麦拿铁"，现在问"我上周末喝了什么咖啡？"→ 从画像 + 情景记忆双线召回。
4. **权限拒绝与人工确认**：发邮件触发 ask 态挂起等待批准；外部支付被 deny 态硬拒绝；批准后邮件才真正发出。

## 目录结构

```
docs/05-agent/personal-agent/mini-demo/
├── README.md
├── pyproject.toml
├── personal_agent_mini/
│   ├── __init__.py
│   ├── clock.py        # FakeClock：确定性时间
│   ├── memory.py       # 个人记忆层：episode + 画像 + 检索
│   ├── connectors.py   # 邮件/日历/文件假连接器
│   ├── agent.py        # 主动循环 + 相关性打分 + 权限门
│   └── demo.py         # 4 个端到端场景
└── tests/
    ├── test_clock.py
    ├── test_memory.py
    ├── test_connectors.py
    ├── test_agent.py
    └── test_demo.py
```

## 运行方式

```bash
cd docs/05-agent/personal-agent/mini-demo
pip install -e ".[dev]"
personal-agent-demo
```

`pyproject.toml` 中定义了 console script：

```toml
[project.scripts]
personal-agent-demo = "personal_agent_mini.demo:run_demo"
```

也可以直接调用 Python：

```bash
python -m personal_agent_mini.demo
```

## 关键代码片段

### clock.py：确定性时钟

```python
class FakeClock:
    def __init__(self, start: str = "2026-10-17T08:00:00"):
        self._now = datetime.fromisoformat(start)

    def now(self) -> datetime:
        return self._now

    def advance(self, *, minutes: int = 0, hours: int = 0, days: int = 0) -> datetime:
        self._now += timedelta(minutes=minutes, hours=hours, days=days)
        return self._now
```

### memory.py：个人记忆层

三个关键点：episode 事件流（带天级索引）、画像蒸馏（保留出处 episode id）、中英文检索（拉丁词整词匹配 + 中文二元组匹配）。

```python
class PersonalMemory:
    def add_episode(self, kind, content, ts, tags=()) -> Episode:
        self._counter += 1
        ep = Episode(id=f"ep{self._counter}", kind=kind, content=content,
                     ts=ts, tags=tuple(tags), day=ts.date().isoformat())
        self._episodes.append(ep)
        self._extract_profile(ep)   # "记住：key=value" → 画像, 带出处
        return ep

    def _extract_profile(self, ep: Episode) -> None:
        m = _REMEMBER_RE.search(ep.content)   # 记住[:：]key=value
        if m and ep.kind == "user":
            self.remember(m.group(1), m.group(2), ep.ts, ep)

    def recall(self, query, limit=3, kind=None) -> list[Episode]:
        terms = _terms(query)   # 拉丁词整词 / 中文二元组
        scored = [(ep.matches(terms), ep) for ep in self._episodes
                  if (kind is None or ep.kind == kind)]
        scored = [(s, ep) for s, ep in scored if s > 0]
        scored.sort(key=lambda x: (-x[0], x[1].id))
        return [ep for _, ep in scored[:limit]]
```

### connectors.py：事件驱动的假连接器

每个连接器持有事件日志，`poll()` 只返回未消费的事件（增量语义），事件 id 从 evt1 开始按连接器独立编号：

```python
class Connector:
    def _emit(self, kind, payload):
        self._counter += 1
        ev = SourceEvent(f"evt{self._counter}", self.name, kind, self.clock.now(), payload)
        self._events.append(ev)
        return ev

    def poll(self):
        pending = self._events[self._cursor:]
        self._cursor = len(self._events)
        return list(pending)
```

`CalendarConnector.conflicts()` 用排序 + 双指针检测时间重叠，是场景 1 的检测内核。

### agent.py：主动循环 + 权限门

感知循环：`poll` 事件 → 相关性打分 → 低于阈值静默归档 → 写记忆 → 生成通知；日历冲突每轮幂等检测（同一冲突对只报一次）。

```python
def step(self) -> bool:
    acted = False
    for conn in self.connectors.values():
        for ev in conn.poll():
            acted = True
            score, reasons = self.scorer.score(ev, self.memory)
            if score < self.threshold:
                self._log("ignore", id=ev.id, score=score, reasons=reasons)
                continue
            self.memory.add_episode(ev.source, self._describe(ev), ev.ts)
            self._handle(ev)
    if self._check_conflicts():
        acted = True
    return acted
```

三态权限门：所有副作用先过 `PermissionGate.check()`，ask 态挂起为 pending 并推送 confirm 级通知，批准后由 `approve()` 真正执行：

```python
def act(self, action_type: str, **kw) -> dict:
    decision = self.gate.check(action_type)   # auto / ask / deny
    if decision.requires_approval:
        self.pending.append({...})
        self._notify("confirm", "需要确认", f"{action_type} 等待批准：{kw}")
        return {"status": "awaiting_approval", "pending_id": pid}
    if not decision.allowed:
        self._notify("info", "操作被拒绝", decision.reason)
        return {"status": "denied", "reason": decision.reason}
    return {"status": "ok", "result": self._execute(action_type, **kw)}
```

默认策略表：

| 动作类型 | 策略 | 理由 |
|---|---|---|
| read_email / read_calendar / summarize_email | auto | 只读，零副作用 |
| send_email / create_event | ask | 对外副作用，先确认 |
| external_payment | deny | 超出演示能力边界 |

## 测试结果

运行 `pytest tests/ -v` 覆盖 clock、memory、connectors、agent、demo 五个模块，**共 40 个测试，全部通过**：

```text
tests/test_agent.py ............ 12 passed
tests/test_clock.py ....... 4 passed
tests/test_connectors.py ....... 7 passed
tests/test_demo.py ..... 5 passed
tests/test_memory.py ......... 10 passed
============================== 40 passed in 0.04s ==============================
```

测试重点包括：episode/事件 id 从 1 开始编号、画像提取保留出处、非用户 episode 不触发画像、"记住："事实可遗忘（记忆主权）、低相关性邮件被过滤、冲突提醒幂等（不重复轰炸）、ask 态挂起→批准→执行全链路、deny 态硬拒绝、通知 id 连续编号、跨天召回。

## Demo 输出

运行 `personal-agent-demo` 的完整输出（节选）：

```text
Mini Personal Agent Demo (fake clock, zero deps)

=== 场景 1：日程冲突主动提醒 ===
[10-19 08:00] (info) 日程冲突：产品评审会 与 牙医预约: 10-19 14:00 起两场活动重叠（产品评审会 至 15:00，牙医预约 至 15:15），建议调整其一。
  trace#1 sense: id=evt1, source=calendar, kind=event_added
  trace#2 relevant: id=evt1, score=2.0, reasons=['calendar event']
  trace#3 sense: id=evt2, source=calendar, kind=event_added
  trace#4 relevant: id=evt2, score=2.0, reasons=['calendar event']
  trace#6 conflict: a=产品评审会, b=牙医预约

=== 场景 2：重要邮件摘要推送 ===
[10-17 09:00] (digest) 新邮件摘要: 老板 <boss@corp.com>: Q4 预算审批紧急 — 请在本周五前批复 Q4 预算，否则影响采购
  trace#1 sense: id=evt1, source=email, kind=new_email
  trace#2 relevant: id=evt1, score=5.0, reasons=['sender matches profile:重要联系人', "urgent keyword '紧急'"]
  trace#4 sense: id=evt2, source=email, kind=new_email
  trace#5 ignore: id=evt2, score=0.0, reasons=[]

=== 场景 3：跨天记忆召回 ===
  Q: 我上周末喝了什么咖啡？
  A: 你的画像：咖啡偏好 = 燕麦拿铁；2026-10-14 [user] 周末去了杭州，在西湖边的咖啡馆工作了一下午；2026-10-14 [user] 记住：咖啡偏好=燕麦拿铁

=== 场景 4：权限拒绝与人工确认 ===
[10-17 10:00] (confirm) 需要确认: send_email 等待批准：{'to': 'client@corp.com', 'subject': '报价单', 'body': '请查收附件。'}
[10-17 10:00] (info) 操作被拒绝: action 'external_payment' is denied by policy
[10-17 10:00] (info) 已发送: 邮件已发送给 client@corp.com
  trace#1 permission: action=send_email, allowed=False, requires_approval=True, reason=action 'send_email' requires user approval
  trace#3 permission: action=external_payment, allowed=False, requires_approval=False, reason=action 'external_payment' is denied by policy
```

场景 2 尤其值得对照阅读：老板的邮件打分 5.0（画像联系人 +3、紧急词 +2）被推送；newsletter 打分 0.0 被静默归档——这就是"注意力经济学"的最小演示。

## 与生产系统的差异

这个 Demo 刻意保持最小化，生产落地时至少需要补齐：

| 方面 | Demo | 生产 |
|---|---|---|
| 相关性判断 | 规则打分（联系人/紧急词/来源权重） | LLM 判断 + 用户状态（忙闲/勿扰/时区）+ 反馈学习 |
| 记忆检索 | 关键词二元组重叠 | 向量检索 + 知识图谱 + 时序衰减 + 画像冲突消解 |
| 规划 | 场景内置的固定任务 | LLM 规划 + 长任务 checkpoint + sub-agent 委派 |
| 连接器 | 内存假数据 | OAuth 生命周期管理、增量同步（webhook/delta）、限流重试 |
| 权限门 | 内存策略表 | 凭证代理（模型不见明文）、网络守门、策略审计日志 |
| 执行沙箱 | 同进程函数调用 | per-user VM/容器、浏览器自动化、快照休眠 |
| 通知 | 内存队列 | 多通道投递、批处理窗口、退避升级、送达确认 |
| 隐私合规 | 无 | 记忆主权控制台、数据导出、级联遗忘、地域策略 |
| 计费 | 无 | per-user 沙箱时长/token/出口流量计量与套餐配额 |

## 本章小结

- Mini Personal Agent 用 5 个模块复现了主动式个人智能体的最小闭环：FakeClock 保证确定性；记忆层演示 episode + 画像 + 召回；连接器演示事件驱动增量感知；权限门演示 auto/ask/deny 与人工批准；4 个场景覆盖 proactive、注意力过滤、跨天记忆与信任路径。
- 40 个确定性测试全部通过；Demo 输出与本文一致。
- 与生产的差距集中在 LLM 化（判断/规划/蒸馏）、凭证与沙箱、通知投递与隐私合规四个方向。

**参考来源**
- [Proactive Memory in AI Agents（Mem0）](https://mem0.ai/library/agent-memory/proactive-memory)
- [A Survey on the Security of Long-Term Memory in LLM Agents（arXiv:2604.16548）](https://arxiv.org/html/2604.16548v1)
