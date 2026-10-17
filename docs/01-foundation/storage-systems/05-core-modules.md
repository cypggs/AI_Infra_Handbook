# 5. 核心模块

存储系统由多个功能模块组成。本章从本地存储、网络存储、对象存储、并行文件系统、K8s 存储、缓存分层、数据管理和可观测工具八个维度展开。

## 5.1 本地存储

### HDD / SSD / NVMe

| 介质 | 延迟 | 吞吐 | 寿命/耐久性 | 适用 |
|---|---|---|---|---|
| HDD | 数 ms | 100-200 MB/s | 高（大容量） | 冷存、归档 |
| SATA SSD | 百 μs | 500 MB/s | 中 | 普通应用 |
| NVMe SSD（TLC） | 十 μs | 数 GB/s | 中-高 | checkpoint、缓存 |
| NVMe SSD（QLC 大容量） | 十 μs | 顺序读约 7 GB/s、写约 3 GB/s | 随机写弱 | 数据湖、温数据（如 Solidigm D5-P5336 122TB） |

> QLC（四层单元）NAND 用容量换耐久性：单盘可达 122TB（ roadmap 指向 245TB 级），顺序读性能接近 TLC，但随机写 IOPS 低一个数量级（4K 随机读约 90 万 IOPS vs 随机写仅约 1.9 万）。它最适合 AI 数据湖、训练数据集这类"写入一次、读取多次"的场景，用单盘 4PB/U 的密度和比 HDD 低得多的功耗重塑温层（来源：[Solidigm D5-P5336](https://www.solidigm.com/products/data-center/d5/p5336.html)、[StorageReview 评测](https://www.storagereview.com/review/solidigm-122-88tb-d5-p5336-review-high-capacity-storage-meets-operational-efficiency)）。

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
| Lustre | 开源、HPC 生态成熟、高吞吐 | 大规模训练 |
| GPFS / Spectrum Scale | IBM 商用，强一致性 | 企业级 |
| BeeGFS | 开源、易部署 | 中小型集群 |
| WEKA | 高性能 NVMe 原生 | 低延迟 AI 工作负载 |
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

- **Alluxio**：内存/SSD 缓存层，挂载在对象存储之上；
- **JuiceFS**：基于对象存储的 POSIX 文件系统，带本地缓存；
- **FUSE**：用户态文件系统，常用于把对象存储挂载为本地路径；
- **Mooncake Store / LMCache**：2025 年后兴起的**推理 KV Cache 池**，缓存单元不是文件而是 KV 块，配合 RDMA 在 GPU 实例间共享，把跨实例前缀复用率从个位数百分比提升到 90%+；
- **CXL 内存池**：XConn/MemVerge、KIOXIA XL1、Liqid 等 2025-2026 年的 CXL 方案把退役 DDR4/DDR5 聚合成 20-100 TiB 级共享内存池，作为 KV Cache 的"温层"（延迟约 460-500ns，远高于 SSD），Azure 于 2025-11 推出首批 CXL 云实例（来源：[OCP 2025 CXL KV Cache](https://www.storagenewsletter.com/2025/10/16/ocp-global-summit-2025-xconn-technologies-and-memverge-demonstrate-cxl-memory-pool-for-kv-cache/)）。

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
