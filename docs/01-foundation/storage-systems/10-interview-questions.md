# 10. 面试题

面试中存储相关的问题，通常从基础协议开始，逐渐深入到 AI Infra 场景。本章按初、中、高级整理。

## 10.1 初级

### 1. 块存储、文件存储、对象存储有什么区别？

**参考答案**：块存储暴露原始块地址，适合数据库和文件系统底层；文件存储提供 POSIX 路径和目录树，适合通用应用；对象存储用 bucket+key+元数据，HTTP API，适合海量非结构化数据。

### 2. 什么是 RAID？RAID 0、1、5、10 各有什么特点？

**参考答案**：RAID 0 条带化性能高但无冗余；RAID 1 镜像可靠性高但容量减半；RAID 5/6 用校验信息兼顾容量和冗余；RAID 10 是镜像+条带，适合高并发读写。

### 3. 什么是 POSIX？对象存储为什么不完全兼容 POSIX？

**参考答案**：POSIX 是类 Unix 文件系统接口标准（open/read/write/rename 等）。对象存储的扁平命名空间、无追加写、无原子 rename 等特性与 POSIX 语义冲突，因此通常只提供 S3 API。

### 4. 解释一下对象存储的 multipart 上传。

**参考答案**：大文件被分成多个 part 并发上传，每个 part 有独立 ETag，最后通过 CompleteMultipartUpload 合并成完整对象。优点是提高并发和容错性。

### 5. 什么是最终一致性？对象存储通常是什么一致性？

**参考答案**：最终一致性指写入后一段时间内并非所有读取都返回最新值。现代对象存储（S3、GCS 等）通常提供强一致性。

## 10.2 中级

### 6. 复制和纠删码有什么区别？AI 场景如何选择？

**参考答案**：复制保存多份完整数据，简单但利用率低；纠删码切分数据并生成校验块，利用率高但计算和恢复开销大。热数据/关键元数据常用复制，冷数据/大容量对象存储常用纠删码。

### 7. 什么是 CAP 定理？存储系统通常怎么选择？

**参考答案**：CAP 指一致性、可用性、分区容忍性，最多同时满足两个。分布式存储通常选 CP 或 AP。AI checkpoint 等场景优先 CP。

### 8. 解释 Kubernetes 中 PV、PVC、StorageClass 的关系。

**参考答案**：StorageClass 是存储模板；PVC 是应用对存储的请求；PV 是实际分配的卷。PVC 绑定到满足条件的 PV，由 StorageClass 指定的 provisioner 动态创建。

### 9. 什么是 CSI？它解决了什么问题？

**参考答案**：CSI 是 Container Storage Interface，标准化容器与存储系统的集成。它让存储厂商可以独立开发 driver，无需修改 Kubernetes 核心代码。

### 10. 并行文件系统和 NFS 有什么区别？

**参考答案**：并行文件系统（Lustre/GPFS/WEKA）通过多个数据服务器并行提供高吞吐共享访问；NFS 基于单服务器架构，容易成为瓶颈。

### 11. 为什么 AI 训练 checkpoint 通常先写本地 NVMe？

**参考答案**：本地 NVMe 延迟低、吞吐高，可以减少训练阻塞时间；之后再异步上传到对象存储或并行文件系统做持久化。

### 12. 对象存储的生命周期管理有什么用？

**参考答案**：自动将旧对象转换到更便宜的存储类型（如 IA、归档）或删除，降低成本。

## 10.3 高级

### 13. 设计一个万卡 AI 训练集群的存储架构。

**参考答案要点**：
- 每个计算节点配置本地 NVMe 作为 checkpoint 热缓冲；
- 使用并行文件系统（Lustre/WEKA）承载训练数据集和共享模型仓库；
- 对象存储用于长期归档、artifact 和日志；
- 异步 checkpoint 机制，本地写入后后台上传到对象存储；
- 热/温/冷分层，配合生命周期管理降低成本；
- 监控 checkpoint 耗时、存储带宽、IOPS、容量。

### 14. PyTorch Distributed Checkpoint 相比 `torch.save` 有什么优势？

