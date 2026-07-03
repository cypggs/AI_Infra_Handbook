# operator-mini —— 纯 Python 从零实现的 Kubernetes Operator

一个**零第三方依赖**的教学模拟器，把 controller-runtime 的核心机制在一个 Python 进程里重建出来：
CRD 资源模型、kube-apiserver（乐观并发 / generation / /status 子资源 / finalizer / 级联 GC / watch 事件流）、
SharedInformer（List + Watch → 本地缓存 → EventHandler）、RateLimitingQueue（去重 + 延迟重排 + 指数退避）、
level-triggered Reconciler、以及一个模拟的"内置 Deployment Controller"。

> **它不是玩具**：四条 reconcile 铁律（level-triggered / 幂等 / 不阻塞 / 乐观）、finalizer 删除语义、
> owner 级联回收、observedGeneration 追踪、漂移自愈、指数退避重试——全部真实可运行、有 37 个测试守护。
> 用 `FakeClock` 替代真实时间，于是第 4 章描述的 `t=0 patch → reconcile #1 → t=5 reconcile #2 → t=10 收敛`
> 时间线可以**精确复现**。

## 快速开始

```bash
cd docs/02-cloud-native/operator/mini-demo
pip install -e ".[dev]"          # 仅依赖 pytest，包本体零依赖
pytest tests/ -v                 # 37 个测试全绿
python -m operator_mini.demo     # 跑四个端到端场景，打印收敛时间线
```

## 四个场景

| 场景 | 演示的核心机制 | 时间线 |
|---|---|---|
| **1. 创建** | 创建 CR → 自动建 Deployment+Service → 多轮收敛到 Ready | `t=0` 建，`t=5` ready |
| **2. 扩容+升级** | patch replicas 2→4 / image 0.6.3→0.7.0，三次 reconcile 收敛 | `t=5` patch，`t=10` ready |
| **3. 删除** | finalizer 清理外部资源 → 移除 finalizer → 级联 GC 子资源 | 删除后 CR/Deployment/Service 全清 |
| **4. 漂移自愈** | 有人手改 Deployment replicas=99，Owns 事件映射回 CR → level-triggered 纠回 3 | 漂移被纠正 |

场景 2 的输出（对应手册第 4 章的收敛时序）：

```
[   5.0s] patched Deployment llama (image=vllm:0.7.0, replicas=4)
[   5.0s] status gen=2 ready=2/4 observedGen=2     # reconcile #1：patch 完，新 Pod 还没 ready
[  10.0s] status gen=2 ready=4/4 observedGen=2     # reconcile #3：Pod ready，收敛
```

## 目录结构

```
operator_mini/
├── __init__.py        # 包说明 + 模块→controller-runtime 对照表
├── model.py           # CRD 资源模型（InferenceService / Deployment / Service + 语义辅助函数）
├── apiserver.py       # FakeApiServer：etcd+apiserver 语义（乐观锁/generation/status/finalizer/级联GC/watch）
├── informer.py        # SharedInformer：List+Watch→缓存；EventHandler（enqueue_self / enqueue_owner）
├── workqueue.py       # RateLimitingQueue + Clock（RealClock/FakeClock）
├── platform.py        # 模拟内置 Deployment Controller（Pod readyReplicas 随时间推进）
├── controller.py      # Controller：Source→Handler→Queue→Reconciler 流水线 + run_until_quiescent
├── reconciler.py      # InferenceServiceReconciler：业务逻辑（四条铁律全落地）
└── demo.py            # 装配 + 四个场景
tests/                 # 37 个测试：apiserver/informer/workqueue/reconciler/demo
```

## 与真实 controller-runtime 的对照

| 本模拟器 | controller-runtime / K8s | 是否简化 |
|---|---|---|
| `FakeApiServer`（内存 dict + 事件流） | kube-apiserver + etcd | 是：无 HTTP/gRPC，无鉴权，无 RBAC，单进程 |
| 乐观并发（`resourceVersion` 校验） | 完全一致 | 否 |
| generation（spec 变 +1，status 不变） | 完全一致 | 否 |
| `/status` 子资源（独立 rv，不 bump gen） | 完全一致 | 否 |
| finalizer（deletionTimestamp + 最后移除才删） | 完全一致 | 否 |
| 级联 GC（递归删 controller 子资源） | 完全一致（Foreground/Background 简化为同步删） | 是：不区分孤儿/前台/后台策略 |
| `Informer`（List 基线 + Watch 增量 → 缓存） | client-go SharedInformer | 是：用 `pump()` 显式驱动而非长连接 goroutine |
| EventHandler（`enqueue_self`=For / `enqueue_owner`=Owns） | `EnqueueRequestForObject` / `EnqueueRequestForOwner` | 否（语义一致） |
| `RateLimitingQueue`（去重 + `add_after` + `add_rate_limited`） | client-go workqueue | 是：无"in-flight 重入"语义（单线程同步模型不需要） |
| 指数退避（`base*2^n`，封顶 `max`）+ 令牌桶 | `ItemExponentialFailureRateLimiter` + `BucketRateLimiter` | 是：省略令牌桶（单进程无并发风暴） |
| `Controller.step()`（pump + get + reconcile + 重排） | controller-runtime Controller worker | 是：单 worker（`max_concurrent=1`），无 leader election |
| Reconciler 返回 `{requeue, requeue_after}` + error | `reconcile.Result{Requeue, RequeueAfter}` + error | 否（语义一致） |
| `platform.reconcile_deployments` | kube-controller-manager + endpoint controller | 重度简化：用时间阈值模拟 Pod ready |
| `Clock`（`FakeClock` 可步进） | 真实时间 | 是：仅为确定性测试 |

**简化的原则**：保留所有"控制平面语义"（这是 Operator 模式的本质），简化所有"分布式系统工程"
（HTTP/etcd/鉴权/并发/网络）——因为后者是 K8s 自己的事，与理解 Operator 无关。

## 测试覆盖要点

- **apiserver**：乐观锁冲突、generation 语义、/status 独立 rv、finalizer 删除、级联 GC、事件流、注入冲突钩子。
- **informer**：List 基线、Watch 增量、删除移出缓存、owner 反查映射、去重。
- **workqueue**：立即/延迟入队、去重、指数退避（5→10→20）、封顶、forget 重置、到期可见性。
- **reconciler（端到端）**：收敛到 Ready、幂等（多跑不产生重复子资源）、observedGeneration 追踪 spec、
  扩容升级多次收敛、finalizer 清理 + 级联、漂移自愈、冲突退避后恢复、RequeueAfter 非阻塞。

## 进一步阅读

- 完整设计讲解见手册 [Operator 第 7 章：Mini-Demo](../07-mini-demo)。
- 机制基础见 [第 2 章 核心思想](../02-core-ideas)、[第 3 章 架构](../03-architecture)、[第 4 章 Reconcile 流程](../04-reconcile-loop)。
- 真实实现对照见 [第 6 章 源码分析](../06-source-analysis)（controller-runtime / KubeRay / Training Operator / GPU Operator）。
