# 9. 最佳实践

把前面几章的知识沉淀成可以落进 SOP 和架构评审的检查清单。

## 9.1 AI 存储架构设计检查清单

### 9.1.1 训练场景

| 检查项 | 建议 |
|---|---|
| checkpoint 目标 | 本地 NVMe 作为热缓冲，异步上传到并行 FS/对象存储 |
| 写入模式 | 大文件顺序写，开启 direct I/O 或合理设置 page cache 回写阈值 |
| 一致性 | 保存完成后写入 manifest/元数据，确认可读后再删除旧 checkpoint |
| 容错 | 至少保留最近 2-3 个可用 checkpoint |
| 频率 | 根据硬件故障率和存储带宽权衡，通常 5-15 分钟 |

### 9.1.2 推理场景

| 检查项 | 建议 |
|---|---|
| 模型权重 | 使用对象存储 + Init Container 或共享 PVC |
| 缓存 | 节点级本地缓存，热门模型预加载 |
| 冷启动 | 设置合理的 readiness probe 和 HPA 预热策略 |
| 多版本 | 对象存储版本控制 + 路由切换 |

### 9.1.3 Kubernetes 存储

| 检查项 | 建议 |
|---|---|
| StorageClass | 按用途分多种：fast-local、shared-fs、object、backup |
| VolumeBindingMode | 本地盘用 `WaitForFirstConsumer` |
| AccessMode | 共享数据集用 RWX，checkpoint 用 RWO |
| CSI driver | 选择经过生产验证的驱动，监控其 pod 健康 |

## 9.2 性能基准

### 9.2.1 本地存储基准

```bash
# 顺序写吞吐
fio --name=seq-write --directory=/data --rw=write --bs=1M --size=10G --numjobs=8 --ioengine=libaio --direct=1

# 随机读 IOPS
fio --name=rand-read --directory=/data --rw=randread --bs=4k --size=10G --numjobs=8 --ioengine=libaio --direct=1
```

### 9.2.2 对象存储基准

```bash
# s3bench / warp / aws s3 cp 批量测试
warp mixed --duration=5m --obj.size=10MiB --bucket=benchmark --access-key=$KEY --secret-key=$SECRET
```

验收标准：

- 本地 NVMe 顺序写 ≥ 线速 70%；
- 并行文件系统单客户端顺序读 ≥ 10 GB/s；
- 对象存储大对象并发上传 ≥ 目标带宽 80%。

## 9.3 可观测性指标体系

| 层级 | 指标 | 工具 |
|---|---|---|
| 设备层 | IOPS、吞吐、延迟、利用率 | `iostat`、`fio` |
| 文件系统层 | 元数据操作、缓存命中率 | `df`、`mount`、专用工具 |
| 并行 FS 层 | MDS/OSS 负载、客户端 I/O | Lustre/WEKA 监控 |
| 对象存储层 | QPS、延迟、错误率、流量 | 云监控、Prometheus |
| K8s 层 | PVC 绑定率、CSI 操作延迟、attach 失败率 | kube-state-metrics |
| 应用层 | checkpoint 耗时、模型加载时间 | 训练框架/服务指标 |

## 9.4 安全最佳实践

| 场景 | 实践 |
|---|---|
| 数据加密 | 静态加密（KMS）+ 传输加密（TLS） |
| 访问控制 | bucket policy、IAM role、K8s RBAC |
| 版本控制 | 防止误删，支持回滚 |
| 审计 | 记录对象访问、删除、策略变更 |
| 合规 | 敏感数据按 SOC2/HIPAA/GDPR 要求存储 |

## 9.5 常见误区

| 误区 | 正确做法 |
|---|---|
| 把对象存储当文件系统用 | 对象存储适合大对象，海量小文件应合并或使用文件系统 |
| 忽视 metadata 开销 | 海量小对象 LIST/HEAD 开销巨大，需要预聚合或索引 |
| checkpoint 只存一份 | 至少保留多份，异地/跨可用区备份 |
| 所有数据都用最高性能存储 | 按访问频率分层，冷热分离 |

## 9.6 一句话总结

**好的 AI 存储设计，不是买最快的盘，而是让数据在正确的时间出现在正确的位置，并持续度量成本和性能。**
