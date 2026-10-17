# 7. Mini Demo：延迟、投机与经济学

本主题的 Mini Demo 是纯 Python + numpy、CPU 可运行、完全确定性的模拟包 `cursor_case_mini`，位于本主题 `mini-demo/` 目录（代码路径引用：`docs/09-case-study/cursor/mini-demo/`）。它把 Cursor 案例里最值得动手验证的五组机制做成可运行模型：

| 模块 | 模拟的机制 | 对应章节 |
|---|---|---|
| `indexing.py` | 代码库索引管道：chunk → embed → Merkle 增量同步 → 混淆路径向量检索 | [3.4 索引演进](03-architecture)、[5.3](05-core-modules) |
| `latency.py` | Tab 端到端延迟预算分解（260ms 教学预算 + 确定性 P50/P95） | [2.1](02-core-ideas)、[4.2](04-workflow) |
| `speculative.py` | Speculative Edits：现有文件作确定性草稿的命中率/加速比模型 | [5.2](05-core-modules) |
| `sandbox.py` | 后台 Agent 沙箱：配额硬约束、bin-packing、TTL 回收 | [5.5](05-core-modules) |
| `economics.py` | 订阅推理经济学：盈亏平衡、毛利率、Router 节省 | [2.4](02-core-ideas)、[8 章](08-production-practice) |
| `demo.py` | 5 个端到端场景 | 本章 |

## 运行方式

```bash
cd docs/09-case-study/cursor/mini-demo
pip install -e ".[dev]"
pytest tests/ -v        # 89 个确定性测试
python -m cursor_case_mini.demo
```

下文所有输出逐字来自 demo 的实际运行（确定性，可复现）。所有模型参数为教学用的简化值，仅对齐公开口径的相对量级，不代表 Cursor 真实内部数字。

## 场景 1：代码库索引管道——Merkle 增量同步

核心代码（`indexing.py`）：按空行边界切块（近似 AST 感知）、哈希词袋嵌入、Merkle 树指纹比对、混淆路径存储。首次同步 3 个文件全部切块嵌入；二次同步只改 1 个文件、删 1 个文件：

```text
场景1 代码库索引管道
  首次同步: {'added': 3, 'updated': 0, 'removed': 0, 'unchanged': 0, 'chunks_reembedded': 3}
  二次同步(改 1 文件删 1 文件): {'added': 0, 'updated': 1, 'removed': 1, 'unchanged': 1, 'chunks_reembedded': 1}
  索引规模: {'files': 2, 'chunks': 7}
  检索 '如何建立数据库连接 connect' top-2:
    命中 混淆路径=fa7741/ece25525f... 行 0-0
    命中 混淆路径=fa7741/2369d3c43... 行 0-1
```

工程读数：**增量同步把带宽成本钉死在"变化率 × 块大小"上**，与仓库总大小解耦——这正是 Merkle 树相对"全量重传"的根本优势，也是 Git 思想的直接移植（[5.3](05-core-modules)）。检索只回传混淆路径 + 行号区间，对应官方"服务端不留明文代码"的架构承诺；教学嵌入用哈希词袋替代神经嵌入模型，保留了"相似文本余弦高、无关文本接近零"的检索语义。

## 场景 2：Tab 延迟预算——大头在哪里

核心代码（`latency.py`）：九段教学预算合计 260ms（对齐官方 2025-01 更新后口径），对数正态抖动（sigma=0.15，种子固定）生成端到端样本：

```text
场景2 Tab 补全延迟预算（教学预算，合计 260 ms，官方口径：更新后约 260 ms）
  阶段拆解: 按键防抖与本地触发 10ms; 上下文组装(光标邻域+最近编辑+打开文件) 25ms; 本地缓存查询(KV/草稿缓存) 2ms; 网络往返(TLS+RTT) 40ms; 服务端排队与路由 5ms; Prefill(长上下文填充,预填 hungry) 130ms; 首 token 解码 30ms; 客户端渲染与预测显示 10ms; 杂项(打点/序列化) 8ms
  更新前口径同结构合计: 475 ms（官方口径约 475 ms）
  端到端样本(n=10000, seed=42): mean 262.9 p50 261.8 p95 300.0 p99 319.0
  贡献前三: Prefill(长上下文填充,预填 hungry) 130ms; 网络往返(TLS+RTT) 40ms; 首 token 解码 30ms
  Prefill 若省 50ms: 端到端下降 19.2%
```

方法论读数：prefill 一段独占 50% 预算，解释了官方为什么把"小模型 + MoE + KV 复用 + 缓存预热"全部押在 prefill 侧【一手访谈】；p95（300.0ms）比 p50 高 15%，补全类交互必须按 p95 做预算；敏感性分析给出优化排序的铁律——**省 50ms 要挑 130ms 的环节下手，2ms 的环节全省也只有 0.8%**。

