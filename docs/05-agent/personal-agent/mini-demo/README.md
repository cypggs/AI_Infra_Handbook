# Mini Personal Agent Demo

一个纯 Python、零外部依赖的最小「主动式个人智能体」原型，位于 `docs/05-agent/personal-agent/mini-demo/`，包名 `personal_agent_mini`。

它演示了个人智能体的四个核心机制：

1. **个人记忆层**（`memory.py`）：episode 事件流存储 + 用户画像提取（带出处）+ 关键词检索召回；
2. **个人数据连接器**（`connectors.py`）：邮件 / 日历 / 文件三类假数据源，事件驱动的 poll 接口；
3. **主动感知循环**（`agent.py`）：感知事件 → 相关性打分（画像联系人 + 紧急词）→ 低分丢弃 → 高分生成主动通知；日程冲突检测；
4. **权限门**（`agent.py`）：所有副作用（发邮件、建日程、支付）先过策略门，支持「自动 / 需确认 / 拒绝」三态与人工批准流程。

## 运行方式

```bash
cd docs/05-agent/personal-agent/mini-demo
pip install -e ".[dev]"
personal-agent-demo
```

也可以直接：

```bash
python -m personal_agent_mini.demo
```

## 测试

```bash
pytest tests/ -v
```

## 目录结构

```
mini-demo/
├── pyproject.toml
├── personal_agent_mini/
│   ├── __init__.py
│   ├── clock.py        # FakeClock
│   ├── memory.py       # 个人记忆层
│   ├── connectors.py   # 邮件/日历/文件假连接器
│   ├── agent.py        # 主动循环 + 权限门
│   └── demo.py         # 4 个端到端场景
└── tests/
    ├── test_clock.py
    ├── test_memory.py
    ├── test_connectors.py
    ├── test_agent.py
    └── test_demo.py
```
