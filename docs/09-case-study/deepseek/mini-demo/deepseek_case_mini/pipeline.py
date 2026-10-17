"""pipeline.py：DualPipe 风格的流水线并行调度模拟器。

复现 DeepSeek-V3 技术报告 §3.2.1 与 Table 2 的核心账：

- 朴素 1F1B 的流水线气泡 = (PP-1)(F+B)；
- DualPipe 双向流水（正反两个方向的 micro-batch 从流水线两端同时注入，
  每个设备承载两个虚拟 stage），气泡 = (PP/2-1)(F+B-3W)，其中 W 是
  被重叠掉的流水间通信（3W：发送激活、发送梯度以及配对重叠）；
- DualPipe 的代价：参数需要两份拷贝、峰值激活显存增加 1/PP；
- 关键前提：all-to-all 与 PP 通信必须能被计算完全盖住，否则
  "暴露通信时间"会把省下的气泡还回去——这就是 EP all-to-all 优化
  （见 ep.py）与 DualPipe 必须成对出现的原因。

同时提供一个通用列表调度器（list scheduler），用 1F1B 的
"在途 micro-batch 数 ≤ PP-s"约束数值复现 1F1B 的闭式气泡，
让闭式公式和模拟结果互相印证。
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 闭式模型（技术报告 Table 2）
# ---------------------------------------------------------------------------

def bubble_1f1b(pp: int, f: float, b: float) -> float:
    """1F1B 流水线气泡（单位：任意时间单位）。

    来源：DeepSeek-V3 技术报告 Table 2：Bubble = (PP-1)(F+B)。
    GPipe 的气泡公式相同（区别只在显存：GPipe 要缓存全部 M 个 micro-batch
    的激活）。
    """
    if pp < 2:
        return 0.0
    return (pp - 1) * (f + b)


def bubble_dualpipe(pp: int, f: float, b: float, w: float) -> float:
    """DualPipe 流水线气泡：(PP/2-1)(F+B-3W)。

    前提：流水间通信总量 3W 可被计算盖住（F+B ≥ 3W），否则按暴露处理
    （见 dualpipe_exposed_comm）。PP 必须是偶数（每个设备承载两个虚拟 stage）。
    """
    if pp < 4:
        return 0.0
    if pp % 2 != 0:
        raise ValueError("DualPipe 要求 PP 为偶数（每个设备承载两个虚拟 stage）")
    inner = max(f + b - 3.0 * w, 0.0)
    return (pp // 2 - 1) * inner


def dualpipe_exposed_comm(pp: int, w: float, f: float, b: float) -> float:
    """流水通信盖不住时的暴露量：max(0, 3W - (F+B)) 每 chunk。

    DualPipe 双向注入后，单位 chunk 内可用来盖通信的计算窗口是 F+B；
    通信 3W 超过这个窗口的部分会被暴露到关键路径上。
    """
    if pp < 4:
        return 0.0
    return max(3.0 * w - (f + b), 0.0)


def bubble_reduction_ratio(pp: int, f: float, b: float, w: float) -> float:
    """DualPipe 相对 1F1B 的气泡缩减比：1 - bubble_dp / bubble_1f1b。"""
    base = bubble_1f1b(pp, f, b)
    if base == 0.0:
        return 0.0
    return 1.0 - bubble_dualpipe(pp, f, b, w) / base


def pipeline_bubble_ratio(bubble: float, makespan: float) -> float:
    """气泡率 = 气泡时间 / 总完工时间。"""
    if makespan <= 0.0:
        raise ValueError("makespan 必须为正")
    return bubble / makespan


def memory_units(method: str, pp: int) -> dict:
    """各 PP 方法的显存占用（以"单个 micro-batch 激活"为单位）。

    Table 2：参数 1F1B/ZB1P 为 1×，DualPipe 为 2×（两份参数拷贝）；
    激活：1F1B/ZB1P 为 PP 个单位，DualPipe 为 PP+1 个单位
    （峰值只多 1/PP——因为大 EP 分摊了每卡的专家参数，两份参数拷贝
    几乎不增加显存）。
    """
    if method in ("1f1b", "zb1p"):
        return {"params": 1.0 * pp, "activations": float(pp)}
    if method == "dualpipe":
        return {"params": 2.0 * pp, "activations": float(pp + 1)}
    raise ValueError(f"未知方法: {method}")


# ---------------------------------------------------------------------------
# 通用列表调度器（数值复现 1F1B 闭式气泡）
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """一个 (micro-batch, stage, 前向/反向) 任务。"""

    mb: int
    stage: int
    kind: str  # "F" 或 "B"
    start: float = 0.0
    end: float = 0.0
    scheduled: bool = False


@dataclass
class ScheduleResult:
    tasks: list[Task]
    makespan: float
    bubble: float
    bubble_ratio: float
    timeline: dict[int, list[Task]] = field(default_factory=dict)


def _build_tasks(num_microbatches: int, pp: int) -> list[Task]:
    tasks = []
    for mb in range(num_microbatches):
        for s in range(pp):
            tasks.append(Task(mb, s, "F"))
        for s in reversed(range(pp)):
            tasks.append(Task(mb, s, "B"))
    return tasks


def _deps(task: Task, pp: int, window: int | None) -> list[tuple[int, int, str]]:
    """任务依赖：(mb, stage, kind) 列表。

    window=None          → GPipe（无在途限制）
    window=pp（默认 1F1B）→ stage s 最多在途 pp-s 个 micro-batch：
                            F(mb,s) 必须等待 B(mb-(pp-s), s) 完成
    """
    deps = []
    if task.kind == "F":
        if task.stage > 0:
            deps.append((task.mb, task.stage - 1, "F"))
        if window is not None:
            mb_dep = task.mb - (pp - task.stage)
            if mb_dep >= 0:
                deps.append((mb_dep, task.stage, "B"))
    else:  # "B"
        if task.stage < pp - 1:
            deps.append((task.mb, task.stage + 1, "B"))
        else:
            deps.append((task.mb, task.stage, "F"))
    return deps


def simulate_pipeline(
    pp: int,
    num_microbatches: int,
    f: float,
    b: float,
    window: int | None = None,
    max_rounds: int = 100000,
) -> ScheduleResult:
    """列表调度模拟 GPipe/1F1B 流水线。

    每 stage 串行占用（一个时钟只能跑一个任务）；任务就绪 =
    依赖完成且 stage 空闲。反向先于前向调度（1F1B 稳态行为）。
    返回每个任务的 start/end，makespan 与数值气泡（makespan − M(F+B)）。
    """
    tasks = _build_tasks(num_microbatches, pp)
    index = {(t.mb, t.stage, t.kind): t for t in tasks}
    stage_free = [0.0] * pp

    # 每 stage 的就绪队列：反向优先
    def ready(task: Task) -> bool:
        if task.scheduled:
            return False
        for d in _deps(task, pp, window):
            if not index[d].scheduled:
                return False
        return True

    def dep_end(task: Task) -> float:
        ends = [index[d].end for d in _deps(task, pp, window)]
        return max(ends, default=0.0)

    scheduled_count = 0
    rounds = 0
    while scheduled_count < len(tasks):
        progress = False
        # 按 stage 依次尝试调度一个任务
        for s in range(pp):
            candidates = [
                t
                for t in tasks
                if t.stage == s and ready(t)
            ]
            if not candidates:
                continue
            # 反向优先，再按 micro-batch 升序
            candidates.sort(key=lambda t: (0 if t.kind == "B" else 1, t.mb))
            t = candidates[0]
            start = max(dep_end(t), stage_free[s])
            dur = f if t.kind == "F" else b
            t.start, t.end, t.scheduled = start, start + dur, True
            stage_free[s] = t.end
            scheduled_count += 1
            progress = True
        rounds += 1
        if not progress:
            raise RuntimeError("调度死锁：依赖环或窗口约束过紧")
        if rounds > max_rounds:
            raise RuntimeError("调度未收敛")

    makespan = max(t.end for t in tasks)
    ideal = num_microbatches * (f + b)
    bubble = makespan - ideal
    timeline = {s: sorted([t for t in tasks if t.stage == s], key=lambda t: t.start) for s in range(pp)}
    return ScheduleResult(
        tasks=tasks,
        makespan=makespan,
        bubble=bubble,
        bubble_ratio=pipeline_bubble_ratio(bubble, makespan),
        timeline=timeline,
    )


# ---------------------------------------------------------------------------
# 可视化：ASCII 甘特图
# ---------------------------------------------------------------------------

def ascii_timeline(result: ScheduleResult, pp: int, width: int = 60) -> str:
    """把调度结果画成字符甘特图（F=前向 #，B=反向 o，空闲 .）。"""
    makespan = result.makespan
    lines = []
    header = "stage |" + "".join(
        str(int(makespan * i / width)).rjust(5) for i in range(0, width, 10)
    )
    lines.append(header)
    for s in range(pp):
        row = ["."] * width
        for t in result.timeline[s]:
            i0 = int(t.start / makespan * width)
            i1 = max(i0 + 1, int(t.end / makespan * width))
            ch = "#" if t.kind == "F" else "o"
            for i in range(i0, min(i1, width)):
                row[i] = ch
        lines.append(f"  {s:2d}  |{''.join(row)}")
    lines.append("legend: # = forward(F), o = backward(B), . = bubble/idle")
    return "\n".join(lines)