**参考答案要点**：
- 每个 rank 独立写自己的 shard，消除单文件竞争；
- `.metadata` 驱动加载，支持不同并行策略间恢复；
- 使用 fsspec 统一本地和对象存储后端；
- 支持异步保存和分片优化。

### 15. LLM 推理服务冷启动慢，如何从存储角度优化？

**参考答案要点**：
- 节点级本地缓存共享已下载权重；
- 使用 JuiceFS/Alluxio 等带缓存的 POSIX 层；
- 热门模型预加载到节点镜像；
- 使用对象存储的 multipart/并发下载；
- 共享 ReadOnlyMany PVC。

### 16. 比较 Local PV 和 EBS/RBD 在 AI 训练中的 trade-off。

**参考答案**：Local PV 延迟低、吞吐高，但 Pod 绑定节点、数据不随 Pod 迁移；EBS/RBD 可以跨节点迁移，但网络延迟和带宽受限。checkpoint 等临时高吞吐数据适合 Local PV，状态服务适合 EBS/RBD。

### 17. 海量小对象对对象存储有什么问题？如何解决？

**参考答案**：LIST/HEAD 元数据开销大、请求成本高。解决方案：合并小对象（如 parquet、tar）、使用前缀索引、选择高元数据性能的对象存储、使用生命周期规则。

### 18. 如何保证 checkpoint 不丢且可恢复？

**参考答案**：
- 写入完成后显式 fsync/close；
- 保存 manifest 记录所有 shard；
- 加载前校验 checksum；
- 保留多个历史版本；
- 异地/跨可用区备份。

## 10.4 场景设计题

### 19. 设计一个多区域 LLM 推理服务的模型分发方案。

**参考答案要点**：
- 模型权重放在中心对象存储；
- 每个区域部署带缓存的本地对象存储/文件系统；
- Pod 启动时优先从区域缓存加载；
- 新版本发布时预热到各区域；
- 监控加载延迟和缓存命中率。

### 20. 如何在 Kubernetes 上为训练 Job 提供高吞吐本地 NVMe checkpoint？

**参考答案要点**：
- 使用 Local Static Provisioner 管理节点本地 NVMe；
- StorageClass 设置 `volumeBindingMode: WaitForFirstConsumer`；
- Pod 声明 Local PV，训练代码写入本地路径；
- 异步 sidecar 或训练框架将 checkpoint 上传到对象存储；
- Job 完成后清理或保留关键 checkpoint。

## 10.5 2025-2026 前沿题

### 21. DeepSeek 3FS 为什么"几乎不做读缓存"？它的架构有什么特点？

