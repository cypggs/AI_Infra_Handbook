# Helm 总览

> 一句话理解：**Helm 是 Kubernetes 的包管理器**——它把一整套 K8s YAML（Deployment、Service、ConfigMap、Secret…）连同可配置的参数打包成一个 **Chart**，通过 **Go template + values** 生成最终的清单，并以 **Release（带版本/可回滚）** 的方式安装、升级、管理它们，让你像管理一个"软件包"而不是一堆散落的 YAML 文件。

## 为什么 AI 平台工程师必须懂 Helm

在 AI 平台上，一个服务往往不是"一个 Deployment"，而是"一整套对象"：推理服务的 Deployment + Service + ConfigMap（模型路径/批处理参数）+ Secret（API key/HF token）+ HPA + PodDisruptionBudget + ServiceMonitor（Prometheus）+ NetworkPolicy，还可能带 GPU Operator 的特殊注解、nodeSelector、toleration。直接用 `kubectl apply -f` 管理：

1. **环境差异难管**：dev / staging / prod 的副本数、镜像 tag、资源、域名都不同，要么维护 N 份几乎一样的 YAML，要么手动 `sed`。
2. **升级/回滚无版本**：`kubectl apply` 覆盖即"升级"，但出问题时你不知道"上一个版本长什么样"，也没有一键回滚。
3. **依赖无管理**：装一个 cert-manager，它自己有 CRD、Deployment、Service、RBAC……手写或复制几十个文件，版本不固定、升级困难。
4. **复用困难**：团队 A 写好的"GPU 推理服务模板"很难直接给团队 B 用，因为里面写死了名字、域名、资源。

Helm 正是解决这四件事的：**Chart（打包）→ values（参数化）→ Release（版本化/可回滚）→ Repository（分发/依赖）**。今天几乎所有的 K8s 上层应用（cert-manager、ingress-nginx、prometheus、GPU Operator、KubeRay、KServe、Volcano、ArgoCD……）都提供官方 Helm Chart 作为首选安装方式。不懂 Helm，你连"把一个 AI 平台组件装起来"都寸步难行；懂了 Helm，你就掌握了 K8s 应用的"打包与发布"这一层，并能用它把团队内部的 GPU 推理/训练模板标准化、版本化、可复用。

## 学习目标

阅读完本主题后，你应该能够：

1. 解释 Helm 的核心抽象：Chart、values、template（Go template + Sprig）、Release、Revision、Repository、Library Chart、Subchart/依赖。
2. 画出 Helm v3 的架构（CLI → 渲染 → 调 kube-apiserver 的三方合并 Patch），说清"为什么 Helm v3 删掉了 Tiller"、release 元数据存哪里（namespace 内的 Secret）。
3. 写一个生产级 Chart：`Chart.yaml`/`values.yaml`/`templates/` 结构，模板里用 <code v-pre>{{ .Values.x }}</code>、<code v-pre>{{ include }}</code>、命名约定、`_helpers.tpl`、`tpl` 函数、按条件渲染（`if`/`range`/`with`）。
4. 理解 Helm 的 **Release 生命周期**：install → upgrade（三方合并 Patch）→ rollback → uninstall，以及为什么"升级后手动 kubectl 改的东西 Helm 下次不一定覆盖"。
5. 掌握 values 的分层与覆盖顺序：`values.yaml` < `values.yaml` 里的子 chart < `-f values-prod.yaml` < `--set` < `--set-string`，以及全局值 `global`。
6. 区分 Helm 与 **Kustomize**（无模板的 overlay 叠加），知道各自适用场景与"何时该用哪个、何时都不该用"。
7. 理解高级特性：Hook（pre-install/post-upgrade/helm test）、post-renderer（渲染后再改一道的"逃生舱"）、OCI registry（Chart 当 OCI 制品）、Chart Signing（provenance）/Cosign、延迟绑定（lookup）、`helm.sh/resource-policy: keep`。
8. 跑通并扩展本主题的 Mini Demo——一个纯 Python、无需真实集群的"微型 Helm"：Chart 结构 + 简化模板引擎 + values 合并 + Release 状态机（install/upgrade/rollback）+ 三方合并 Diff。
9. 回答生产实践与面试题：私有 Chart 仓库/OCI 选型、CI/CD 与 GitOps（ArgoCD/Flux 与 Helm 集成）、Chart 版本与镜像版本策略、values 安全（Secret 不进 values）、helm release 卡在 pending-upgrade 如何救。

## Helm 与其他主题的关系