## 场景 3：Speculative Edits——收益与编辑局部性成正比

核心代码（`speculative.py`）：把整文件重写抽象为"未改动 token 成批验证（32/步）+ 改动 token 逐步生成"，扫不同改动率：

```text
场景3 Speculative Edits（8192 token 整文件重写）
  改动率 -> 命中率/加速比:
    改动率 2%: 命中率 97.89%, 加速比 15.85x
    改动率 5%: 命中率 95.10%, 加速比 9.27x
    改动率 10%: 命中率 89.89%, 加速比 5.12x
    改动率 20%: 命中率 80.29%, 加速比 2.80x
    改动率 40%: 命中率 59.50%, 加速比 1.54x
  对齐官方口径: vanilla 108 tok/s x 9.27 = 1001 tok/s（官方约 1000 tok/s）
  5% 改动率下 8192 token 重写耗时 8183 ms
```

机制读数：真实代码编辑绝大多数是局部修改，落在 2%-10% 改动率区间，对应 5x-16x 加速——官方"约 13x 于朴素推理"的口径正落在此区间（官方 13x 还叠加了"验证比生成更便宜"的硬件因素）。当改动率逼近 40%（接近重写），投机退化为负收益，这正是官方为 Apply 单独维持一个微调模型、而不是直接复用 Chat 模型的原因：让模型生成"像局部编辑的整文件"，保住投机的命中率。

## 场景 4：沙箱配额调度——隔离是有成本的

核心代码（`sandbox.py`）：32 核/128G 宿主机调度 5 个 Agent 沙箱（其中 agent-3 申请 16 核接近半机）：

```text
场景4 后台 Agent 沙箱调度（32 核/128G 宿主机，5 个 Agent）
  统计: {'launched': 5.0, 'reclaimed': 5.0, 'queued_events': 2.0, 'avg_cpu_util': 0.2031, 'final_running': 0.0}
  事件流(前 8 条):
    tick=0 启动 agent=agent-0
    tick=0 启动 agent=agent-1
    tick=0 启动 agent=agent-2
    tick=0 启动 agent=agent-3
    tick=0 排队 agent=agent-4 (cpu 4 mem 8)
    tick=1 排队 agent=agent-4 (cpu 4 mem 8)
    tick=2 回收 agent=agent-1
    tick=2 回收 agent=agent-3
```

调度读数：硬配额保证隔离下限（agent 观测资源永不超额，测试强制校验），代价是碎片化——平均 CPU 利用率只有 20.31%。真实 Cursor 用 auto-scaling 池摊平峰谷（且 Composer RL 与 Cloud Agents 复用同一调度器，见 [5.5](05-core-modules)）；本模型的价值在于把"隔离下限、TTL 回收、超额排队"三条配额语义变成可测试的代码契约。

## 场景 5：订阅推理经济学——盈亏平衡与毛利悬崖

核心代码（`economics.py`）：按官方口径复现 $20 额度池的盈亏平衡，并对轻度/重度用户算毛利率：

```text
场景5 订阅推理经济学（Pro $20/月，含 $20 API 价额度）
  sonnet_4: 单请求成本 $0.0900, $20 额度约 222 次
  gemini: 单请求成本 $0.0370, $20 额度约 541 次
  gpt_4.1: 单请求成本 $0.0312, $20 额度约 641 次
  轻度(100 次/月): MarginResult(requests=100, revenue=20.0, serving_cost=9.0, margin_pct=55.0, verdict='盈利（额度内）')
  重度(600 次/月): MarginResult(requests=600, revenue=54.0, serving_cost=54.0, margin_pct=0.0, verdict='亏损（补贴超额用户，靠长尾盈利用户对冲）')
  Router 节省(Auto Intelligence vs 全量 Fable 5): 46.7%
  cost per commit 官方口径: auto_intelligence $6.76, auto_balance $4.63, fable_5 $12.69, opus_4.8 $7.34
  Tab 日请求 4 亿次的推理成本教学折算: $40/天
```

经济学读数：三个模型的盈亏平衡数（222/541/641 次）与官方口径（约 225/550/650 次）逐一对齐，验证了"额度池 = 透明化转售"的模型。毛利率结构是悬崖式的：额度内 55%，超额后趋向零（本模型按成本价转售超额部分；真实产品另有加价，见 [第 8 章](08-production-practice) 定价风波）。Router 的 46.7% 节省（官方 cost-per-commit 表直接计算）说明：**在固定订阅下，调度器的每一分节省都直接变成毛利**——这是 Router 被做成一等产品功能的经济动机。
