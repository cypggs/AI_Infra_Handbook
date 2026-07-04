# 存储系统 Mini Demo

本目录包含一个 CPU 可运行的存储系统机制模拟器，用于帮助理解 AI Infra 中最常遇到的存储概念。

> **注意**：这是一个教学模拟器，不是真实磁盘、文件系统或对象存储。它用于建立直觉，真实调优需要在真实环境中使用 `fio`、`dd`、`s3cmd`、`rclone`、`torch.save/load` 等工具。

## 模拟内容

| 模块 | 文件 | 模拟的机制 |
|---|---|---|
| 块设备 | `storage_systems_mini/block.py` | 固定大小块、分配位图、坏块标记 |
| Inode 文件系统 | `storage_systems_mini/inode_fs.py` | inode 表、直接块指针、简单目录、创建/读写/删除 |
| 对象存储 | `storage_systems_mini/object_store.py` | bucket、对象元数据、S3-like put/get/list/delete、分片上传、版本控制 |
| 纠删码 | `storage_systems_mini/erasure_coding.py` | XOR 编码：k 个数据块 + 1 个校验块，恢复任意一个丢失块 |
| 分层缓存 | `storage_systems_mini/tiered_cache.py` | hot tier（有限本地容量）+ warm tier（对象存储后端）、LRU 淘汰、读提升、写回 |
| Checkpoint 管理 | `storage_systems_mini/checkpoint.py` | 模型 state dict 切片、cache + 对象存储保存、校验和验证、模拟异步上传 |
| 入口脚本 | `storage_systems_mini/demo.py` | 展示所有模块的运行效果 |

## 安装与运行

```bash
cd docs/01-foundation/storage-systems/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m storage_systems_mini.demo
```

## 与真实存储系统的差异

| 模拟器 | 真实系统 |
|---|---|
| 内存中的字节数组 | 真实 SSD/HDD、NVMe、LBA、FTL |
| 简化 inode 与直接块指针 | 真实 ext4/XFS 的间接块、B-tree、日志、权限、ACL |
| 内存对象存储 | 真实 S3/MinIO/Ceph/OSS，涉及 HTTP、认证、生命周期、多 AZ |
| 简单 XOR 纠删码 | 真实 Reed-Solomon、LRC、局部修复组、多AZ冗余 |
| 两层 LRU 缓存 | 真实 page cache、KV cache、CDN、读写策略、一致性协议 |
| 单线程模拟异步上传 | 真实 PyTorch Checkpoint 的异步保存、分布式 barrier、NCCL |

## 推荐阅读顺序

1. 先阅读本章文档，理解块设备、文件系统、对象存储、纠删码、缓存、Checkpoint 的概念；
2. 运行 `demo.py`，观察模拟输出；
3. 打开源码，看每个机制是怎么被简化模拟的；
4. 回到生产环境，用真实工具验证。
