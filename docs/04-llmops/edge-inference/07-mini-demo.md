---
title: 7. Mini Demo：六类机制的纯 Python 模拟
---

# 7. Mini Demo：六类机制的纯 Python 模拟

> 一句话理解：用一个只依赖 numpy 的迷你包 `edge_inference_mini`，把第 2 章的三本账变成可执行、可测试的确定性模型——每个场景的输出都与本章数字逐字一致。

## 7.1 运行方式

Mini Demo 位于本主题目录下的 `mini-demo/`（代码路径，非站内页面）：

```bash
cd docs/04-llmops/edge-inference/mini-demo
pip install -e ".[dev]"
pytest tests/ -v      # 84 个确定性测试
python -m edge_inference_mini.demo
```

包内模块与真实系统的对应关系：

| 模块 | 模拟对象 | 对应真实系统 |
|---|---|---|
| `clock.py` | 离散事件伪时钟 | OS 调度器/硬件计时器的可步进抽象 |
| `memory.py` | 带宽受限 decode 模型、KV 容量规划 | llama.cpp/MLX 的带宽账与 KV 预算 |
| `hetero.py` | NPU/GPU/CPU 放置与回退 | ExecuTorch delegate / ggml backend 调度层 |
| `streaming.py` | mmap 缺页、预取窗口、热子集 | llama.cpp mmap + mlock、LLM-in-a-flash |
| `lora.py` | 热切换 vs 合并的内存/时延权衡 | llama.cpp `--lora` / PEFT 多 adapter |
| `speculative.py` | 投机解码/MTP 接受率模型 | llama.cpp draft、GLM/DeepSeek MTP |
| `routing.py` | 隐私分级 + SLO + 热节流路由 | Apple Intelligence 端侧优先/PCC |

## 7.2 场景 1：带宽受限 decode 吞吐模型

模型画像：8B 参数、GQA（32 头/8 KV 头）、68 GB/s 带宽、兑现率 0.85。

```text
=== 场景 1：带宽受限 decode 吞吐模型 ===
模型画像: 8B 参数, GQA(32 头/8 KV头), 带宽 68 GB/s, 利用率 0.85
每 token 需读权重: Q4_K_M = 5.18 GB, FP16 = 16.00 GB
decode 上限: Q4 = 11.15 tok/s, FP16 = 3.61 tok/s (带宽相同, 比值 3.09x)
叠加 MTP(α=0.75, γ=4, draft 成本比 0.15, 加速比 1.91x): Q4+MTP ≈ 21.26 tok/s
```

读法：位宽 4 倍差距只换来 3.09 倍吞吐（量化元数据吃掉约 8%）；MTP 用闲置算力对冲带宽瓶颈，再放大 1.91 倍——两个杠杆相乘，Q4 + MTP ≈ 21.26 tok/s，已是可交互的语速。

## 7.3 场景 2：KV cache 容量与上下文规划

```text
=== 场景 2：KV cache 容量与上下文规划 ===
设备: 8 GiB 统一内存, 保留 0.8 GiB, Q4_K_M 权重 4.83 GiB → KV 预算 2.37 GiB
KV 每 token: FP16 = 131072 B, INT8 = 65536 B, INT4 = 32768 B
最大上下文(fp16 KV):  19,431 tokens
最大上下文(int8 KV):  38,863 tokens
最大上下文(int4 KV):  77,726 tokens
```

读法：GQA 把 KV 头数压到 8，每 token 只要 128 KiB（FP16）；KV 量化两档各翻一倍上下文。端侧「长上下文」不靠模型魔法，靠这张内存会计表。

## 7.4 场景 3：异构算子放置与回退

seq=512 单层 prefill，NPU 优先策略（NPU 只支持 matmul 与 elementwise，softmax/norm 回退 GPU）：

```text
=== 场景 3：异构算子放置与回退（seq=512 单层 prefill）===
算子          设备          计算(us)      传输(us)
qkv_gemm    NPU          572.7         0.0
rope        NPU          123.4         0.0
softmax     GPU          370.1       419.4   (回退自 NPU)
attn_gemm   NPU          195.2         0.0
norm1       GPU          246.7       279.6   (回退自 NPU)
gate_up     NPU         2052.0         0.0
down        NPU         1026.0         0.0
norm2       GPU          246.7       279.6   (回退自 NPU)
单层总时延: 5811.5 us, 回退传输税 978.7 us (16.8%)
```

