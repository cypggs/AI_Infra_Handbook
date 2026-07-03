# 8. 企业生产实践

本章把前几章的机制放回真实 fleet 规模，聚焦五个生产主题：**NSDI'24 的可靠性体系如何在大规模落地**、**Borg 与 TPU 基础设施的调度协同**、**Multislice 的规模化**、**可持续性（PUE/碳/电网）**、以及**安全治理与开放生态**。数字与机制均来自一手来源（NSDI'24、Borg EuroSys'15、Multislice 博客、Google 可持续页面、AI Principles、Frontier Safety Framework），二手或未披露项明确标注。

---

## 8.1 可靠性即设计：NSDI'24 在生产的落地

### 8.1.1 为什么大规模同步训练"天生脆弱"

NSDI'24 开宗明义："现代 ML 模型（如 LLM）需要前所未有的硬件量……把期望 MTBF 压到**小时甚至分钟**级"。原因是 ML 作业"更常用静态（编译时）分片策略 + **gang 调度，要求所有计算资源同时健康**"。直接约束（§2.1 原文）：

> "To train a model, all TPU processes must be simultaneously up to synchronously update their weights via ICI collectives. A single failed, or interrupted process will interrupt the whole training process."

即一颗坏芯片毒化整个 4096 芯片同步作业。这个约束是整套可靠性设计的出发点。

### 8.1.2 故障分类与频率（§5.2 Fleet Statistics）

NSDI'24 给出 fleet 实测的每组件每日故障率：

> "In an average supercomputer, each day, **0.08% of the TPU machines, 0.005% of the ICI cables, and 0.04% of the OCS** experience a failure."

单组件率很小，但 Pod 有数千机器/链路/交换机，"受硬件中断影响的作业数不可忽视"。故障按 blast radius 分类：机器/ICI 链路故障局部化、可被 reconfigure 容忍；**OCS 故障 blast radius 大**——"可影响超算中所有 cube"。故障在三层诊断："TPU machine、ICI link、OCS"。

### 8.1.3 检测体系（§3.6，论文真实术语）

检测是四层栈，**不是**泛泛的"性能/功能健康"：

1. **`healthd`（§3.6.1）**：每台 TPUv4 机器上的守护进程，实时监控 24 条单向 ICI 链路、TPU 与 CPU 间 PCIe、4 颗 TPU ASIC；症状按临界度排序，严重症状触发 Borg 驱逐并重调度。
2. **preflight "end-to-end check"（§3.6.2）**：每个用户作业前跑一个**迷你样本 workload**，覆盖硬件 + 软件组件（TPU 驱动、固件、libtpunet）。
3. **preflight "intent-driven checker"（§3.6.2）**：把物理级硬件指标对照一组 **golden "within spec" 阈值**，发现"链路质量亚标"等不明显问题。失败则 borglet 告知 Borg Prime 重调度。
4. **坏机标记不可用（§3.3）**：Borg 聚合所有信号（borglet←healthd、Pod Manager←OCS、修复自动化、包管理器），"受影响 TPU 机器被标记不可用，驱逐运行中作业（带通知），排除待调度作业落到它们上面，直至解决"。

### 8.1.4 恢复：两条真实路径（§5.2–5.3）

> **术语提醒**：论文里**没有** "cherry-pick"。两条路径的真实名称如下。

**Path 1 — reconfigure（迁移到空闲健康 cube）**：OCS 把作业从坏 cube 迁到空闲健康 cube，**从最近 checkpoint 恢复**。用于机器/ICI 故障（小 blast radius）。代价 = 一次性迁移停机（evict + 重调度 + OCS xconnect + preflight + 重编译 + checkpoint 载入）+ 回滚重跑；恢复后零持续惩罚；被放弃坏 cube 后台修复期间闲置（fleet 代价）。

**Path 2 — reroute（fault-tolerant ICI routing）**：保留分配，libtpunet 加载**预计算的容错路由表（wild-first routing）**让流量绕开坏链路，作业**不迁移、不回滚、继续跑**。用于 OCS 故障（大 blast radius，否则要换很多 cube）。代价 = 几乎不停机，但此后每步承受持续步时惩罚。

