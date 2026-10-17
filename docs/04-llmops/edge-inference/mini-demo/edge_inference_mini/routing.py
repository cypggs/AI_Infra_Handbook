"""端-云混合路由：隐私分级 + 延迟 SLO + 成本 + 热节流降额的决策模型。

对应 Apple Intelligence 的「端侧优先、Private Cloud Compute 兜底」式路由、
Android AICore 的调度策略与各类助手 App 的端云混合推理。决策优先级：

1. 硬性约束：隐私级别 2（机密）必须留在端侧，级别 1（内部）不允许走公有云；
2. SLO 可行性：端侧估时（含热节流降额）与云端估时（含网络）都要算；
3. 可行解里先选满足 SLO 的；都满足时选成本低的一方（端侧计机会成本）。

所有估时都是解析模型，参数显式，输出完全确定。
"""

from __future__ import annotations

from dataclasses import dataclass

# 隐私级别
PUBLIC = 0        # 公开内容（闲聊、百科）
INTERNAL = 1      # 内部资料（可走企业云/专有云，不走公有云）
CONFIDENTIAL = 2  # 机密（个人敏感数据，必须端侧）

# 云端类型
CLOUD_PUBLIC = "public_cloud"
CLOUD_PRIVATE = "private_cloud"   # 如 Private Cloud Compute / 企业专有云


@dataclass(frozen=True)
class DeviceProfile:
    prefill_tps: float      # 端侧 prefill 吞吐（tok/s，计算受限）
    decode_tps: float       # 端侧稳态 decode 吞吐（tok/s，带宽受限）
    derate_after_s: float   # 持续推理多久后开始热节流
    derate_factor: float    # 节流后性能保持比例（0~1）


@dataclass(frozen=True)
class CloudProfile:
    rtt_s: float            # 往返网络时延
    ttft_s: float           # 云侧首 token 时延（排队+prefill）
    decode_tps: float       # 云侧 decode 吞吐
    cost_per_1k_tokens: float
    private_available: bool = True


@dataclass(frozen=True)
class Request:
    name: str
    privacy: int
    input_len: int
    output_len: int
    latency_slo_s: float = 60.0


def device_latency_s(req: Request, dev: DeviceProfile) -> float:
    """端侧端到端时延：prefill + decode；超过节流阈值后对 decode 部分降额。"""
    t_prefill = req.input_len / dev.prefill_tps
    t_decode = req.output_len / dev.decode_tps
    if t_prefill + t_decode > dev.derate_after_s:
        t_decode = t_decode / dev.derate_factor
    return t_prefill + t_decode


def thermal_derated(req: Request, dev: DeviceProfile) -> bool:
    """该请求在端侧是否会触发热节流降额。"""
    return req.input_len / dev.prefill_tps + req.output_len / dev.decode_tps > dev.derate_after_s


def cloud_latency_s(req: Request, cloud: CloudProfile) -> float:
    """云端端到端时延：RTT + 首 token + decode。"""
    return cloud.rtt_s + cloud.ttft_s + req.output_len / cloud.decode_tps


def cloud_cost(req: Request, cloud: CloudProfile) -> float:
    tokens = req.input_len + req.output_len
    return tokens / 1000.0 * cloud.cost_per_1k_tokens


def route(req: Request, dev: DeviceProfile, cloud: CloudProfile) -> dict:
    """路由决策：返回 (decision, device_lat, cloud_lat, reason)。"""
    t_dev = device_latency_s(req, dev)
    can_cloud = req.privacy == PUBLIC or (req.privacy == INTERNAL and cloud.private_available)
    t_cloud = cloud_latency_s(req, cloud) if can_cloud else float("inf")

    if req.privacy == CONFIDENTIAL:
        return {"decision": "device", "device_s": t_dev, "cloud_s": t_cloud,
                "reason": "机密数据，硬约束留在端侧"}
    derate_note = "（触发热节流）" if thermal_derated(req, dev) else ""
    if t_dev <= req.latency_slo_s and (t_cloud == float("inf") or t_dev <= t_cloud):
        return {"decision": "device", "device_s": t_dev, "cloud_s": t_cloud,
                "reason": f"端侧满足 SLO 且不慢于云端{derate_note}"}
    if t_cloud <= req.latency_slo_s:
        which = CLOUD_PRIVATE if req.privacy == INTERNAL else CLOUD_PUBLIC
        why = "端侧超时" if t_dev > req.latency_slo_s else "云端显著更快"
        return {"decision": which, "device_s": t_dev, "cloud_s": t_cloud,
                "reason": f"{why}（端侧 {t_dev:.2f}s vs 云端 {t_cloud:.2f}s）{derate_note}，走云端"}
    return {"decision": "device", "device_s": t_dev, "cloud_s": t_cloud,
            "reason": "两端都不满足 SLO，端侧尽力而为（降级输出长度）"}
