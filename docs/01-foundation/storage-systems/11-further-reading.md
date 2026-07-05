# 11. 延伸阅读

## 11.1 经典书籍

| 书名 | 作者 | 推荐理由 |
|---|---|---|
| 《Designing Data-Intensive Applications》 | Martin Kleppmann | 数据模型、存储引擎、复制、一致性、事务的系统讲解。 |
| 《The Linux Programming Interface》 | Michael Kerrisk | 文件 I/O、ext4、VFS 等 Linux 存储接口圣经。 |
| 《Cloud Native Storage》 | Alex Chalkias 等 | Kubernetes 存储、CSI、云原生存储实践。 |

## 11.2 关键论文

- GFS / Colossus — Google 分布式文件系统的设计演进。
- Ceph — 统一的分布式存储系统。
- Lustre — 面向 HPC 的并行文件系统。
- Alluxio — 内存/SSD 虚拟分布式存储层。
- JuiceFS — 基于对象存储的 POSIX 文件系统。

## 11.3 官方文档

- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [MinIO Documentation](https://min.io/docs/minio/linux/index.html)
- [Ceph Documentation](https://docs.ceph.com/)
- [Lustre Documentation](https://www.lustre.org/)
- [Kubernetes Storage Concepts](https://kubernetes.io/docs/concepts/storage/)
- [Kubernetes CSI Spec](https://github.com/container-storage-interface/spec)
- [PyTorch Distributed Checkpoint](https://pytorch.org/docs/stable/distributed.checkpoint.html)
- [fsspec Documentation](https://filesystem-spec.readthedocs.io/)
- [Google Orbax / Zarr3](https://orbax.readthedocs.io/)

## 11.4 本手册相关主题

- [Linux 系统与性能调优](../linux-systems/)：VFS、ext4/xfs、块层、I/O 调度器、page cache、direct I/O。
- [计算机网络](../computer-networks/)：网络存储（NAS/SAN/对象存储/并行文件系统）依赖的网络基础。
- [Kubernetes](../../02-cloud-native/kubernetes/)：PV/PVC/StorageClass/CSI 的使用与实现。
- [CNI / CSI 深度](../../02-cloud-native/cni-csi/)：CSI 接口、Controller/Node Service、external-provisioner/attacher/resizer/snapshotter、VolumeAttachment、快照与扩容。
- [MLflow](../../03-ai-platform/mlflow/)：Artifact Store 与模型版本管理。
- [Kubeflow](../../03-ai-platform/kubeflow/)：Pipeline artifact 与 MLMD lineage。
- [KServe](../../03-ai-platform/kserve/)：模型存储与 storage-initializer。
- [Ray](../../03-ai-platform/ray/)：Object store spill/restore 与数据集存储。
- [Airflow](../../03-ai-platform/airflow/)：XCom 与 Dataset/Asset 调度中的存储。
- [RAG](../../06-rag/)：向量与 embedding 存储。
- [AI SRE](../../07-ai-sre/)：存储层可观测性。
- [Meta 案例研究](../../09-case-study/meta/)：Tectonic、Hammerspace、checkpoint SLA。
- [Google 案例研究](../../09-case-study/google/)：Orbax / OCDBT / Zarr3 checkpoint。
- [OpenAI 案例研究](../../09-case-study/openai/)：TB 级 checkpoint 与并行文件系统。
- [Anthropic 案例研究](../../09-case-study/anthropic/)：TB 级 checkpoint 与 artifact 治理。

## 11.5 社区与会议

- USENIX FAST / ATC：文件系统与存储顶会。
- SNIA：存储网络行业协会，关注企业存储标准。
- KubeCon + CloudNativeCon：CSI、云原生存储、数据管理。

## 11.6 一句话收尾

存储系统是 AI Infra 中**最不容易被看见、却最容易成为瓶颈**的底座。理解它的语义、架构和 trade-off，是设计可扩展、可运维、可省钱的 AI 平台的前提。
