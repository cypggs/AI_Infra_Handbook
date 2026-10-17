"""deepseek_case_mini：DeepSeek 训练系统核心机制模拟器（Mini Demo）。

复现 DeepSeek-V3/V3.2 技术报告中最具工程辨识度的四组机制：
  - pipeline：DualPipe 双向流水线 vs 1F1B 的气泡账（Table 2）；
  - fp8：E4M3 细粒度量化 + FP32 分段累加的精度账（§3.3）；
  - ep：专家并行 all-to-all 通信量、节点受限路由与负载不均（§3.2.2）；
  - mla：MLA 低秩 KV 压缩与 DSA 稀疏注意力的伏笔（§2.1.1 / V3.2 §2.1）。

纯 CPU、纯 numpy、确定性（seeded），无需任何 GPU 或 LLM key。
"""
from .ep import (
    EpConfig,
    all_to_all_time,
    combine_bytes_per_gpu,
    dispatch_bytes_per_gpu,
    ep_step_comm_time,
    expert_loads,
    imbalance_factor,
    inter_node_fraction,
    routing_imbalance,
    split_traffic,
)
from .fp8 import (
    E4M3_MAX,
    bf16_reference_gemm,
    bulk_signal_error,
    channel_outlier_indices,
    compute_scales,
    fp8_gemm_simulate,
    make_channel_outlier_matrix,
    quantization_snr,
    quantize_e4m3,
    quantize_tensor_wise,
    quantize_tile_wise,
    relative_error,
)
from .mla import (
    MlaConfig,
    compress_kv,
    kv_cache_bytes_per_token,
    kv_compression_ratio,
    kv_elements_mha,
    kv_elements_mla,
    latent_reconstruction_error,
    lightning_index_scores,
    make_mla_weights,
    reconstruct_heads,
    select_top_k,
    sparse_attention_flops_ratio,
    v3_reference_config,
)
from .pipeline import (
    ScheduleResult,
    ascii_timeline,
    bubble_1f1b,
    bubble_dualpipe,
    bubble_reduction_ratio,
    dualpipe_exposed_comm,
    memory_units,
    pipeline_bubble_ratio,
    simulate_pipeline,
)

__all__ = [
    # pipeline
    "ScheduleResult",
    "ascii_timeline",
    "bubble_1f1b",
    "bubble_dualpipe",
    "bubble_reduction_ratio",
    "dualpipe_exposed_comm",
    "memory_units",
    "pipeline_bubble_ratio",
    "simulate_pipeline",
    # fp8
    "E4M3_MAX",
    "bf16_reference_gemm",
    "bulk_signal_error",
    "channel_outlier_indices",
    "compute_scales",
    "fp8_gemm_simulate",
    "make_channel_outlier_matrix",
    "quantization_snr",
    "quantize_e4m3",
    "quantize_tensor_wise",
    "quantize_tile_wise",
    "relative_error",
    # ep
    "EpConfig",
    "all_to_all_time",
    "combine_bytes_per_gpu",
    "dispatch_bytes_per_gpu",
    "ep_step_comm_time",
    "expert_loads",
    "imbalance_factor",
    "inter_node_fraction",
    "routing_imbalance",
    "split_traffic",
    # mla
    "MlaConfig",
    "compress_kv",
    "kv_cache_bytes_per_token",
    "kv_compression_ratio",
    "kv_elements_mha",
    "kv_elements_mla",
    "latent_reconstruction_error",
    "lightning_index_scores",
    "make_mla_weights",
    "reconstruct_heads",
    "select_top_k",
    "sparse_attention_flops_ratio",
    "v3_reference_config",
]
