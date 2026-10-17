"""集群建设排程模拟：并行工作流 + 关键路径分析，复现"122 天"式压缩。

对应 xAI Colossus 案例的工程组织核心：
"不是把每个环节加速，而是重排依赖关系——用移动燃气轮机先解决电，
网络按 pod 滚动交付，服务器边到货边上架，让电网审批完全退出关键路径。"

模型：每个任务有 (名称, 工期天, 依赖)。采用最早开始调度：
start = max(dep.finish)；makespan = 全部任务的最大完工。
关键路径 = 从 makespan 任务沿"决定其开始的依赖"回溯到起点。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    name: str
    duration_days: int
    deps: tuple[str, ...] = ()


def schedule(tasks: list[Task]) -> dict[str, tuple[int, int]]:
    """最早开始调度。返回 {任务名: (开始日, 完工日)}。

    任务可以任意顺序给出；依赖必须构成 DAG。
    """
    by_name = {t.name: t for t in tasks}
    if len(by_name) != len(tasks):
        raise ValueError("duplicate task names")
    start: dict[str, int] = {}
    finish: dict[str, int] = {}

    remaining = dict(by_name)
    # 迭代解析，直到所有任务排完；剩余不减少说明有环
    while remaining:
        progressed = False
        for name, task in list(remaining.items()):
            if all(d in finish for d in task.deps):
                s = max((finish[d] for d in task.deps), default=0)
                start[name] = s
                finish[name] = s + task.duration_days
                del remaining[name]
                progressed = True
        if not progressed:
            raise ValueError("dependency cycle detected: %s" % sorted(remaining))
    return {name: (start[name], finish[name]) for name in by_name}


def makespan_days(tasks: list[Task]) -> int:
    """全部任务的最大完工日。"""
    result = schedule(tasks)
    return max(f for _, f in result.values())


def critical_path(tasks: list[Task], goal: str | None = None) -> list[str]:
    """关键路径：从 goal 任务（默认 makespan 任务）沿"决定其开始的依赖"回溯。"""
    by_name = {t.name: t for t in tasks}
    if goal is not None and goal not in by_name:
        raise ValueError(f"unknown goal task: {goal}")
    result = schedule(tasks)
    current = goal or max(result, key=lambda n: result[n][1])
    path = [current]
    while by_name[current].deps:
        deps = by_name[current].deps
        current = max(deps, key=lambda d: result[d][1])
        path.append(current)
    return list(reversed(path))


def conventional_plan() -> list[Task]:
    """教科书式串行流程：先建完再装机（"typical 12-24 months"数量级）。"""
    return [
        Task("site_and_permits", 90),
        Task("grid_upgrade", 150, ("site_and_permits",)),
        Task("facility_fitout", 120, ("site_and_permits",)),
        Task("server_logistics", 120, ("site_and_permits",)),
        Task("network_fabric", 90, ("facility_fitout", "grid_upgrade")),
        Task("rack_and_stack", 60, ("server_logistics", "network_fabric")),
        Task("cluster_integration", 21, ("rack_and_stack",)),
        Task("burn_in", 14, ("cluster_integration",)),
        Task("first_training", 0, ("burn_in",)),
    ]


def aggressive_plan() -> list[Task]:
    """Colossus 式压缩流程：临时动力 + 滚动交付 + 并行施工。

    关键重排：
    - 移动燃气轮机（25 天）让"电"不再等待电网改造（120 天，后台进行）
    - 5 个网络 pod 并行铺，42 天全部就绪
    - 10 个服务器波次两两并行交付，边到货边上架
    - 第一个 rack 完成（第 46 天）后即可开始首批训练
    """
    tasks: list[Task] = [
        Task("mobilize", 5),
        Task("temp_turbines", 25, ("mobilize",)),      # 第 30 天临时供电就绪
        Task("facility_prep", 40, ("mobilize",)),
        Task("grid_upgrade", 120, ("mobilize",)),      # 电网扩容退居后台
    ]
    for p in range(5):
        tasks.append(Task(f"pod{p}_network", 12, ("temp_turbines",)))
    for w in range(10):
        deps = ("mobilize",) if w < 2 else (f"wave{w - 2}_delivery",)
        tasks.append(Task(f"wave{w}_delivery", 8, deps))
    for r in range(10):
        tasks.append(Task(f"rack{r}", 4,
                          (f"wave{r}_delivery", f"pod{r % 5}_network",
                           f"rack{r - 1}" if r > 0 else "temp_turbines")))
    tasks.append(Task("first_training", 15, ("rack0",)))
    tasks.append(Task("cluster_integration", 21, ("rack9",)))
    tasks.append(Task("burn_in", 19, ("cluster_integration",)))  # 集群就绪 = 第 122 天
    return tasks


def compression_report() -> dict[str, object]:
    """对照报告：两种流程的 makespan、关键路径与压缩倍数。

    aggressive_days 取"集群就绪"（burn_in 完工）——电网扩容等后台
    收尾工作不计入，这与"122 天建成 Colossus"的官方口径一致。
    """
    conv = conventional_plan()
    aggr = aggressive_plan()
    conv_span = makespan_days(conv)
    aggr_result = schedule(aggr)
    aggr_ready = aggr_result["burn_in"][1]
    return {
        "conventional_days": conv_span,
        "aggressive_days": makespan_days(aggr),
        "cluster_ready_days": aggr_ready,
        "compression_ratio": conv_span / aggr_ready,
        "conventional_critical_path": critical_path(conv),
        # 以集群就绪为目标的压缩流程关键路径（不含后台电网收尾）
        "aggressive_critical_path": critical_path(aggr, goal="burn_in"),
        "first_training_day": aggr_result["first_training"][1],
        "grid_upgrade_done_day": aggr_result["grid_upgrade"][1],
    }