**reroute 的量化步时惩罚（Table 3，§5.3）**：实测 0.5%–8.6%（如 RM-1 0.5%、RM-4 8.6%、LLM-1 2.6%、BERT-1 1.2%）。all-reduce workload 影响更大（"最近邻通信模式承受 50% 吞吐打击"），all-to-all workload 影响不显著（离线路由优化器已最小化 all-to-all 性能损失）。单 OCS 故障下 all-to-all 吞吐保留 92.2%–101.7%。

**opt-in 与活跃率**："**95% 的 TPUv4 训练作业 opt-in 容错 ICI 路由**以应对 OCS 中断；其余 opt-out 以排除不同路由策略带来的性能非确定性"；"任意时刻**少于 2% 的作业在跑容错路由**，与 OCS 维护事件高度相关"。

**何时选哪条**：机器/ICI 故障 → reconfigure（cube 替换 + checkpoint 重启）；OCS 故障 → reroute（保留分配、付 ≤~9% 步时税），且 OCS 组件被**优先修复**以最小化 reroute 时长。未来工作（§7）目标混合方案："provision a hot-standby cube … 直接迁移加速器状态到新 TPU，**无需写持久 checkpoint**"。

### 8.1.5 头条结果

整套体系在 fleet 规模上达成"**99.98% 系统可用率**，优雅处理**约 1% 训练作业**经历的硬件中断"。OCS 可重配性的可用率杠杆："无重配性时，1024 主机作业 decent 可用率要求每主机 99.9% 可用；引入可重配 OCS **把主机可用率要求降到 99%**"。

### 8.1.6 可靠性的工程启示

- **把拓扑做成故障单元**：cube（64 芯片）作为 blast radius，配合 OCS 让"换一组空闲 cube"成为快速恢复原语。
- **双轴权衡而非单点最优**：reconfigure（迁移停机）vs reroute（持续税）按故障类型分工，并对症优先修复。
- **检测要先于调度**：preflight 在 Borg 选 cube 后、用户二进制前跑，把"看似可调度但 golden 阈值不达标"的芯片最后一刻挡掉。
- **可用率靠重配性而非单机可靠性**：这是 OCS 投资回报的核心论据（<5% 成本换主机可用率要求从 99.9% 降到 99%）。

> 与 [Meta 案例](/09-case-study/meta/) 的 SDC 治理对照：Meta 重点攻"静默数据损坏（SDC）"这种"错了但不报错"的故障；Google 重点攻"任一故障停顿整个同步作业"的可用率。两者都是"同步训练可靠性"的硬核工程，但切入点不同。

---

## 8.2 Borg 与 TPU 基础设施的调度协同

NSDI'24 披露了 Borg 与 TPU 基础设施如何**共用真相源**并**协同避免坏芯片**：

- **datacenter model DB**：反映 TPUv4 机器及所有相关组件，"被 Borg 与 Pod Manager 共同消费，作为每台超算配置的**真相源**"，"为 cube 部署、作业调度、OCS xconnect、网络设置、健康检查设定意图"。
- **避开已知坏芯片**：Borg 调度器"把意图配置（来自 datacenter model）与当前世界观结合，把所有 TPUv4 资源组织成**可调度机器组**"，"把每个用户请求匹配到一组**可行（可用）机器**"；坏机不进可行集。
- **preflight 闸门**：在 Borg 选 cube 后、用户二进制前跑 preflight，"任何失败都导致 **Borg 重调度到不同 cube**"。
- **优先级 + 反碎片化**：Borg Prime 实现优先级调度；"为帮助反碎片化，Borg Prime 也可选择**抢占运行中 workload**（如把多个 sub-cube 作业重定位以装入更少 cube，或把多 cube 作业迁到别的 Pod 以容纳超大作业）"，受控且公平。
- **OCS 对调度的解放**："有 OCS 重配性，**Borg 不必太担心 TPU 资源的物理连续性**——任意一组空闲 cube 都能通过 OCS 交叉连接给用户作业"，直接解决"workload 碎片化"难题；且"OCS 足迹装好后，cube 一落地即可部署使用"，支持增量产能上线。

