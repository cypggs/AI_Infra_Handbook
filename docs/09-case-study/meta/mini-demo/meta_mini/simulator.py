"""The core training simulator.

Runs a synchronous training job step-by-step, injecting hard failures and SDCs
according to the configured per-GPU rates, and applying checkpoint/validation
policy. Fully deterministic given a ``seed``.
"""

from __future__ import annotations

import random

from meta_mini.checkpoint import is_checkpoint_step
from meta_mini.failures import per_step_cluster_hazard
from meta_mini.model import JobConfig, SimResult
from meta_mini.sdc import is_validation_step


class TrainingSimulator:
    """Simulates one synchronous training job under failures + SDC."""

    def run(self, cfg: JobConfig) -> SimResult:
        rng = random.Random(cfg.seed)

        hard_hazard = per_step_cluster_hazard(
            cfg.hard_fail_rate, cfg.n_gpus, cfg.step_seconds
        )
        sdc_hazard = per_step_cluster_hazard(
            cfg.sdc_rate, cfg.n_gpus, cfg.step_seconds
        )

        wall = 0.0
        last_ckpt = 0          # step index of the most recent *clean* checkpoint
        cur = last_ckpt        # current frontier (steps completed this episode)
        corrupted = False      # True if an SDC is present but not yet caught

        interruptions = 0
        sdc_detected = 0       # caught by validation before being baked in
        sdc_baked = 0          # corrupted a checkpoint, or reached target corrupted
        recompute = 0          # steps executed then discarded by rollback

        ckpt_t = 0.0
        restart_t = 0.0
        valid_t = 0.0

        executed = 0           # safety cap to guarantee termination

        while cur < cfg.target_steps:
            if executed >= cfg.max_step_budget:
                # Pathological failure rate: the job never converged.
                return self._abort(cfg, wall, interruptions, sdc_detected,
                                   sdc_baked, recompute, ckpt_t, restart_t, valid_t)

            executed += 1
            cur += 1
            wall += cfg.step_seconds

            # (a) Hard (static/transient) failure -> immediate halt + rollback.
            if rng.random() < hard_hazard:
                interruptions += 1
                recompute += cur - last_ckpt
                cur = last_ckpt
                corrupted = False
                restart_t += cfg.restart_seconds
                wall += cfg.restart_seconds
                continue

            # (b) SDC injection (silent; no immediate effect).
            if (not corrupted) and (rng.random() < sdc_hazard):
                corrupted = True

            # (c) Validation point: runs *before* checkpoint, so an SDC is caught
            #     before it can be baked into a checkpoint (when
            #     validation_interval <= ckpt_interval).
            if is_validation_step(cur, cfg.validation_interval):
                valid_t += cfg.validation_seconds
                wall += cfg.validation_seconds
                if corrupted:
                    sdc_detected += 1
                    recompute += cur - last_ckpt
                    cur = last_ckpt
                    corrupted = False
                    restart_t += cfg.restart_seconds
                    wall += cfg.restart_seconds
                    continue

            # (d) Checkpoint point: commit a clean checkpoint, or discover the
            #     corruption has been baked in.
            if is_checkpoint_step(cur, cfg.ckpt_interval):
                ckpt_t += cfg.ckpt_seconds
                wall += cfg.ckpt_seconds
                if corrupted:
                    # The corrupted state was about to be durably saved.
                    sdc_baked += 1
                    recompute += cur - last_ckpt
                    cur = last_ckpt
                    corrupted = False
                    restart_t += cfg.restart_seconds
                    wall += cfg.restart_seconds
                else:
                    last_ckpt = cur  # clean commit

        # (e) Epilogue: if we reached the target with an uncaught SDC, that
        #     corruption is baked into the final weights -> wasted work.
        if corrupted:
            sdc_baked += 1
            recompute += cur - last_ckpt

        return SimResult(
            completed=True,
            target=cfg.target_steps,
            recompute_steps=recompute,
            ckpt_seconds=ckpt_t,
            restart_seconds=restart_t,
            validation_seconds=valid_t,
            interruptions=interruptions,
            sdc_detected=sdc_detected,
            sdc_baked=sdc_baked,
            step_seconds=cfg.step_seconds,
            wall_seconds=wall,
        )

    @staticmethod
    def _abort(cfg: JobConfig, wall: float, interruptions: int, sdc_detected: int,
               sdc_baked: int, recompute: int, ckpt_t: float, restart_t: float,
               valid_t: float) -> SimResult:
        return SimResult(
            completed=False,
            target=cfg.target_steps,
            recompute_steps=recompute,
            ckpt_seconds=ckpt_t,
            restart_seconds=restart_t,
            validation_seconds=valid_t,
            interruptions=interruptions,
            sdc_detected=sdc_detected,
            sdc_baked=sdc_baked,
            step_seconds=cfg.step_seconds,
            wall_seconds=wall,
        )