读法：三个回退算子的传输税占 16.8%——宣传 TOPS 要按算子覆盖率打折的真实写照。FFN 的两个 int8 大矩阵乘在 NPU 上吃掉 3/5 的时间，是 prefill 的绝对主战场。

## 7.5 场景 4：闪存流式加载

5.18 GB 模型文件（316,407 页 × 16 KiB），缺页开销 25 µs/页：

```text
=== 场景 4：闪存流式加载（mmap / 预取 / 热子集）===
模型文件 5.18 GB, 316,407 页 x 16 KiB, 带宽 68 GB/s, 缺页开销 25 us
全量预载(mlock):           0.076 s  (纯带宽项)
按需缺页(无预取):          7.986 s  (缺页项 7.910 s)
预取窗口 32 页:            0.323 s  (缺页项 0.247 s)
只访问 30% 页(热子集):      2.396 s  (读入字节同比例下降)
30% 页 + 预取窗口 32:      0.097 s  (热子集 + readahead)
```

读法：纯按需缺页比纯带宽项慢两个数量级（缺页税 7.910 s）；预取窗口把缺页批处理掉；若一次会话只触达 30% 权重页（稀疏激活），加载成本逼近 0.1 s——「大模型秒开」的账就是这么算出来的。

## 7.6 场景 5：LoRA 热切换 vs 权重合并

rank=16、全 32 层 7 个目标矩阵的 adapter：

```text
=== 场景 5：LoRA 热切换 vs 权重合并 ===
adapter(rank=16, 全 32 层 7 目标): 56.0 MiB
合并副本(全量 delta, fp16):       12.06 GiB
热切换一次: 卸载+加载 ≈ 1727.1 us + 固定开销 250 us = 1977.1 us
内存比(热切换/合并): 0.45% → 端侧 8 GiB 放不下 1 份合并副本,但可同时驻留 42 个 adapter
```

读法：热切换以 0.45% 的内存代价换 2 ms 级的切换时延，是端侧多角色/多租户 adapter 的唯一可行方案；合并方案在端侧连一份副本都放不下。

## 7.7 场景 6：端云混合路由决策

端侧画像：prefill 180 tok/s、decode 13 tok/s、45 s 后热节流降额至 0.7；云端画像：RTT 0.12 s、TTFT 0.35 s、decode 60 tok/s。

```text
=== 场景 6：端云混合路由决策 ===
请求         隐私      端侧(s)    云端(s) 决策             理由
病历摘要       机密      25.38       -- device         机密数据，硬约束留在端侧
闲聊问答       公开       5.10     1.54 public_cloud   端侧超时（端侧 5.10s vs 云端 1.54s），走云端
会议纪要       内部      31.07     4.74 private_cloud  云端显著更快（端侧 31.07s vs 云端 4.74s），走云端
长文续写       公开     112.88    17.54 public_cloud   端侧超时（端侧 112.88s vs 云端 17.54s）（触发热节流），走云端
```

读法：机密请求被隐私约束钉死在端侧（25.38 s 也认）；「长文续写」展示了热节流的威力——不降额约 79 s，降额后 112.88 s，直接改变路由结论。

## 7.8 测试与扩展

`pytest tests/` 含 84 个确定性测试，覆盖每个模块的公式正确性、边界条件（α=1、OOM 预算为零、回退链穷尽等）以及 demo 输出与本文数字的逐字回归。可尝试的扩展练习：

1. 把场景 1 的带宽换成 AI PC（120 GB/s）与 Jetson Orin（204 GB/s），重算三档 tok/s；
2. 在 `hetero.py` 中给 NPU 增加 softmax 支持，观察回退税归零后总时延变化；
3. 在 `routing.py` 中增加「中途升级」决策点：端侧生成 30 s 后允许切云端续写，比较总时延；
4. 用 `speculative.best_gamma` 对 α∈[0.5, 0.9] 扫描最优 γ，画出「接受率-最优步长」关系。

## 7.9 本章小结

六个场景分别对应带宽账、容量账、异构账、加载账、adapter 账与路由账；它们共享同一套「参数显式、解析求解、输出确定」的建模纪律——这正是把端侧系统从玄学变成工程的方法论本身。