---

## 8.3 Multislice：跨 Pod 规模化

单个 Pod（ICI 域）受物理规模限（v4 = 4096 芯片；最大 slice 3072）。Multislice 让训练 run 跨多 slice/Pod，靠 DC-GN/Jupiter：

- **历史限制**："历史上训练 run 只能用单 slice……即不超过 3072 TPUv4 芯片。Multislice 让训练 run 跨多 slice、跨多 Pod，经数据中心网络（DCN）通信。"
- **并行分层**：数据并行下"激活继续走 ICI……梯度经 DCN 归约"；支持 FSDP/模型/流水线并行；引入"跨 DCN 的新分片维度"；"XLA 编译器自动把 all-reduce 分解为层次集合通信"。
- **指标**：TPUv4 上几十亿参数生成式模型 **58.9% MFU**；"多 slice 的 MFU 与单 slice 相当"（编译器优化使然）；弱扩展近线性。
- **故障恢复**："单 slice 故障时从上一个 checkpoint 自动重启；配合 GKE 进一步改善恢复体验。"

---

## 8.4 可持续性：从 PUE 到 24/7 无碳电网

Google 的可持续性目标是基础设施层面的硬承诺（来源：Google 数据中心与可持续页面）：

- **净零目标（2021 承诺）**："2021 年我们设定了到 2030 年在所有运营与价值链达成净零排放的雄心"；具体：绝对 Scope 1+2（市场基）+3 较 2019 基年降 50%，其余投资碳移除。
- **24/7 无碳能源（CFE）**："到 2030 年在我们运营的每个电网实现 24/7 无碳能源"。"自 2017 起每年用可再生能源采购匹配 100% 年度用电"；"2024 年签了约 8 GW 新清洁能源合同（史上最大年度总量，2× 2023）"。具体当前 CFE 百分比需查年度环境报告（页面未直接给数字）。
- **PUE**："2024 年我们全球数据中心机群年均 **PUE = 1.09**，对比行业平均 **1.56**——即每单位 IT 能耗的架空能耗少约 84%。"
- **AI 时代能效**："我们的数据中心每单位电力的算力是 5 年前的 6 倍以上"；2024 数据中心用电同比 +27%（AI + 产品增长），但数据中心能源排放同比 **−12%**。
- **TPU 与液冷的贡献**：Ironwood 级 Pod 用 direct-to-chip 液冷；Google 引用"水冷较风冷能降能耗与碳排"。具体 TPU 指标到 PUE 的映射未在页面披露。
- **清洁能源组合**：与 Kairos Power 的 SMR 核能协议（到 2035 年最多 500 MW）；Fervo 增强地热试点（内华达）；自 2010 起超 170 笔清洁能源 PPA、合计 >22 GW。

> 与 Meta 的 Prometheus（1GW）/Hyperion（5GW）选址与电力路线对照：两者都把"AI 数据中心的电力与碳"作为头等工程约束，但 Google 把承诺推到"24/7 无碳电网"（更强于"年度可再生能源匹配"）。

---

## 8.5 安全治理：AI Principles 与 Frontier Safety Framework

### 8.5.1 AI Principles

Google 的 AI Principles（2018 首版，已重构为三条顶层原则）：**Bold innovation**（大胆创新，AI 助人、驱动经济、解科学难题）、**Responsible development and deployment**（负责任开发部署——人类监督、安全/安全研究、设计与测试以减害与**避免不公平偏见**、**尊重隐私与知识产权**）、**Collaborative progress, together**（协作共进）。2018 原版的"不予追求的应用"（武器、违规监视、以伤害为主旨的技术、违反国际法/人权的技术）在当前页面已不作为独立可见段落呈现，责任经治理贯穿模型生命周期。

### 8.5.2 Frontier Safety Framework