**参考答案要点**：
- AI 训练数据每个 epoch 只读一遍，传统读缓存命中率趋近于零，缓存反而引入一致性和内存开销；
- 架构：存算分离的 Chunk 引擎聚合千级 NVMe SSD + RDMA 网络的裸带宽；无状态元数据服务基于 FoundationDB；CRAQ 链复制保证强一致；
- 效果：180 节点集群聚合读带宽 6.6 TiB/s，单节点 KV Cache 查找读带宽 40+ GiB/s（来源：[3FS](https://github.com/deepseek-ai/3fs)）。

### 22. 推理 PD 分离架构下，KV Cache 存储层要解决什么问题？

**参考答案要点**：
- Prefill 与 Decode 在不同 GPU 上执行，KV Cache 需要跨节点高速传输；
- 用分布式 KV Cache 池（Mooncake Store：CPU DRAM + SSD + RDMA）按块寻址、跨实例复用前缀；
- 用 RDMA/Transfer Engine 做 GPU 显存直拷；分层驻留（DRAM 热、SSD 温）；
- 更进一步的 CXL 内存池把 KV 温层从 SSD 提到内存总线级，TTFT 可再降一个数量级；
- 实测：agentic 负载跨实例命中率从约 1.7% 提升到约 92%（来源：[Mooncake](https://github.com/kvcache-ai/Mooncake/)）。

### 23. PyTorch 异步 checkpoint 的实现原理是什么？为什么还要"进程化"？

**参考答案要点**：
- 两阶段：阶段一 GPU→CPU 页锁定内存（训练只在此阻塞约 1 秒），阶段二后台写盘不影响训练；
- 线程化后台写盘会与训练线程争抢 Python GIL，造成 checkpoint 结束后 TPS 持续下跌，改成独立进程后消除；
- 缓存 save plan 避免每次保存都重复全局 collective（planner 只需第一次计算）；
- 实测 1856 H200 / Llama3-70B：后台处理 436s→67s，约 6.5 倍提升（来源：[PyTorch Blog](https://pytorch.org/blog/6x-faster-async-checkpointing/)）。

### 24. CXL 内存扩展会给 AI 存储层级带来什么变化？

**参考答案要点**：
- 在 GPU HBM 与 NVMe SSD 之间新增"可池化内存层"，延迟约 500ns 级，带宽 64-128 GB/s；
- 杀手级场景是推理 KV Cache 温层：比 SSD 快一个数量级、比 HBM 便宜一个数量级，且可跨节点共享；
- 2025-2026 进展：OCP 2025 上 XConn+MemVerge 演示 100 TiB CXL 内存池跑 NVIDIA Dynamo；Azure 2025-11 推出首批 CXL 云实例；CXL 4.0（2025-11）带宽翻倍到 128 GT/s；
- 2026 年现实：生产部署仍以 CXL 2.0/3.x 扩展与早期池化为主，机架级池化预计 2027 年后进入主流；
- 代价：软件栈（内存分层、QoS、故障隔离）还不成熟，生产部署案例少。

### 25. QLC NAND 大容量 SSD 适合 AI 场景的哪些层级？有什么坑？

**参考答案要点**：
- 适合：数据湖、训练数据集、对象存储温层等"写一次读多次"场景；2026-05 Micron 245TB 6600 ION 已出货，1 EB 容量下比 HDD 少 82% 机架、功耗约一半；
- 坑：随机写 IOPS 比 TLC 低约两个数量级，耐久性（DWPD）低，不适合 checkpoint 热缓冲和高频覆写层（来源：[Micron 6600 ION 出货公告](https://www.nasdaq.com/press-release/industry-leading-245tb-micron-6600-ion-data-center-ssd-now-shipping-2026-05-05)）。

### 26. 2026 年对象存储为什么开始"抢"并行文件系统的 checkpoint 场景？

**参考答案要点**：
- 传统短板是延迟和元数据吞吐；S3 Express One Zone 用单可用区目录桶把延迟压到个位数 ms；
- 2026-04 Google Cloud Storage Rapid Bucket 单可用区桶做到 >15 TB/s、2000 万请求/秒、亚毫秒延迟，原生 PyTorch/JAX 集成，官方数据 checkpoint 写快 3.2 倍、恢复快 5 倍；
- 含义：云上中小规模训练可以"对象存储 + 低延迟桶"替代自建并行 FS 来存 checkpoint，成本结构完全不同；超大规模共享数据集场景 Lustre/3FS 仍有优势（来源：[Google Cloud Next '26 Storage Announcements](https://cloud.google.com/blog/products/storage-data-transfer/next26-storage-announcements)）。

### 27. 除了 Mooncake，2026 年推理 KV Cache 存储还有哪些新形态？

**参考答案要点**：
- 框架集成标准化：vLLM v0.31 内置 Mooncake Store connector（GPUDirect RDMA，12 张 GB200 吞吐 3.8 倍、P50 TTFT 降 46 倍），TensorRT-LLM 在 KVCMv2 中内置支持；
- 产品化：WEKApod 3 + NeuralMesh 6（2026-07）单柜 1.1 EB、10.2 TB/s，Augmented Memory Grid 把 KV 卸载到闪存；WEKA × OCI 实测 72 张 H100 长上下文吞吐提升 10 倍；
- 分层下探：CXL 内存池把 KV 温层从 SSD 提到内存总线级，2026 年仍以 CXL 2.0/3.x 为主（来源：[vLLM Blog: Mooncake Store](https://vllm-project.github.io/blog/2026-05-06-mooncake-store/)、[WEKApod 3 发布](https://www.weka.io/news/wekapod-3-densest-ai-storage-memory-system)）。
