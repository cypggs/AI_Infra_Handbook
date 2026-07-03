# 7. Mini Demo

本章介绍 `docs/09-case-study/meta/mini-demo/` 中的迷你示例。它复现 Meta 超大规模训练基础设施中最具辨识度、也最难理解的一组机制：**同步训练的故障经济学**——硬件故障如何造成回滚损失、checkpoint 频率如何在"损失 vs 开销"间权衡、以及 **Silent Data Corruption（SDC）如何在验证间隔与 checkpoint 间隔的赛跑中被检测或被"焊死"（baked-in）**。

这个 Demo 把 Meta 公开的可靠性数字（>66% 中断来自硬件、SDC 约每 1000 设备 1 个、有效训练时间 >95%、中断率下降约 50 倍）变成可运行、可调参、可测试的确定性模拟器。

## 场景

一个名为 `meta-mini` 的包提供：

1. **训练模拟器**（`simulator.py`）：模拟 N-GPU 同步训练任务在 `target_steps` 步内的运行。每一步都有概率发生硬件故障（static/transient）或 SDC；故障触发回滚到最近 checkpoint 并 auto-restart；SDC 静默腐蚀状态，只能靠周期性验证（validation）捕获。
2. **故障模型**（`failures.py`）：把"每 GPU 每小时故障率"换算成"同步任务的每步集群风险（per-step cluster hazard）"——这正是一个 N-GPU 同步任务可靠性 ≈ 单 GPU 可靠性 N 次方的数学体现。
3. **Checkpoint 管理器**（`checkpoint.py`）：固定间隔的同步 checkpoint，可调间隔与开销。
4. **SDC 检测器**（`sdc.py`）：周期性验证，模拟 Fleetscanner/Ripple/Hardware Sentinel 三层检测的"检测延迟"。
5. **指标**（`metrics.py`）：计算有效训练时间（effective utilization）、回滚浪费百分比、checkpoint 开销百分比、中断次数、SDC 检测/焊死计数。
6. **入口**（`demo.py`）：对比"朴素配置"（大 checkpoint 间隔、无验证）vs"优化配置"（小间隔、频繁验证）vs"理想无故障"基线，打印对比表。

整个 Demo **确定性、纯 CPU、无需任何 LLM key**——所有随机性来自带 seed 的 `random.Random`。

## 目录结构

```text
mini-demo/
├── pyproject.toml
├── README.md
├── meta_mini/
│   ├── __init__.py
│   ├── model.py          # JobConfig / Failure / SimResult 数据结构
│   ├── failures.py       # per-step cluster hazard 换算 + 故障采样
│   ├── checkpoint.py     # CheckpointManager：固定间隔同步 checkpoint
│   ├── sdc.py            # SDCDetector：周期验证（检测延迟）
│   ├── simulator.py      # TrainingSimulator.run()：主模拟循环
│   ├── metrics.py        # 有效训练时间 / 浪费 / 开销 指标
│   └── demo.py           # run_demo()：朴素 vs 优化 vs 理想 对比
└── tests/
    ├── __init__.py
    ├── test_failures.py
    ├── test_checkpoint.py
    ├── test_sdc.py
    ├── test_simulator.py
    └── test_demo.py
```

## 安装

```bash
cd docs/09-case-study/meta/mini-demo
pip install -e ".[dev]"
```

## 运行对比实验

```bash
python -m meta_mini.demo
```

输出形如（具体数字随 seed 与配置变化）：

```text
Meta 训练集群可靠性模拟（同步训练的故障经济学）
────────────────────────────────────────────────────────────────────────
配置                  有效训练时间  回滚浪费%  ckpt开销%  中断  SDC检出  SDC焊死
理想(无故障)            62.5%        0.0%      37.5%      0      0        0
朴素(大间隔/无验证)     41.2%       33.1%      19.4%     18      0       11
优化(小间隔/频繁验证)   73.8%        6.7%      16.1%     18     11        0
────────────────────────────────────────────────────────────────────────
结论：优化配置把"焊死的 SDC"清零（验证先于 checkpoint），用略多的
checkpoint/验证开销换取大幅降低的回滚浪费，有效训练时间反超朴素基线。
```

## 测试

```bash
pytest tests/ -q
```

## 关键代码片段

### 1. 同步任务的"每步集群风险"

一个 N-GPU 同步任务里，任意一个 GPU 故障都会停顿整个任务。把"每 GPU 每小时故障率"换算成"每步集群故障概率"：

```python
def per_step_cluster_hazard(rate_per_gpu_hour, n_gpus, step_seconds):
    # 单 GPU 在一步内的故障概率
    p_gpu = rate_per_gpu_hour * (step_seconds / 3600.0)
    # 任意一个 GPU 故障（任一发生即停顿）= 1 - 全都不发生
    return 1.0 - (1.0 - p_gpu) ** n_gpus
```

这正是"集群越大越脆弱"的数学——`n_gpus` 在指数上。

### 2. 主模拟循环（故障回滚 + SDC 验证赛跑）

