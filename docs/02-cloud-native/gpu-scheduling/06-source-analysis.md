# 6. 源码分析

> 一句话理解：**读源码不是为了背每一行，而是为了找到“谁调用谁、状态存在哪、扩展点在哪”**——这样你在排障、写插件、做二次开发时才能快速定位。

## 6.1 源码阅读策略

面对 NVIDIA Device Plugin、GPU Operator、scheduler-plugins、Volcano、Kueue 这么多仓库，建议按这个顺序：

1. **先找入口**：`main.go` / `cmd/` 下面的启动函数。
2. **再找循环**：`wait.Until`、`Run`、`syncLoop`、`session` 这类周期或事件驱动循环。
3. **然后看状态**：资源存在哪（apiserver、informer cache、本地内存）。
4. **最后看扩展点**：Filter/Score/Reserve/Permit 接口在哪实现。

## 6.2 NVIDIA k8s-device-plugin

仓库：[https://github.com/NVIDIA/k8s-device-plugin](https://github.com/NVIDIA/k8s-device-plugin)

### 目录结构

```text
k8s-device-plugin/
├── cmd/
│   └── nvidia-device-plugin/         # main 入口
├── internal/
│   ├── plugin/                       # DevicePlugin 实现
│   ├── rmgr/                         # 资源管理
│   ├── mig/                          # MIG 相关逻辑
│   └── allocator/                    # 设备分配策略
├── nvidiadeviceplugin.yml            # 部署清单
└── deployments/
```

### 启动调用链

```text
main()
  │
  ▼
StartDevicePlugin(ctx, config)
  │
  ▼
plugin.NewNvidiaDevicePlugin(config, resourceManager)
  │
  ▼
p.Serve(socketPath)          # 在 unix socket 上启动 gRPC server
  │
  ▼
注册到 kubelet /var/lib/kubelet/device-plugins/kubelet.sock
```

### ListAndWatch

```go
// internal/plugin/server.go
func (plugin *NvidiaDevicePlugin) ListAndWatch(e *pluginapi.Empty, s pluginapi.DevicePlugin_ListAndWatchServer) error {
    s.Send(&pluginapi.ListAndWatchResponse{Devices: plugin.apiDevices()})
    for {
        select {
        case <-plugin.health:
            s.Send(&pluginapi.ListAndWatchResponse{Devices: plugin.apiDevices()})
        case <-plugin.stop:
            return nil
        }
    }
}
```

关键逻辑：

- 初始发送全部设备列表。
- 当健康状态变化时重新发送。
- kubelet 据此更新 `node.status.allocatable`。

### Allocate

```go
func (plugin *NvidiaDevicePlugin) Allocate(ctx context.Context, reqs *pluginapi.AllocateRequest) (*pluginapi.AllocateResponse, error) {
    responses := pluginapi.AllocateResponse{}
    for _, req := range reqs.ContainerRequests {
        // 1. 检查 req.DevicesIDs 是否都在 plugin.devices 中且 healthy
        // 2. 根据 MIG 配置决定返回的设备 ID
        // 3. 构造 pluginapi.ContainerAllocateResponse
        //    - Envs: NVIDIA_VISIBLE_DEVICES=UUID1,UUID2,...
        //    - Devices: /dev/nvidia*
        //    - Mounts: 驱动库路径
    }
    return &responses, nil
}
```

### MIG 处理

MIG 设备命名遵循 `nvidia.com/mig-<profile>`，源码里通过 `mig.Profile` 和 `mig.Device` 把物理 GPU 的 MIG 实例映射成独立设备 ID。当用户请求 `nvidia.com/mig-1g.5gb: 2` 时，Allocate 会返回两个 MIG 实例的 UUID。

## 6.3 NVIDIA GPU Operator

仓库：[https://github.com/NVIDIA/gpu-operator](https://github.com/NVIDIA/gpu-operator)

### 目录结构

```text
gpu-operator/
├── cmd/
│   └── gpu-operator/                 # 主控制器入口
├── controllers/
│   ├── clusterpolicy_controller.go   # ClusterPolicy 调和
│   ├── state_manager.go              # 节点状态机
│   └── ...
├── assets/
│   └── *.yaml                        # DaemonSet/Deployment 模板
└── api/
    └── v1/
        └── clusterpolicy_types.go    # ClusterPolicy CRD
```

### 控制器入口

```go
// cmd/gpu-operator/main.go
func main() {
    mgr, err := ctrl.NewManager(...)
    ...
    if err = controllers.NewClusterPolicyReconciler(mgr).SetupWithManager(mgr); err != nil {
        os.Exit(1)
    }
    mgr.Start(ctrl.SetupSignalHandler())
}
```

### ClusterPolicy 调和循环

```go
// controllers/clusterpolicy_controller.go
func (r *ClusterPolicyReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // 1. 读取 ClusterPolicy
    // 2. 按顺序创建/更新组件：Driver → Toolkit → DevicePlugin → MIG Manager → DCGM → GFD → Validator
    // 3. 更新 ClusterPolicy.status
}
```

### 节点状态机

GPU Operator 为每个节点维护一个状态：

```go
// controllers/state_manager.go（简化）
type nodeState struct {
    driverReady      bool
    toolkitReady     bool
    pluginReady      bool
    migReady         bool
    dcgmReady        bool
    gfdReady         bool
    validatorReady   bool
}
```

只有全部 Ready，节点才被认为可用于 GPU 调度。这个状态机让 GPU Operator 能够处理“驱动编译慢”、“MIG 配置失败”等长尾问题。

### 组件模板

`assets/` 下的 YAML 模板会被 controller 用 `text/template` 渲染，注入镜像版本、ConfigMap 名、节点 selector 等参数。这使得 GPU Operator 可以通过一个 CR 控制所有 DaemonSet 的部署细节。

## 6.4 scheduler-plugins

仓库：[https://github.com/kubernetes-sigs/scheduler-plugins](https://github.com/kubernetes-sigs/scheduler-plugins)

### 目录结构

```text
scheduler-plugins/
├── cmd/
│   └── scheduler/                    # 自定义调度器入口
├── pkg/
│   ├── coscheduling/                 # Gang 调度
│   ├── noderesourcetopology/         # 拓扑感知
│   ├── capacityscheduling/           # 弹性配额
│   ├── trimaran/                     # 负载感知
│   └── ...
└── manifests/
```

### Coscheduling 插件

核心文件：`pkg/coscheduling/coscheduling.go`。

```go
func New(args runtime.Object, handle framework.Handle) (framework.Plugin, error) {
    // 初始化 PodGroup  informer
}

func (cs *Coscheduling) PreFilter(ctx context.Context, state *framework.CycleState, pod *v1.Pod) (*framework.PreFilterResult, *framework.Status) {
    // 检查 PodGroup 是否超时、minMember 是否合法
}

func (cs *Coscheduling) Filter(ctx context.Context, state *framework.CycleState, pod *v1.Pod, nodeInfo *framework.NodeInfo) *framework.Status {
    // 普通节点过滤
}

func (cs *Coscheduling) Reserve(ctx context.Context, state *framework.CycleState, pod *v1.Pod, nodeName string) *framework.Status {
    // 在假定节点上为 PodGroup 预留资源
}

func (cs *Coscheduling) Permit(ctx context.Context, state *framework.CycleState, pod *v1.Pod, nodeName string) (*framework.Status, time.Duration) {
    // 等待 PodGroup 全部到达
    // 到达 → Success
    // 未到达 → Wait(timeout)
}
```

实现要点：

- 通过 `framework.Handle` 获取 PodGroup informer。
- 用 `CycleState` 在扩展点之间传递 PodGroup 上下文。
- `Permit` 阶段使用 `time.After` 或 `wait` 等待其他成员。

### NodeResourceTopology 插件

核心文件：`pkg/noderesourcetopology/filter.go`、`pkg/noderesourcetopology/score.go`。

```go
func (tm *TopologyMatch) Filter(ctx context.Context, cycleState *framework.CycleState, pod *v1.Pod, nodeInfo *framework.NodeInfo) *framework.Status {
    // 1. 从 informer cache 获取 NodeResourceTopology 对象
    // 2. 检查 Pod 请求的资源是否能在某个 zone（NUMA）内满足
    // 3. 返回 Unschedulable 或 Success
}

func (tm *TopologyMatch) Score(ctx context.Context, state *framework.CycleState, pod *v1.Pod, nodeName string) (int64, *framework.Status) {
    // 1. 获取节点拓扑
    // 2. 计算请求资源在拓扑上的紧凑程度
    // 3. 返回 0-100 分数
}
```

## 6.5 Volcano

仓库：[https://github.com/volcano-sh/volcano](https://github.com/volcano-sh/volcano)

### 目录结构

```text
volcano/
├── cmd/
│   ├── scheduler/                    # volcano-scheduler 入口
│   ├── controller-manager/           # Job/PodGroup/Queue 控制器
│   └── ...
├── pkg/
│   ├── scheduler/
│   │   ├── framework/                # 插件框架
│   │   ├── plugins/                  # gang/nodeorder/predicates/proportion
│   │   └── cache/                    # 调度缓存
│   └── controllers/
│       ├── job/                      # VolcanoJob 控制器
│       └── podgroup/                 # PodGroup 控制器
```

### 控制器入口

```go
// cmd/controller-manager/main.go
func main() {
    // 初始化 VolcanoJob / PodGroup / Queue informer
    // 启动 Reconciler
}
```

### 调度器入口

```go
// cmd/scheduler/main.go
func main() {
    s, err := scheduler.NewScheduler(...)
    s.Run(ctx)
}
```

### Session 与调度循环

Volcano 用 `Session` 表示一次调度周期：

```go
// pkg/scheduler/scheduler.go
func (pc *Scheduler) Run(ctx context.Context) {
    for {
        select {
        case action := <-pc.actions:
            session := schedulerutil.OpenSession(pc.cache, pc.plugins, pc.configurations)
            action.Execute(session)
            schedulerutil.CloseSession(session)
        case <-ctx.Done():
            return
        }
    }
}
```

一次 Session 内：

1. 从 cache 中读取所有 Job/Queue/PodGroup/Node。
2. 按 Queue 权重选择待调度 Job。
3. 运行 `predicate` 插件过滤节点。
4. 运行 `nodeorder` 插件打分。
5. 运行 `gang` 插件检查 minMember。
6. 统一 Allocate / Bind。

### Gang 插件

```go
// pkg/scheduler/plugins/gang/gang.go
func (gp *gangPlugin) OnSessionOpen(ss *framework.Session) {
    // 1. 为每个 PodGroup 创建 JobInfo
    // 2. 在 predicate 阶段检查 PodGroup 资源是否足够
    // 3. 在 allocate 阶段统一绑定
}
```

Volcano 的 Gang 实现比 scheduler-plugins 更“原生”，因为它在独立调度器里可以控制整个调度周期，而不需要依赖 Permit 等待。

## 6.6 Kueue

仓库：[https://github.com/kubernetes-sigs/kueue](https://github.com/kubernetes-sigs/kueue)

### 目录结构

```text
kueue/
├── cmd/
│   └── kueue/                        # 主控制器入口
├── pkg/
│   ├── controller/
│   │   ├── core/                     # Workload / ClusterQueue / LocalQueue 控制器
│   │   └── jobs/                     # Job/Deployment/StatefulSet 集成
│   ├── scheduler/                    # Kueue 调度器（做准入决策）
│   ├── cache/                        # 配额缓存
│   └── workload/                     # Workload 工具函数
```

### Workload 控制器

```go
// pkg/controller/core/workload_controller.go
func (r *WorkloadReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    // 1. 获取 Workload
    // 2. 若未 admitted，尝试匹配 ClusterQueue
    // 3. 配额足够 → admit，解挂 Job，创建 Pod
    // 4. 配额不足 → 保持 suspend，更新 status
}
```

### 配额缓存

Kueue 在内存中维护一个 `Cache`，记录每个 `ClusterQueue` 的 nominal quota、borrowing limit、当前使用量：

```go
// pkg/cache/cluster_queue.go
 type ClusterQueue struct {
     Name string
     ResourceGroups []ResourceGroup
     UsedResources  Resources
     Workloads      map[string]*workload.Info
 }
```

这个缓存让 Kueue 能在不频繁查询 apiserver 的情况下做快速准入决策。

## 6.7 关键源码入口速查表

| 组件 | 入口文件 | 看什么 |
|---|---|---|
| k8s-device-plugin | `cmd/nvidia-device-plugin/main.go` | 启动、配置加载 |
| k8s-device-plugin | `internal/plugin/server.go` | ListAndWatch / Allocate |
| GPU Operator | `cmd/gpu-operator/main.go` | 控制器初始化 |
| GPU Operator | `controllers/clusterpolicy_controller.go` | Reconcile 循环 |
| GPU Operator | `assets/*.yaml` | DaemonSet 模板 |
| scheduler-plugins | `cmd/scheduler/main.go` | 自定义调度器入口 |
| scheduler-plugins | `pkg/coscheduling/coscheduling.go` | Gang 扩展点 |
| scheduler-plugins | `pkg/noderesourcetopology/filter.go` | 拓扑 Filter |
| Volcano | `cmd/scheduler/main.go` | 调度器启动 |
| Volcano | `pkg/scheduler/scheduler.go` | Session 循环 |
| Volcano | `pkg/scheduler/plugins/gang/gang.go` | Gang 插件 |
| Kueue | `cmd/kueue/main.go` | 控制器启动 |
| Kueue | `pkg/controller/core/workload_controller.go` | Workload 准入 |
| Kueue | `pkg/cache/cluster_queue.go` | 配额缓存 |

## 6.8 本章小结

| 模块 | 最值得读的调用链 |
|---|---|
| Device Plugin | `main → Serve → ListAndWatch / Allocate` |
| GPU Operator | `ClusterPolicy Reconcile → 按顺序 apply DaemonSet → 更新节点状态` |
| Coscheduling | `PreFilter → Reserve → Permit → Bind` |
| NodeResourceTopology | `Filter(zone) → Score(topology compactness)` |
| Volcano | `Session.Open → predicate → nodeorder → gang → allocate → Session.Close` |
| Kueue | `Workload Reconcile → cache.FindClusterQueue → admit → unsuspend Job` |

掌握这些调用链后，遇到“Pod 调度不到节点”、“MIG 配置不生效”、“Gang 调度死锁”、“队列配额不更新”等问题时，你就能快速判断该打断点或加日志的位置。下一章我们将把这些概念和源码变成可以本地运行的 Mini Demo。
