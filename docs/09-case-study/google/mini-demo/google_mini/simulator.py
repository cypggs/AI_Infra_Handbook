"""主模拟循环：在 3D-torus 上跑同步训练，注入芯片故障，按策略恢复。

关键设计（保证三种策略公平对比同一组故障）：

1. **故障序列预抛、与策略无关**——用 seed 一次性 roll 出每个逻辑步是否故障，
   三种策略面对 *完全相同* 的故障点。触发后即"消费"（一次性故障），回滚重跑
   该步时不再重复触发，避免死循环。

2. **同一故障、不同处理**：
   - naive / reconfigure：回滚到最近 checkpoint，重跑未提交的步（wasted 增加），
     再支付一次迁移 / 维修停机。reconfigure 还产生 fleet 闲置。
   - reroute（NSDI Path 2）：**不回滚**，作业原地继续；只把该步重试一次（wasted +1），
     支付极短停机，但此后每步叠加一个步时惩罚 tax（多次故障累积）。

3. **useful = 已提交步数 × 基础步时**（不含 tax）；wall 含 tax / 停机 / checkpoint。
   于是 reroute 的 tax 体现为 wall 增长快于 useful → 有效 MFU 下降，而 reconfigure
   的代价体现为回滚重跑 + 一次性迁移停机。
"""
import random

from .collective import torus_allreduce_time
from .failures import per_step_cluster_hazard, roll_failures
from .model import JobConfig, SimResult
from .recovery import apply_strategy
from .topology import Torus3D


class TrainingSimulator:
    """跑一次 target_steps 步的同步训练模拟。

    每步 = AllReduce（torus 分维）+ 前向/反向计算。每步都有概率发生芯片故障；
    故障按 cfg.strategy 支付恢复开销（见 recovery.py）。
    """

    def run(self, cfg: JobConfig) -> SimResult:
        rng = random.Random(cfg.seed)
        torus = Torus3D(cfg.dims)
        n = torus.size

        base_step = torus_allreduce_time(
            cfg.dims, cfg.msg_bytes, cfg.link_bandwidth_bps, cfg.link_latency_s
        ) + cfg.compute_seconds
        hazard = per_step_cluster_hazard(
            cfg.per_chip_fail_rate_per_hour, n, base_step
        )

        # 预抛故障序列（与策略无关）；fails_at[i] 表示逻辑步 i+1 是否故障（触发后消费）。
        fails_at = roll_failures(rng, cfg.target_steps, hazard)

        wall = 0.0          # 总挂钟（含 tax / 停机 / checkpoint）
        ckpt_t = 0.0
        recovery_t = 0.0
        fleet_idle = 0.0
        tax = 0.0           # reroute 累积的步时惩罚（naive/reconfigure 恒为 0）
        last_ckpt = 0
        cur = 0             # 已提交（commit）的步数
        wasted = 0          # 回滚 / 重试作废的步数
        executed = 0        # 实际尝试的次数（含重跑）
        failures = reconfigures = reroutes = 0

        def make_result(completed: bool) -> SimResult:
            useful = cur * base_step
            return SimResult(
                completed=completed, target=cfg.target_steps, steps_done=cur,
                wasted_steps=wasted, useful_seconds=useful, wall_seconds=wall,
                ckpt_seconds=ckpt_t, recovery_seconds=recovery_t,
                fleet_idle_chip_seconds=fleet_idle, failures=failures,
                reconfigures=reconfigures, reroutes=reroutes,
                final_step_penalty=tax, total_chips=n,
            )

        while cur < cfg.target_steps:
            step = cur + 1                # 本次尝试的逻辑步
            executed += 1
            if executed > cfg.max_step_budget:
                return make_result(False)

            # 本次尝试的步时：reroute 下随 tax 累积而变长
            wall += base_step * (1.0 + tax)

            # (a) 故障 → 集合通信停顿，按策略恢复
            if step <= len(fails_at) and fails_at[step - 1]:
                fails_at[step - 1] = False            # 消费：一次性故障
                failures += 1
                outcome = apply_strategy(cfg.strategy, cfg, n)
                wall += outcome.job_downtime_seconds
                recovery_t += outcome.job_downtime_seconds
                fleet_idle += outcome.fleet_idle_chip_seconds
                tax += outcome.step_penalty_increment
                if cfg.strategy == "reconfigure":
                    reconfigures += 1
                elif cfg.strategy == "reroute":
                    reroutes += 1
                if outcome.rollback:
                    # naive / reconfigure：丢弃自上次 checkpoint 以来的进度，重跑
                    wasted += step - last_ckpt
                    cur = last_ckpt
                else:
                    # reroute：保留进度，仅该步作废、原地重试
                    wasted += 1
                    # cur 不变 → 下一轮重试同一逻辑步
                continue

            # (b) 该步成功：提交进度
            cur = step

            # (c) checkpoint 点：提交干净进度
            if cur % cfg.ckpt_interval == 0:
                ckpt_t += cfg.ckpt_seconds
                wall += cfg.ckpt_seconds
                last_ckpt = cur

        return make_result(True)
