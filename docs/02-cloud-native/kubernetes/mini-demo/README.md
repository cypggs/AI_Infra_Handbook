# k8s-mini — CPU 可运行的迷你 Kubernetes

一个**单进程、确定性、零外部依赖**的 Kubernetes 教学模拟器。它不启动任何容器、不连任何真实集群，
却忠实复刻了 Kubernetes 最核心的四大机制：

1. **调度框架（Scheduling Framework）** — `PreFilter → Filter → Score → Reserve → Bind`，以及 `PostFilter` 抢占
2. **Device Plugin + GPU 调度** — 扩展资源（`nvidia.com/gpu`）的上报与独占分配
3. **控制器范式 + Deployment 滚动升级** — `watch → reconcile`（水平触发）、`maxSurge/maxUnavailable`、级联 GC、自愈
4. **Gang 调度（all-or-nothing）** — 对应分布式训练的 `KEP-4671`，凑不够法定数全部回滚

> 设计哲学：**用最少的代码暴露最多的真实机制**。每个模块顶部的注释都写明了它与真实 K8s 组件的对应关系。
> 所有状态用一个 `tick` 驱动的单线程控制循环推进，没有并发、没有随机数，因此**反复运行结果完全一致**。

## 目录结构

```
k8s_mini/
├── model.py          # 数据模型：Resources / Node / Pod / ReplicaSet / Deployment（对应 API 对象）
├── store.py          # etcd 模拟：强一致 KV + watch/notify（对应 informer 的 list+watch）
├── apiserver.py      # kube-apiserver 模拟：CRUD + Mutating/Validating 准入链
├── scheduler.py      # kube-scheduler 模拟：调度框架 12 扩展点的核心几个 + gang + 抢占
├── device_plugin.py  # NVIDIA Device Plugin 模拟：注册容量 + Allocate/Release
├── kubelet.py        # kubelet 模拟：PLEG + syncPod + 探针 + Device Plugin 分配
├── controller.py     # Deployment/ReplicaSet 控制器：reconcile + 滚动升级 + 级联 GC
├── observer.py       # 事件观测器：记录调度/控制循环 trace（对应 Pod events）
└── demo.py           # 入口：四个场景串起上述机制
tests/                # 56 个 pytest 用例，覆盖每个模块
```

## 安装与运行

```bash
cd docs/02-cloud-native/kubernetes/mini-demo

# 方式一：安装为可执行命令
pip install -e ".[dev]"
k8s-mini-demo          # 运行演示
pytest tests/ -v       # 运行测试

# 方式二：直接用模块方式运行（无需安装）
python -m k8s_mini.demo
python -m pytest tests/ -v
```

> 不需要 Docker、不需要 GPU、不需要 minikube —— 一台普通笔记本的 CPU 即可。

## 四个演示场景

运行 `python -m k8s_mini.demo` 会输出：

```
[场景 1] 调度策略：binpack vs spread
  binpack 分布: {'node-a': 0, 'node-b': 0, 'node-c': 3}   ← Pod 聚到一个节点（提高密度）
  spread  分布: {'node-a': 1, 'node-b': 1, 'node-c': 1}   ← Pod 打散到不同节点（容错）

[场景 2] GPU 调度：Device Plugin 分配 nvidia.com/gpu
  vllm-0 → gpu-node-2 (Running), GPU devices allocated=[0]
  vllm-1 → gpu-node-2 (Running), GPU devices allocated=[1]
  vllm-2 → gpu-node-1 (Running), GPU devices allocated=[0]
  节点剩余 GPU: {'gpu-node-1': 1, 'gpu-node-2': 0}

[场景 3] Deployment 滚动升级 + 自愈
  v1 阶段 Pod: ['web-0293f695-0', 'web-0293f695-1', 'web-0293f695-2']
  v2 阶段 Pod: ['web-cdd2ad8d-0', 'web-cdd2ad8d-1', 'web-cdd2ad8d-2']
  滚动后镜像: {'web-cdd2ad8d-0': 'app:v2', ...}     ← 全部 v2
  自愈: 删除前 running=3 → 补齐后 running=3

[场景 4] Gang 调度（all-or-nothing）
  各 gang 状态: {'gang-ok': '2/2 scheduled', 'gang-fail': '0/3 scheduled'}
  gang-ok  已调度: 2（应=2，全部成功）
  gang-fail 已调度: 0（应=0，资源不足整体拒绝）
```

## 与真实 Kubernetes 的对应关系

| 本模拟 | 真实 K8s | 说明 |
|---|---|---|
| `store.py` 的内存 dict | etcd | 唯一真相源；`add_watcher` 对应 informer 的 list+watch |
| `apiserver._admit` 链 | 准入控制器 | Mutating → Validating，对应 webhook（Kyverno/OPA） |
| `scheduler._filter_nodes` | `NodeResourcesFit`/`NodeAffinity`/`TaintToleration` 插件 | Filter 扩展点 |
| `scheduler._score` | `NodeResourcesFit(MostAllocated/LeastAllocated)` + `SelectorSpread` | Score 扩展点 |
| `scheduler._schedule_gang` | KEP-4671 原生 PodGroup（v1.36）/ Volcano | Permit 扩展点 + all-or-nothing |
| `scheduler._try_preempt` | `DefaultPreemption`（PostFilter） | 抢占低优先级 Pod |
| `device_plugin.register` | `ListAndWatch` gRPC 上报 | 把扩展资源并入 `node.status.allocatable` |
| `kubelet._sync_pod` | PLEG → syncPod | 调 CRI 起容器、Device Plugin Allocate |
| `controller.reconcile` | controller-manager | 水平触发：期望 vs 实际，差值驱动 |

## 与真实集群的本质差异

| 维度 | 本模拟 | 真实集群 |
|---|---|---|
| 并发 | 单线程串行 tick | apiserver/etcd/scheduler/kubelet 各自并发 |
| 网络 | 无真实网络，Pod IP 是伪造字符串 | CNI 真实组网，kube-proxy 转发 |
| 容器运行时 | 不起任何容器，仅推进状态机 | CRI（containerd）真正拉镜像、起进程 |
| 持久化 | 进程结束即丢失 | etcd 强一致持久化 |
| 一致性 | 每步同步完成 | 最终一致（多控制循环异步收敛） |

正因为简化了这些，**模拟器能在 0.04 秒内跑完 56 个测试并复现 K8s 的核心设计权衡**——这正是教学想要的效果。
