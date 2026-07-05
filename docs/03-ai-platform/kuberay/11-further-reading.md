# 11. 延伸阅读与总结

> 一句话理解：KubeRay 不是孤立的 Operator，它与 **Ray、Kubernetes、Operator 模式、KServe、MLflow、Kueue、Volcano、Prometheus** 共同构成完整的 AI 平台拼图。

## 11.1 核心官方资源

| 资源 | 说明 |
|---|---|
| [KubeRay Docs](https://ray-project.github.io/kuberay/) | 官方文档首页 |
| [Ray on Kubernetes](https://docs.ray.io/en/latest/cluster/kubernetes/index.html) | Ray 官方 K8s 指南 |
| [KubeRay GitHub](https://github.com/ray-project/kuberay) | 源码与 release note |
| [KubeRay API Reference](https://ray-project.github.io/kuberay/reference/api/) | CRD 字段参考 |
| [Ray Cluster Key Concepts](https://docs.ray.io/en/latest/cluster/key-concepts.html) | Ray 核心概念 |

## 11.2 相邻主题交叉引用

| 主题 | 关系 | 链接 |
|---|---|---|
| Ray | KubeRay 是 Ray 在 K8s 上的部署形态 | [Ray 总览](../ray/) |
| Kubernetes | KubeRay 的底座 | [Kubernetes 总览](../../02-cloud-native/kubernetes/) |
| Operator 模式 | KubeRay 本身就是 Operator | [Operator 模式总览](../../02-cloud-native/operator/) |
| KServe | 可加载 Ray Serve 端点 | [KServe 总览](../kserve/) |
| GPU 在 Kubernetes 上的调度 | KubeRay 的 RayCluster/Worker 需要 GPU 资源；本主题覆盖 K8s GPU 调度、MIG/MPS、拓扑感知、Gang 调度 | [GPU 在 Kubernetes 上的调度总览](../../02-cloud-native/gpu-scheduling/) |
| MLflow | 训练实验追踪与模型注册 | [MLflow 总览](../mlflow/) |
| Airflow | 工作流编排；Ray 作业可作为 Airflow 任务执行 | [Airflow 总览](../airflow/) |
| AI SRE | 可观测、SLO、告警 | [AI SRE 总览](../../07-ai-sre/) |

## 11.3 关键工程指南

| 主题 | 链接 |
|---|---|
| RayCluster Quick Start | https://docs.ray.io/en/latest/cluster/kubernetes/getting-started/raycluster-quick-start.html |
| RayJob Quick Start | https://docs.ray.io/en/latest/cluster/kubernetes/getting-started/rayjob-quick-start.html |
| RayService Quick Start | https://docs.ray.io/en/latest/cluster/kubernetes/getting-started/rayservice-quick-start.html |
| GCS Fault Tolerance | https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/kuberay-gcs-ft.html |
| Configuring Autoscaling | https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/configuring-autoscaling.html |
| GPU Guide | https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/gpu.html |
| TPU Guide | https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/tpu.html |
| KubeRay Auth | https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/kuberay-auth.html |
| TLS Guide | https://docs.ray.io/en/latest/cluster/kubernetes/user-guides/tls.html |
| Kueue Integration | https://docs.ray.io/en/latest/cluster/kubernetes/k8s-ecosystem/kueue.html |
| Prometheus + Grafana | https://docs.ray.io/en/latest/cluster/kubernetes/k8s-ecosystem/prometheus-grafana.html |

## 11.4 推荐学习路径

1. **第 1 周**：精读本主题 01-05 章，理解 CRD、架构、模块与工作流。
2. **第 2 周**：阅读 06 源码分析 + 07 Mini Demo；尝试本地 kind 安装 KubeRay Operator。
3. **第 3 周**：实践 GCS FT、GPU worker group、Autoscaler V2、RayService 升级。
4. **第 4 周**：阅读 KubeRay release note 与源码，关注 v1.6 新特性（History Server、RBAC、CronJob）。

## 11.5 一句话总结

**KubeRay 让 Ray 集群成为 Kubernetes 中的一等公民**：你写一份 YAML 描述 desired state，Operator 负责把 Head、Worker、Service、Autoscaler、Job、Serve 全部调和到现实状态，并在故障时自动恢复。

## 本章小结

- 官方文档、GitHub、API Reference 是最权威的学习来源。
- KubeRay 与 Ray、K8s、Operator、KServe、MLflow、AI SRE 等主题紧密相连。
- 学习路径：理论 → Mini Demo → 本地 kind → 生产实践 → 源码。

**参考来源**

- [KubeRay Docs](https://ray-project.github.io/kuberay/)
- [Ray Docs — Ray on Kubernetes](https://docs.ray.io/en/latest/cluster/kubernetes/index.html)
- [KubeRay GitHub](https://github.com/ray-project/kuberay)
- 本手册相关主题总览
