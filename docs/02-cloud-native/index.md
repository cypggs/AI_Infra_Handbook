# 云原生篇

> 一句话理解：AI 平台首先是云原生平台，**Kubernetes 是调度 GPU、网络、存储和生命周期管理的底座**——几乎所有 AI 平台（Ray、vLLM、Triton、KServe、Kubeflow）都构建在它之上。

## 已上线主题

- **[Kubernetes](./kubernetes/)** — 声明式、控制循环驱动的容器编排系统。从设计动机、架构、调度框架、源码、生产实践到 GPU/Gang 调度，附纯 Python 可运行的 Mini Demo。
- **[容器运行时](./container-runtime/)** — 把"镜像变成进程"的那一层。从 chroot/LXC/Docker 演进、OCI 标准、namespace/cgroup/overlayfs 三件套、containerd/runc 分层架构、CRI/dockershim、到镜像优化/签名/沙箱/惰性拉取，附纯 Python 可运行的 Mini Demo（40 测试）。
- **[Helm](./helm/)** — Kubernetes 的包管理器。从裸 YAML 四宗罪、Chart/values/template/Release 四要素、Tiller 移除与客户端渲染、到三方合并 Patch（升级保留人工改动的核心机制），附纯 Python 可运行的 Mini Demo（55 测试）。
- **[Operator 模式](./operator/)** — 把领域运维知识编码成控制循环。从 CoreOS 2016 定义、CRD/Controller/Reconcile 四铁律、controller-runtime 架构、finalizer/owner/status/webhook、KubeRay/Training Operator/GPU Operator 源码对照，到纯 Python 从零实现的 Mini Demo（37 测试，精确复现 reconcile 收敛时间线）。
- **[CNI / CSI 深度](./cni-csi/)** — Kubernetes 把网络与存储外包给插件的两根柱子。从 in-tree 到 out-of-tree 的演进、CNI ADD/DEL/CHECK/GC、CSI Identity/Controller/Node 三面 gRPC、Flannel/Calico/Cilium/Multus/SR-IOV、EBS/Ceph/Lustre/WEKA/S3 CSI，到纯 Python 从零实现的 Mini Demo（46 测试，精确复现 Pod 网络 + 存储生命周期）。

## 计划中主题

- Docker

> 后续主题将按"先打地基（容器运行时 → Kubernetes），再讲周边（Docker/Helm/Operator/网络存储接口）"的顺序推进。