| 主题 | 解决的核心问题 | 与 Helm 的关系 |
|---|---|---|
| [Foundation](/01-foundation/) | Linux/网络/存储/GPU 基础 | Helm 不依赖这些，但 Chart 里经常声明 nodeSelector/资源/存储卷，需要懂它们才能写对 values |
| [容器运行时](/02-cloud-native/container-runtime/) | 镜像 + 容器生命周期 | Chart 渲染出的清单里，`image:` 字段就是容器运行时消费的对象；镜像版本策略（见容器运行时第 9 章）是 Helm values 的关键参数 |
| [Kubernetes](/02-cloud-native/kubernetes/) | 声明式编排、调度、生命周期 | Helm 不"运行"任何东西，它只是把参数化的 YAML **渲染后 `apply` 到 apiserver**；理解 K8s 声明式 API 是理解 Helm 的前提 |
| **Helm** | K8s 应用的打包、参数化、版本化、分发 | 本主题，K8s 的"包管理 + 发布"层 |
| Operator 模式（计划中） | 用代码管理有状态/领域应用 | Operator 管理的是"集群内长期运行的 reconcile 逻辑"；Helm 管理的是"渲染 + 一次性安装/升级"。两者常配合：用 Helm 装 Operator，Operator 管理具体实例 |
| [Ray](/03-ai-platform/ray/) | 分布式 Python 计算 | KubeRay 官方提供 Helm Chart 安装；RayCluster 的镜像/资源/版本都通过 Helm values 配置 |
| [vLLM](/04-llmops/vllm/) / [Triton](/04-llmops/triton/) | 单实例推理引擎 | 生产部署常把 vLLM/Triton 打成内部 Chart，副本数/GPU 数/模型/域名参数化，dev/staging/prod 复用 |
| [AI SRE](/07-ai-sre/) | 可观测、SLO | Helm Chart 里常带 ServiceMonitor/PodMonitor/annotations；版本化发布利于事故追溯与回滚 |
| [安全](/08-security/) | Secrets、RBAC、合规 | Chart 里的 Secret 管理（不进 values、用 External Secrets/sealed-secrets）、Chart 签名验证、OCI 仓库的准入策略 |
| [Meta](/09-case-study/meta/) / [Google](/09-case-study/google/) | 超大规模训练基础设施 | 超大规模公司内部有更强的配置管理系统（如 Google 用 Borg/CUE 系），Helm 是开源 K8s 生态对其的"够用"近似 |

## 本章结构

1. [背景](01-background) — 从手写 YAML 到包管理的演进，Helm 的历史（v1/v2 Tiller → v3），它解决的核心问题，与 Kustomize 的关系。
2. [核心思想](02-core-ideas) — Chart、values、template（Go template + Sprig 函数）、Release/Revision、Repository、依赖/Library Chart。
3. [架构设计](03-architecture) — Helm v3 架构（CLI 渲染 → kube-apiserver），为什么删 Tiller，release 存储演进（ConfigMap → Secret），三方合并 Patch。
4. [Release 工作流程](04-release-workflow) — install/upgrade/rollback/uninstall 全时序，三方合并怎么算"该改什么"，Hook 与生命周期。
5. [核心模块](05-core-modules) — Chart 仓库/OCI、template 引擎、values 合并、Release 存储、CLI 子命令、Hook/Test、post-renderer、Chart 依赖解析、Chart Signing。
6. [源码分析](06-source-analysis) — `helm/helm` 仓库结构，`pkg/action`（动作）、`pkg/engine`（模板引擎）、`pkg/releaseutil`、`pkg/lint`、`pkg/cli`、`pkg/kube`（与 apiserver 交互与三方合并）。
7. [工程实践](07-mini-demo) — 纯 Python 可运行的"微型 Helm"：Chart + 简化模板引擎 + values 合并 + Release 状态机 + 三方合并 Diff。
8. [企业生产实践](08-production-practice) — 私有仓库/OCI 选型、values 多环境管理、CI/CD 集成、GitOps（ArgoCD/Flux + Helm）、Chart 与镜像版本策略、Secret 治理、Chart 审计与签名、release 救援。
9. [最佳实践](09-best-practices) — Chart 设计黄金法则、命名约定、values 分层、模板可读性、Chart 测试、发布与回滚、安全基线、Helm vs Kustomize 决策。
10. [面试题](10-interview-questions) — 初/中/高级 Helm 概念、机制、实现与生产落地面试题。
11. [延伸阅读](11-further-reading) — 官方文档、Chart 指南、源码入口、社区 Chart、与本手册其他主题的交叉引用与学习路径。

## 一句话总结

Helm 不是一个"运行时"，而是 **Kubernetes 应用的"编译器 + 包管理器 + 发布工具"三合一**：它用 Go template + values 把"参数化的模板"编译成"具体清单"，把一整套对象打包成 Chart 分发复用，并以 Release 的版本化记录让你能安全升级、一键回滚；理解了"Chart = 模板 + 默认值，Release = 一次带版本的渲染结果，三方合并 = Helm 用你上次的 chart、上次的 values、这次的 chart+values 算出最小 diff"，你就理解了 Helm 的全部——剩下的都只是 Sprig 函数与 CLI 语法。