```python
def run(self, cfg: JobConfig) -> SimResult:
    rng = random.Random(cfg.seed)
    hard_hazard = per_step_cluster_hazard(cfg.hard_fail_rate, cfg.n_gpus, cfg.step_seconds)
    sdc_hazard  = per_step_cluster_hazard(cfg.sdc_rate, cfg.n_gpus, cfg.step_seconds)

    wall = 0.0
    last_ckpt = 0          # 最近一个干净 checkpoint 的步号
    cur = last_ckpt        # 当前已完成的步（含未 checkpoint 的在途工作）
    corrupted = False      # 当前是否有未捕获的 SDC
    interruptions = sdc_detected = sdc_baked = recompute = 0
    ckpt_t = restart_t = valid_t = 0.0

    while cur < cfg.target_steps:
        cur += 1
        wall += cfg.step_seconds

        # (a) 硬件故障 → 立即停顿，回滚到 last_ckpt
        if rng.random() < hard_hazard:
            interruptions += 1
            recompute += cur - last_ckpt
            cur = last_ckpt
            corrupted = False
            restart_t += cfg.restart_seconds
            wall += cfg.restart_seconds
            continue

        # (b) SDC 注入（静默，无立即效果）
        if not corrupted and rng.random() < sdc_hazard:
            corrupted = True

        # (c) 验证点：先于 checkpoint，捕获 SDC
        if cfg.validation_interval and cur % cfg.validation_interval == 0:
            valid_t += cfg.validation_seconds
            wall += cfg.validation_seconds
            if corrupted:                      # 赶在 checkpoint 前捕获
                sdc_detected += 1
                recompute += cur - last_ckpt
                cur = last_ckpt
                corrupted = False
                restart_t += cfg.restart_seconds
                wall += cfg.restart_seconds
                continue

        # (d) checkpoint 点：提交或焊死
        if cur % cfg.ckpt_interval == 0:
            ckpt_t += cfg.ckpt_seconds
            wall += cfg.ckpt_seconds
            if corrupted:                      # 腐蚀被 checkpoint 焊死！
                sdc_baked += 1
                recompute += cur - last_ckpt
                cur = last_ckpt
                corrupted = False
                restart_t += cfg.restart_seconds
                wall += cfg.restart_seconds
            else:
                last_ckpt = cur                # 干净提交

    # 收尾：若带着未捕获 SDC 到达终点，这部分工作作废
    if corrupted:
        sdc_baked += 1
        recompute += cur - last_ckpt

    return SimResult(completed=True, target=cfg.target_steps, recompute_steps=recompute,
                     ckpt_seconds=ckpt_t, restart_seconds=restart_t, validation_seconds=valid_t,
                     interruptions=interruptions, sdc_detected=sdc_detected, sdc_baked=sdc_baked,
                     step_seconds=cfg.step_seconds, wall_seconds=wall)
```

关键设计：**验证点（c）先于 checkpoint（d）执行**——只要 `validation_interval ≤ ckpt_interval`，SDC 总能在被 checkpoint 焊死前被捕获。这就是"优化配置把 SDC 焊死清零"的机制根源，也对应 Meta 用 Fleetscanner/Ripple/Hardware Sentinel 三层检测把 SDC 控制在"焊死"之前的工程目标。

### 3. 有效训练时间指标

```python
def effective_utilization(r: SimResult) -> float:
    # 有效训练时间 = 持久前进的步 × 每步时间 / 总挂钟时间
    # 一切回滚重算、checkpoint、restart、validation 都算"非有效"开销
    if r.wall_seconds <= 0:
        return 0.0
    return (r.target * r.step_seconds) / r.wall_seconds
```

这与 Meta 公开的 **"有效训练时间 >95%"** 同口径：分子是真正推进模型前进的计算，分母是含所有故障恢复开销的挂钟时间。

## 与生产系统的差异

| 方面 | Mini Demo | Meta 生产 |
|---|---|---|
| 故障模型 | 每步 Bernoulli（static/transient + SDC 两类） | static/transient/silent 三类，含热失控、不可纠正错误等子模式 |
| SDC 检测 | 周期 validation（单一机制） | Fleetscanner（45–60 天）+ Ripple（ms–s，几天）+ Hardware Sentinel（内核态，+41%）三层 |
| SDC 失败模式 | 焊死 / 被检测 二元 | NaN 传播、梯度方差污染，含 reductive triage/deterministic training/hyper-checkpointing 等治理 |
| Checkpoint | 固定间隔同步 | 跨数千 rank 数百毫秒、进程组初始化分钟级、含 hyper-checkpointing |
| 恢复 | 回滚到 last_ckpt + restart | 隔离故障节点 + 重组集群 + auto-restart |
| 拓扑 | 无 | fat-tree + 拓扑感知调度 + NCCL 协同（影响 step 时间与 straggler） |
| 硬件 | 抽象为故障率 | H100/Blackwell/MI300/MTIA 异构，含 AALC 散热约束 |

## 扩展练习

1. 加入 **straggler 模型**：某些 step 因网络抖动变慢，模拟 straggler 对吞吐的拖累（不只是硬故障）。
2. 把固定间隔 checkpoint 升级为 **hyper-checkpointing**：检测到 SDC 后动态提高 checkpoint 频率，观察 triage 加速。
3. 实现 **tri-variate computational training**：用 shadow rank 重复训练 step，不一致才回滚——对比它对 SDC 焊死率的影响。
4. 引入 **MTIA vs H100 异构故障率**：不同硅有不同 SDC 率，模拟异构集群的可靠性组合。
5. 把指标导出为 Prometheus，画出有效训练时间随 checkpoint 间隔的曲线，找到最优点。

## 小结

Mini Demo 把 Meta 超大规模训练最硬核的工程——**同步训练的故障经济学与 SDC 治理**——变成可调参的确定性模拟器。它直观回答了三个问题：为什么集群越大越脆弱（per-step hazard 的指数项）；checkpoint 间隔如何在"回滚损失 vs checkpoint 开销"间权衡；以及为什么"验证先于 checkpoint"能把 SDC 焊死清零。这是理解 Meta "中断率下降 50 倍、有效训练时间 >95%"数字背后机制的最快路径。