DeepMind 的 Frontier Safety Framework（2024-05 引入，2026 有修改时间戳）是一套"主动识别未来可能造成严重伤害的 AI 能力、并建立检测与缓解机制"的协议，聚焦"模型级强能力（如异常自主性或复杂网络能力）带来的严重风险"。三组件：

1. **识别有严重伤害潜力的能力**，定义"最小能力水平"，称 **Critical Capability Levels（CCLs）**。
2. **周期性评估前沿模型**，开发"早期预警评估"，在跨阈值前提醒。
3. **通过缓解计划**（聚焦安全——防模型外泄；与部署——防关键能力滥用）。

初始 CCL 覆盖四域：**自主性、生物安全、网络安全、机器学习研发**。缓解分级（更高安全缓解 → 更强权重外泄保护；更高部署缓解 → 更紧关键能力管理），并承认"可能也减慢创新速率、降低能力可及性"。配套评估套件（Phuong et al. 2024）含专家预测器作为前瞻预警。

> v2.0 具体变更：博客元数据示 2026-03 修改，但 v2.0 详细 PDF 未从博客 HTML 可达——具体 delta 标 [未从一手核实]。

### 8.5.3 传输安全：PSP

Falcon 连接支持 **PSP** 加密（Google 的安全/加密协议），为 DC-GN 流量提供机密性。

---

## 8.6 开放生态：硬件闭源、软件全开

Google 在生产生态上的独特姿态（详见 [第 1 章](01-background) 对照表）：把支撑 TPU 的**完整软件栈开源**（JAX、XLA/OpenXLA、MaxText、JetStream/tpu-inference、T5X、Paxml）+ 开放权重（Gemma），但 **TPU 硅闭源**（仅 GCP 可用）。这意味着：

- **可学习**：外部能读到"跑在 Google 自研加速器上的编译 + 训练 + 服务栈"的全部源码（MaxText 是最易读的入口）。
- **可复现**：`JAX + MaxText + Cloud TPU` 是开放、可在 Cloud TPU 上复现的训练路径。
- **不可复制**：TPU 硬件本身无法在 GCP 之外获得——这是 Google 与 Meta（OCP 开放硬件设计）的根本差异。

**生产工程启示**：开放软件栈让 Google 的 ML 系统研究（GSPMD、Pathways 思想、JetStream 机制）成为社区公共知识，加速了整个生态对"编译器自动并行""TPU 原生推理"的理解与采纳；同时把硬件护城河留在硅这一层。

---

## 8.7 生产落地检查清单

若你要在 Cloud TPU 上落地大规模训练/推理，参考以下清单（综合本章与前几章）：

- [ ] **并行策略**：用 MaxText 的逻辑轴规则 + `with_sharding_constraint` 表达 FSDP/张量/流水线混合并行，而非手写集合通信。
- [ ] **跨 Pod**：单 slice 不够时启用 Multislice；激活走 ICI、梯度走 DCN；验证多 slice MFU 与单 slice 相当。
- [ ] **可靠性**：启用 NSDI'24 双路径（生产已默认）；对 OCS 故障接受 reroute 的步时税，对机器/ICI 故障走 reconfigure + checkpoint 重启。
- [ ] **checkpoint**：用 Orbax（OCDBT + Zarr3，异步）；间隔权衡回滚损失与写盘开销（见 [Mini Demo](07-mini-demo)）。
- [ ] **调度**：依赖 Borg/GKE 的优先级 + 反碎片化；让 preflight 把不达标芯片挡在调度外。
- [ ] **推理**：用 JetStream/tpu-inference 的权重分片三轴 + 连续批处理 + HBM KV cache（可 int8）；考虑 DFlash 投机解码拿 ~3×。
- [ ] **监控**：Prometheus 风格 metrics（JetStream 暴露）；MFU/步时/恢复停机作为核心 SLO。
- [ ] **可持续性**：关注 region 的 CFE 与 PUE；用液冷 region；预估训练总能耗与碳。
- [ ] **安全**：传输走 PSP；模型部署遵循 Frontier Safety Framework 的 CCL 评估。

下一章 [最佳实践](09-best-practices) 把这些提炼成可复用原则。
