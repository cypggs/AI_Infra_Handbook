# 9. 最佳实践

> 一句话理解：**AI 集群网络的最佳实践可以浓缩成三张表——设计检查清单（建之前）、参数模板（调的时候）、运行纪律（跑起来之后）；每张表都对应第 8 章排障 playbook 里的一类事故。**

## 9.1 Fabric 设计检查清单（建之前）

### 拓扑与带宽

- [ ] 用流量矩阵（第 7 章 Mini Demo 场景 3 的方法）算过每 step 字节数，确认 fabric 带宽预算 ≥ 1.3× 峰值需求。
- [ ] 训练 fabric 为 1:1 无阻塞（full bisection），收敛比只留给前端/存储网。
- [ ] 多轨（每 GPU 一块 NIC）成对设计：NIC i ↔ GPU i 的 PCIe 拓扑经 `nvidia-smi topo -m` 验证在同 PCIe switch/NUMA 下。
- [ ] MoE 训练占比高时采用 rail-optimized/双平面设计，并为 all-to-all 预留多路径能力（自适应路由或 UEC spraying）。
- [ ] 故障域：双 ToR 或双 plane；单点失效只造成带宽降级，不造成训练中断。

### 协议与机制

- [ ] 明确无损路线：IB（credit）或 RoCE（PFC+ECN）或丢包容忍（Falcon/UEC 思路），并写入架构决策记录（ADR）。
- [ ] RoCE 路线：PFC 只开在最必要的一个无损队列（DCB 逐跳一致性），并配置死锁检测与 watchdog。
- [ ] ECN/DCQCN 参数按 RTT 与缓冲尺寸整网计算，而不是逐台手调（模板见 9.2）。
- [ ] IB 路线：SHARP 阈值策略明确（消息小于阈值不卸载），SM 主备部署。

### 辅网与运维

- [ ] 前端/存储/带外三网物理隔离，训练 NIC 不承载任何业务流量。
- [ ] checkpoint 带宽按"全集群同时写、分钟级完成"单独预算。
- [ ] 遥测覆盖：FEC/CRC、PFC pause、ECN 标记率、per-flow 吞吐、nccl-tests 历史曲线，全部进统一监控。
- [ ] 布线即数据：链路两端标签与配置管理库（IPAM/DCIM）自动对账，扩缩容后自动 diff。

## 9.2 参数模板（调的时候）

### RoCE/DCQCN 参考起点（按 400G、RTT 约 5–10µs 量级 fabric 的经验值，**必须实测微调**）

| 参数 | 起点 | 说明 |
|---|---|---|
| ECN Kmin / Kmax | 约 80KB / 约 1.2MB（按缓冲 1–2% / 15–25% 推算） | 队列低于 Kmin 不打标，超 Kmax 全标 |
| DCQCN alpha 平滑 g | 1/256 | 标准值 |
| 降速幅度 | alpha/2 乘性降 | 每 CNP 一次 |
| 加性升速 | 每定时器周期 +1–5% 线速 | 宁慢勿快，防振荡 |
| PFC 触发阈值 | 高于 Kmax 且留足 headroom | 保证 ECN 先动作、PFC 是最后手段 |

调参顺序：先把 PFC 阈值放到"几乎不触发"，再调 ECN 的 K 值控制队列水位，最后调 DCQCN 的升降速速率匹配流量突发。每一步用 nccl-tests + 生产流量回放验证。

### NCCL 常用环境变量（生产调优子集）

| 变量 | 用途 |
|---|---|
| `NCCL_IB_HCA` / `NCCL_IB_GID_INDEX` | 指定用哪些网卡 / RoCE v2 的 GID 选择 |
| `NCCL_IB_QPS_PER_CONNECTION` | 每连接 QP 数，多 rail 下增大可提升并行度 |
| `NCCL_NET_GDR_LEVEL` | GPUDirect RDMA 的启用级别（跨不跨 PCIe switch） |
| `NCCL_ALGO` / `NCCL_PROTO` | 强制 ring/tree 与 Simple/LL/LL128 协议（排障对比用） |
| `NCCL_IB_TIMEOUT` / `NCCL_IB_RETRY_CNT` | QP 超时与重试（大集群常见调大） |
| `NCCL_SHARP_DISABLE` / `NCCL_COLLNET_ENABLE` | SHARP 开关（灰度与逃生通道） |
| `NCCL_DEBUG=INFO` + `NCCL_DEBUG_SUBSYS=INIT,GRAPH` | 初始化与拓扑调试日志 |

### 验收基线（交付时固化）

- 单轨 all_reduce busbw ≥ 标称 90%；整机 ≥ 85%。
- 全集群 10% 抽样主机对 ≥ 80%。
- 72 小时稳定性：无 NCCL timeout、PFC pause 占比小于万分之一。

## 9.3 运行纪律（跑起来之后）

1. **版本三件套一起升**：驱动 + 固件 + NCCL。拓扑识别（第 6 章 NCCL `src/graph/`）依赖三者配套，混用是大集群性能劣化的头号原因。
2. **一次只改一个变量**：网络调参与实验科学同规则，留对照组。
3. **灰度 + 逃生通道**：SHARP、自适应路由、新固件先小集群灰度；每个 job 保留降级运行路径（非 SHARP、单 plane、低版本协议）。
4. **慢源先查网络再查 GPU**：step 抖动先拉 PFC pause/ECN 曲线与 per-flow 分布，再看 GPU 利用率——统计上网络灰度故障多于 GPU 隐性故障，且更容易修复。
5. **把遥测当训练的一部分**：P99 通信时间、每 rail 带宽达标率进入 [AI SRE](/07-ai-sre/) 的 SLI 看板，与 checkpoint 恢复时间（MTTR）一起看——网络指标的最终意义是有效训练时间占比。
6. **容量水位线**：任一 rail 的 15 分钟均值超过 70% 即触发扩容评估；incast 场景看 P99 而不是均值（第 2 章的尾部延迟数学）。
7. **变更窗口避开训练高峰**：fabric 变更（固件、路由策略）尽量在 job 间隙执行；必须在线做的，先确认 gang 调度能保证受影响 job 整体重调度。
8. **演练故障注入**：每月随机断链/断 ToR 演练一次，验证降级行为与告警链路（不演练的预案等于没有预案）。

## 9.4 一句话总结

最佳实践的本质是**把"调网络"从手艺变成流程**：设计阶段用清单挡住结构性错误，调参阶段用模板和基线挡住随机性错误，运行阶段用纪律和演练挡住长尾错误——剩下的才算真问题。

**参考来源**

- [NVIDIA NCCL 环境变量文档](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/envs.html)
- [DCQCN（SIGCOMM'15）](https://www.microsoft.com/en-us/research/publication/dcqcn-congestion-control-for-large-scale-rdma-deployments/)
- [NVIDIA Quantum-X800 集群文档](https://networking-docs.nvidia.com/nvidia-quantum-x800-xdr-clusters)（SHARP 配置与 IB 参数）
