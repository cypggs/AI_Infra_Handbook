# 5. 核心模块

存储系统由多个功能模块组成。本章从本地存储、网络存储、对象存储、并行文件系统、K8s 存储、缓存分层、数据管理和可观测工具八个维度展开。

## 5.1 本地存储

### HDD / SSD / NVMe

| 介质 | 延迟 | 吞吐 | 寿命/耐久性 | 适用 |
|---|---|---|---|---|
| HDD | 数 ms | 100-200 MB/s | 高（大容量） | 冷存、归档 |
| SATA SSD | 百 μs | 500 MB/s | 中 | 普通应用 |
| NVMe SSD（TLC） | 十 μs | 数 GB/s | 中-高 | checkpoint、缓存 |
| NVMe SSD（QLC 大容量） | 十 μs | 顺序读约 7-14 GB/s | 随机写弱 | 数据湖、温数据（Solidigm D5-P5336 122TB；Micron 6600 ION 245TB，2026-05 出货） |

> QLC（四层单元）NAND 用容量换耐久性：2026 年 5 月 Micron 245TB 6600 ION（G9 QLC、PCIe Gen5）已开始出货，把单盘容量从 2025 年的 122TB 级又翻了一倍；顺序读性能接近 TLC（约 14 GB/s），但随机写 IOPS 低一个数量级。厂商定位非常明确：AI 数据湖与"写一次读多次"的训练数据集——1 EB 容量下比 HDD 方案少 82% 机架、功耗约为一半。同期 Samsung BM1743 做到 122.88TB（E3.S），Kioxia、SK hynix 也披露了 245TB 级产品，SanDisk 路线图指向 2026 年 256TB、2027 年 512TB（来源：[Micron 6600 ION 出货公告](https://www.nasdaq.com/press-release/industry-leading-245tb-micron-6600-ion-data-center-ssd-now-shipping-2026-05-05)、[Tom's Hardware 报道](https://www.tomshardware.com/pc-components/ssds/microns-industry-first-pci-6-0-ssd-promises-sequential-reads-up-to-28-000-mb-s-245-tb-ssd-also-coming-for-those-who-need-capacity-more-than-cutting-edge-speed)）。旧数据点参考：122TB 级 QLC 的 4K 随机读约 90 万 IOPS vs 随机写仅约 1.9 万（[StorageReview 评测](https://www.storagereview.com/review/solidigm-122-88tb-d5-p5336-review-high-capacity-storage-meets-operational-efficiency)）。

### RAID

RAID 通过多块磁盘组合提高性能或可靠性：

| RAID 级别 | 特点 | 存储效率 | AI 场景 |
|---|---|---|---|
| RAID 0 | 条带化，性能最高 | 100% | 临时数据，不关键 |
| RAID 1 | 镜像，可靠性高 | 50% | 小规模关键元数据 |
| RAID 5/6 | 条带 + 校验 | 67-80% | 通用文件服务器 |
| RAID 10 | 镜像 + 条带 | 50% | 高并发读写 |

### 文件系统选型

| 文件系统 | 特点 | AI 场景 |
|---|---|---|
| ext4 | 稳定、通用 | 根分区、普通数据 |
| xfs | 大文件、高并发 I/O 性能好 | 大数据集、checkpoint |
| btrfs | 快照、压缩、校验和 | 实验环境 |
| ZFS | 高级数据保护、压缩、去重 | 小型 NAS/工作站 |

## 5.2 网络存储

### NFS

- 协议简单，易于共享；
- 单点性能受限，元数据操作可能成为瓶颈；
- 适合小团队共享数据集，不适合大规模训练。

### iSCSI / SAN

- 提供块设备，适合数据库等需要裸设备的应用；
- 需要专用网络或 VLAN 隔离；
- AI 训练中较少直接使用。

## 5.3 对象存储

### S3 API 核心操作

```text
PUT    /bucket/key       # 上传对象
GET    /bucket/key       # 下载对象
DELETE /bucket/key       # 删除对象
LIST   /bucket?prefix=   # 列出对象
HEAD   /bucket/key       # 获取元数据
```

### multipart 上传

大文件拆分成多个 part 并发上传，最后合并：

```mermaid
flowchart LR
    A[大文件] -- 分片 --> B[part 1]
    A --> C[part 2]
    A --> D[part N]
    B -- 并发上传 --> E[对象存储]
    C --> E
    D --> E
    E -- CompleteMultipartUpload --> F[合并成完整对象]
```

### 生命周期管理

| 策略 | 作用 |
|---|---|
| 转换存储类型 | 30 天后转 IA，90 天后转归档 |
| 过期删除 | 旧 checkpoint 自动清理 |
| 版本控制 | 保留历史版本，支持回滚 |

### 常见产品

- **AWS S3 / GCS / Azure Blob**：托管对象存储；
- **MinIO**：兼容 S3 的开源对象存储；
- **Ceph RADOS**：分布式对象存储，支持块/文件/对象；
- **S3 Express One Zone**：低延迟对象存储（目录桶），ms 级延迟，适合高吞吐 AI 工作负载；
- **S3 Vectors**：2025-12 GA 的原生向量检索，向量直接存在对象存储里做 ANN 查询，服务 RAG 场景（每索引 20 亿向量、每 bucket 1 万个索引）。

## 5.4 并行文件系统

并行文件系统允许多个客户端同时访问同一命名空间，适合多机训练。

| 产品 | 特点 | 适用 |
|---|---|---|
| Lustre | 开源、HPC 生态成熟、超算 TOP500 最常用；2.17（2025-12 GA）带来 Hybrid IO 大 I/O 自动优化、动态 LNet NID 配置、动态 nodemap 多租户，2.18 规划文件级纠删码与客户端压缩 | 大规模训练 |
| GPFS / IBM Storage Scale | IBM 商用，5.2.x 系列集成 NVIDIA GPUDirect Storage，通过 DGX BasePOD 认证 | 企业级 |
| BeeGFS | 开源、易部署，2026 稳定版 8.3.x | 中小型集群 |
| WEKA | 高性能 NVMe 原生；2026-07 发布 WEKApod 3 + NeuralMesh 6：单柜 1.1 EB 有效容量、10.2 TB/s 吞吐、2.1 亿 IOPS，面向 agentic 推理 KV Cache 卸载 | 低延迟 AI 工作负载 |
| Google Managed Lustre | 托管 Lustre（基于 DDN EXAScaler），2026-04 单实例 10 TB/s、checkpoint 快 2.6 倍 | 云上大规模训练/推理 |
| 3FS (Fire-Flyer) | 2025-02 DeepSeek 开源；NVMe+RDMA 全带宽利用、几乎放弃读缓存、元数据基于 FoundationDB、CRAQ 强一致 | AI 训练/推理，180 节点聚合读 6.6 TiB/s |

### 3FS 架构要点

```mermaid
flowchart LR
    A[客户端 FUSE / USRBIO] --> B[无状态元数据服务<br/> backed by FoundationDB]
    A -- 数据面 --> C[Chunk 引擎<br/>千级 SSD 聚合]
    C -- CRAQ 链复制 --> C
```

- **存算分离的 Chunk 引擎**：把集群里所有 SSD 聚合成一个资源池，应用以"位置无关"的方式访问任意一块盘；
- **无状态元数据服务**：状态全部放在 FoundationDB 这类事务型 KV 存储里，元数据服务本身可以水平扩展和快速 failover；
- **CRAQ（Chain Replication with Apportioned Queries）**：链式复制的改进版，读可以从链上任意节点进行，在保证强一致的同时提高读并发；
- **KVCache 支持**：单节点 KV 查找读带宽可达 40+ GiB/s，直接把推理 KV Cache 存在文件系统里（来源：[DeepSeek 3FS](https://github.com/deepseek-ai/3fs)）。

### 传统并行文件系统关键组件

```mermaid
flowchart LR
    A[客户端] --> B[MDS 元数据服务器]
    A --> C[OSS 对象存储服务器]
    B -- 管理命名空间 --> C
```

- **MDS（Metadata Server）**：管理文件元数据；
- **OSS（Object Storage Server）**：管理实际数据块。

## 5.5 Kubernetes 存储

### PV / PVC / StorageClass

| 资源 | 角色 |
|---|---|
| StorageClass | 存储模板，定义 provisioner、参数、回收策略 |
| PVC | 应用对存储的请求（大小、访问模式） |
| PV | 实际分配的存储卷 |

### CSI driver 示例

- AWS EBS CSI driver
- Ceph RBD CSI driver
- Lustre CSI driver
- NFS CSI driver
- Local PV static provisioner
- 裸金属本地盘：csi-lvm、DirectPV、TopoLVM、OpenEBS Local LVM

> 协议进展：CSI spec v1.13.0（2026-07-27）新增了 VolumeHealth（卷健康度）RPC 和快照拓扑（Snapshot Topology，均为 alpha）；面向对象存储的 COSI（Container Object Storage Interface）到 2026 年仍未 GA，生产上仍以各厂商自研 provisioner/sidecar 为主（来源：[CSI Spec Releases](https://github.com/container-storage-interface/spec/releases)）。

### K8s 存储选型

| 场景 | 推荐 |
|---|---|
| 训练 checkpoint | Local SSD + CSI，或并行 FS PVC |
| 模型权重 | S3 + storage-initializer，或 ReadOnlyMany PVC |
| 数据库/状态服务 | EBS/RBD PVC + StatefulSet |
| 共享数据集 | NFS/EFS/并行 FS PVC |

## 5.6 缓存与分层

### 典型缓存层

| 层 | 速度 | 容量 | 例子 |
|---|---|---|---|
| GPU 显存 | 最快 | 最小 | HBM |
| 本地 NVMe | 快 | 小 | 节点本地 SSD |
| 并行文件系统 | 中 | 中 | Lustre/WEKA |
| 对象存储 | 慢 | 极大 | S3/GCS |

### 缓存策略

| 策略 | 说明 |
|---|---|
| Read-through | 读取未命中时自动从下层加载 |
| Write-through | 写入时同时写缓存和下层 |
| Write-back | 写入时只写缓存，异步回写下层 |
| LRU | 最近最少使用淘汰 |

### 常见缓存产品

- **Alluxio**：内存/SSD 缓存层，挂载在对象存储之上；企业版 3.5 引入 CACHE_ONLY、3.6 引入 ASYNC 两种 checkpoint 写模式（checkpoint 只写缓存、后台异步落盘），MLPerf Storage v3.0 上跑出 147 GiB/s 的 Llama 3 405B checkpoint 写入带宽；
- **JuiceFS**：基于对象存储的 POSIX 文件系统，带本地缓存；1.4（2026-07-14 GA，新 LTS）把存储类别做进文件语义——支持文件/目录级分层存储（目录级设置可被子目录继承）、批量删除/批量克隆（数据集版本管理）、元数据 changelog 与断点续传的 `juicefs sync`；企业版 5.x 引入 RDMA 并支持单卷 5000 亿+ 文件（来源：[JuiceFS 1.4 Release Notes](https://juicefs.com/en/blog/release-notes/juicefs-1-4-tiered-storage-faster-metadata)）；
- **FUSE**：用户态文件系统，常用于把对象存储挂载为本地路径；
- **Mooncake Store / LMCache**：2025 年后兴起的**推理 KV Cache 池**，缓存单元不是文件而是 KV 块，配合 RDMA 在 GPU 实例间共享，把跨实例前缀复用率从个位数百分比提升到 90%+；2026-05 vLLM v0.31 内置 Mooncake Store connector，12 张 GB200 实测吞吐 3.8 倍、P50 TTFT 降至 1/46，命中率在 Codex agentic 轨迹上达 92.2%（来源：[vLLM Blog: Mooncake Store](https://vllm-project.github.io/blog/2026-05-06-mooncake-store/)）；
- **CXL 内存池**：XConn/MemVerge、KIOXIA XL1、Liqid 等 2025-2026 年的 CXL 方案把退役 DDR4/DDR5 聚合成 20-100 TiB 级共享内存池，作为 KV Cache 的"温层"（延迟约 460-500ns，远高于 SSD），Azure 于 2025-11 推出首批 CXL 云实例；CXL 4.0 规范 2025-11 发布（128 GT/s），2026 年生产部署以 CXL 2.0/3.x 扩展与早期池化为主，机架级池化预计 2027 年后普及（来源：[OCP 2025 CXL KV Cache](https://www.storagenewsletter.com/2025/10/16/ocp-global-summit-2025-xconn-technologies-and-memverge-demonstrate-cxl-memory-pool-for-kv-cache/)、[Synopsys CXL 4.0 解读](https://www.synopsys.com/blogs/chip-design/cxl-4-ip-solution-ai-memory-connectivity.html)）。

## 5.7 数据管理

| 功能 | 作用 | AI 场景 |
|---|---|---|
| 快照 | 某一时刻的只读副本 | 保存训练中间状态 |
| 备份 | 跨地域/跨介质复制 | 灾难恢复 |
| 迁移 | 数据在不同存储间移动 | 冷热分层 |
| 校验和 | 检测数据损坏 | checkpoint 完整性 |

## 5.8 可观测工具

| 工具 | 用途 |
|---|---|
| `iostat` | 磁盘 I/O 利用率、IOPS、吞吐 |
| `fio` | 存储性能基准测试 |
| `dd` | 简单顺序读写测试 |
| `s3cmd` / `aws s3` | 对象存储操作与统计 |
| `lustre stats` / `weka fs` | 并行文件系统监控 |
| Prometheus + Grafana | 持续监控存储指标 |

## 5.9 一句话总结

**存储系统的模块选择，本质上是根据 AI 工作负载的访问模式（读/写、顺序/随机、大/小文件、共享/独占）匹配最合适的介质和协议。**
