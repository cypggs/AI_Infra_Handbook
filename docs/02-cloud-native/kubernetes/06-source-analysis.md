# 6. 源码分析

> 一句话理解：`kubernetes/kubernetes` 是个庞大的 Go 单体仓库，但核心机制集中在三条调用链——**调度链**（scheduler）、**控制链**（controller-runtime / sample-controller）、**执行链**（kubelet PLEG + syncPod）。本章带你定位每条链的入口与关键函数。

## 6.1 仓库结构总览

`github.com/kubernetes/kubernetes` 主要目录：

```text
kubernetes/
├── cmd/                    # 各组件的 main 入口
│   ├── kube-apiserver/
│   ├── kube-scheduler/
│   ├── kube-controller-manager/
│   ├── kubelet/
│   └── kube-proxy/
├── pkg/                    # 核心实现（最常读的部分）
│   ├── scheduler/          # ★ kube-scheduler 实现 + 调度框架
│   ├── kubelet/            # ★ kubelet 实现（PLEG/syncPod）
│   ├── controller/         # 内置控制器
│   ├── apiserver/          # apiserver 实现
│   ├── proxy/              # kube-proxy iptables/IPVS
│   ├── kube-plugins/       # 插件
│   └── ...
├── staging/src/k8s.io/     # 被 vendor 的子模块（client-go, api, apimachinery）
│   ├── client-go/          # ★ Informer / WorkQueue / client
│   └── api/                # 内置资源类型定义
├── test/                   # 集成/e2e 测试
└── plugin/                 # CNI/CSI/admission 插件示例
```

辅助仓库：

- `kubernetes-sigs/controller-runtime`：写 Operator 的事实标准库（KubeRay、Volcano、GPU Operator 都用它）。
- `kubernetes-sigs/scheduler-plugins`：调度框架的 out-of-tree 插件。
- `kubernetes/client-go`：K8s Go 客户端，含 Informer/WorkQueue。

## 6.2 调度链：kube-scheduler 源码

### 入口

`cmd/kube-scheduler/scheduler.go` → `pkg/scheduler/scheduler.go` 的 `Scheduler.Run()`：

```go
// pkg/scheduler/scheduler.go（简化）
func (sched *Scheduler) Run(ctx context.Context) {
    sched.SchedulingQueue.Run()      // 待调度队列
    go wait.Until(sched.scheduleOne, 0, ctx.Done())  // 主循环
}
```

### scheduleOne：调度一个 Pod 的主流程

```go
// pkg/scheduler/scheduler.go
func (sched *Scheduler) scheduleOne(ctx context.Context) {
    // 1. 从队列取出一个 Pod（QueueSort 插件决定顺序）
    podInfo := sched.NextToTry()

    // 2. 调度周期：跑框架流水线
    state, targetNode, err := sched.SchedulePod(ctx, fwk, state, pod)
    //   SchedulePod 内部依次调用：
    //     RunPreFilterPlugins → RunFilterPlugins(含 NodeFilter) → RunPostFilterPlugins(抢占)
    //     → RunPreScorePlugins → RunScorePlugins → 选最高分节点

    // 3. Reserve（预占）
    fwk.RunReservePlugins(...)

    // 4. Permit（Gang 调度在此"等待"或"放行"）
    permit := fwk.RunPermitPlugins(...)

    // 5. 绑定周期（可并发）
    go sched.bind(ctx, fwk, state, pod, targetNode)
    //   bind 内部：RunPreBindPlugins → RunBindPlugins(写 nodeName) → RunPostBindPlugins
}
```

### 调度框架接口

`pkg/scheduler/framework/interface.go` 定义了 `Framework` 接口与各扩展点插件接口：

```go
// pkg/scheduler/framework/interface.go（节选）
type Framework interface {
    // 调度周期
    RunPreFilterPlugins(ctx, state, pod) Status
    RunFilterPlugins(ctx, state, pod, node) PluginToStatus
    RunPostFilterPlugins(ctx, state, pod, filteredNodeStatusMap) *PostFilterResult
    RunPreScorePlugins(ctx, state, pod, nodes) Status
    RunScorePlugins(ctx, state, pod, nodes) PluginToNodeScores
    // 绑定周期
    RunReservePlugins(...) 
    RunPermitPlugins(...) 
    RunPreBindPlugins(...) 
    RunBindPlugins(...) 
    RunPostBindPlugins(...) 
    // 状态
    CycleState()  // 内部用 sync.Map
}

// 各插件接口（节选）
type FilterPlugin interface { Plugin; Filter(ctx, state, pod, node) *Status }
type ScorePlugin   interface { Plugin; Score(ctx, state, pod, nodeName) (int64, *Status) }
type PermitPlugin  interface { Plugin; Permit(ctx, state, pod, nodeName) (*Status, time.Duration) }
```

**重要更正**（来自调研验证）：`pkg/scheduler/framework` **本身就是调度框架的规范定义（canonical definition）**，而不是"对 `k8s.io/kube-scheduler/framework` 接口的内部包装"。早期文献把它描述成 wrapper 是错误的——这个包定义了所有扩展点接口，`k8s.io/kubernetes/pkg/scheduler/framework` 是权威来源。

### v1.36 PodGroup / Placement 接口（新增）

自 v1.36.0，`interface.go` 新增了协同调度相关接口（在 v1.34/v1.35 中不存在）：

```go
// pkg/scheduler/framework/interface.go（v1.36 新增，节选）
type PodGroupPostFilterPlugin interface {
    Plugin
    // PodGroup 调度失败后的抢占逻辑
    PostFilter(ctx, state, pod, filteredNodeStatusMap) *PostFilterResult
}

// 协同放置（Placement）相关，基于 PodGroupCycleState
func (f *framework) RunPlacementGeneratePlugins(...) 
func (f *framework) RunPlacementScorePlugins(...)
```

对应 KEP-4671（Gang Scheduling）与 KEP-5598（Opportunistic Batching）。这是 Gang 调度走向 in-tree 的代码证据。

### 内置插件位置

`pkg/scheduler/framework/plugins/` 下每个插件一个目录：

```text
plugins/
├── noderesources/      # NodeResourcesFit(Filter/Score), BalancedAllocation(Score)
├── nodeaffinity/       # NodeAffinity(Filter), NodePreferAvoidPods
├── tainttoleration/    # TaintToleration(Filter/Score)
├── podtopologyspread/  # PodTopologySpread(Filter/Score) —— 拓扑打散
├── defaultpreemption/  # DefaultPreemption(PostFilter)
├── imagelocality/      # ImageLocality(Score)
├── volumescheduling/   # VolumeBinding(PreBind)
└── ...
```

每个插件实现对应接口并注册到 registry，配置通过 `KubeSchedulerConfiguration` 启用/调参。

## 6.3 控制链：Controller 模式源码

### client-go Informer 机制

`staging/src/k8s.io/client-go/tools/cache/` 是 Informer 实现：

```go
// client-go/tools/cache/shared_informer.go（概念）
type SharedInformer interface {
    AddEventHandler(handler ResourceEventHandler)  // 注册 OnAdd/OnUpdate/OnDelete
    Run(stopCh)  // 启动 Reflector（list+watch）
    GetStore() Store  // 本地缓存（Indexer）
    // 周期性 resync：把 Store 全量重新触发 OnUpdate，纠正漂移
}

type ResourceEventHandlerFuncs struct {
    OnAdd    func(obj interface{})
    OnUpdate func(oldObj, newObj interface{})
    OnDelete func(obj interface{})
}
```

典型控制器结构：

```go
// 经典 controller 模板（sample-controller / controller-runtime 都遵循它）
type Controller struct {
    informer    cache.SharedInformer   // watch + 本地缓存
    workqueue   workqueue.RateLimitingInterface  // 限速去重队列
    kubeclient  clientset.Interface
}

func (c *Controller) Run(workers int, stopCh <-chan struct{}) {
    c.informer.AddEventHandler(cache.ResourceEventHandlerFuncs{
        AddFunc:    c.enqueue,   // 事件 → 入队 key
        UpdateFunc: func(_, x) { c.enqueue(x) },
        DeleteFunc: c.enqueue,
    })
    for i := 0; i < workers; i++ {
        go wait.Until(c.worker, time.Second, stopCh)  // 多 worker 消费
    }
}

func (c *Controller) worker() {
    for c.processNext() {}  // 从队列取 key → reconcile
}

func (c *Controller) reconcile(key string) error {
    obj, exists, err := c.informer.GetStore().GetByKey(key)  // 读本地缓存
    if !exists { return nil }  // 已删除
    // ... 业务逻辑：对比 spec vs status，调 apiserver 纠偏 ...
}
```

这就是 **水平触发（level-triggered）reconcile** 的标准实现：不依赖"发生了什么事件"，只看"当前状态"。

### controller-runtime（写 Operator 的标准库）

`kubernetes-sigs/controller-runtime` 把上面的模板封装成更高层抽象：

```go
mgr, _ := ctrl.NewManager(config, ctrl.Options{})

type RayClusterReconciler struct {
    client.Client
    Scheme *runtime.Scheme
}

func (r *RayClusterReconciler) Reconcile(ctx, req) (ctrl.Result, error) {
    var cluster rayv1.RayCluster
    if err := r.Get(ctx, req.NamespacedName, &cluster); err != nil { ... }
    // 业务逻辑：按 spec 创建/更新 head/worker Pod、Service...
    // 返回 Result{RequeueAfter: duration} 控制下一轮
}

// 注册：watch RayCluster，及其拥有的 Pod（owner reference 变化触发 reconcile）
r.ctrl.New(mgr, &RayClusterReconciler{}).
    For(&rayv1.RayCluster{}).
    Owns(&corev1.Pod{}).
    Complete(r)
```

KubeRay、GPU Operator、Volcano、KServe 的 Operator 都基于这套库。

## 6.4 执行链：kubelet PLEG 与 syncPod

### PLEG（Pod Lifecycle Event Generator）

`pkg/kubelet/pleg/pleg.go`：

```go
// pkg/kubelet/pleg/generic.go（简化）
func (g *GenericPLEG) relist() {
    // 1. 通过 CRI 列出本节点所有 PodSandbox 与 Container
    pods := g.runtime.GetPods(true)
    // 2. 对比 g.cache（上次状态），找出变化
    for _, pod := range pods {
        old := g.cache.get(pod.ID)
        // 对比容器状态，产生 PodLifecycleEvent（Started/Died/...）
        g.eventChannel <- *event
    }
    g.cache.Update(pods)  // 更新缓存
}
```

PLEG 每 1s `relist` 一次，产生的事件触发 kubelet 主循环对该 Pod 的 `syncPod`。

### syncPod：把 Pod 收敛到期望状态

`pkg/kubelet/kubelet.go` 的 `syncPod` 是 kubelet 最核心的函数：

```go
// pkg/kubelet/kubelet_pods.go / kubelet.go（概念）
func (kl *Kubelet) syncPod(pod *v1.Pod, mirrorPod *v1.Pod, podStatus *kubecontainer.PodStatus) {
    // 1. 判断是否需要重建 sandbox（网络/Cgroup 变化、sandbox 不存在）
    // 2. 创建数据目录、生成容器运行时选项
    // 3. 拉镜像（PullImage）
    // 4. 通过 Device Plugin 分配硬件资源（GPU/FPGA），注入环境变量与设备挂载
    // 5. CRI RunPodSandbox（CNI 在此分配网络）
    // 6. CSI 挂卷
    // 7. 对每个 container：CreateContainer → StartContainer
    // 8. 启动探针
}
```

`syncPod` 是**幂等收敛**的：它对比"期望（Pod spec）"与"实际（CRI 上报的容器状态）"，只做必要的增量操作。这与控制器的 reconcile 同构。

### Device Plugin 的接入点

`pkg/kubelet/device-manager/` 在 syncPod 中调用各 Device Plugin：

```go
// 概念：kubelet 启动时监听 /var/lib/kubelet/device-plugins/kubelet.sock
// 各 Device Plugin（如 NVIDIA）启动时向 kubelet 注册，上报资源容量（如 nvidia.com/gpu=8）
//   并暴露 Allocate() 接口
//
// syncPod 中：
allocations := deviceManager.Allocate(pod, container)
//   返回每个容器的设备分配：环境变量(NVIDIA_VISIBLE_DEVICES) + 设备挂载(/dev/nvidia0)
//   注入到容器的 CreateContainer 请求
```

这是 GPU 能被 Pod 声明 `nvidia.com/gpu` 并被实际挂载的代码路径。

## 6.5 一次完整调度的源码追踪（串起来）

把三条链串起来：用户 apply 一个 GPU Pod 后，

1. **apiserver**（`staging/k8s.io/apiserver`）：`InstallAPI` → handler → admission → `etcd3` store 写入。
2. **scheduler**（`pkg/scheduler`）：`SharedInformer` watch 到 Pod → `scheduleOne` → `Framework.RunFilterPlugins`（含 `NodeResourcesFit` 检查 `nvidia.com/gpu`）→ `RunScorePlugins` → `RunBindPlugins` 写 `nodeName`。
3. **kubelet**（`pkg/kubelet`）：`PodConfig` informer watch 到 `nodeName==self` → `PLEG`/事件触发 `syncPod` → `device-manager.Allocate`（调 NVIDIA Device Plugin）→ `CRI.RunPodSandbox`（CNI）→ `CRI.CreateContainer/StartContainer`。
4. **kubelet** 周期 `updateStatus` 把 `phase=Running` 写回。

## 6.6 调试与阅读源码的建议

- **从 cmd/ 入口顺着 Run 往下读**，比从中间啃容易建立全局观。
- **关注 `wait.Until` / `Run` 这类周期循环**——它们标记了"控制循环"的边界。
- **Informer 是控制器性能的关键**：读 `client-go/tools/cache` 理解为什么控制器不压垮 apiserver。
- **用 `kubectl explain` 和 CRD 的 OpenAPI schema 对照源码类型**，理解 spec/status 结构。
- **调度框架改插件**：clone `scheduler-plugins`，按 `pkg/coscheduling`（Gang 调度样例）读，是学习扩展点最快的路径。

## 本章小结

K8s 源码虽大，但核心机制集中在三条链：**调度链**（`pkg/scheduler` 的 `scheduleOne` + 调度框架 12 扩展点，v1.36 新增 PodGroup/Placement）、**控制链**（`client-go` Informer + reconcile 模板，`controller-runtime` 是 Operator 标准库）、**执行链**（`pkg/kubelet` 的 PLEG + `syncPod` + device-manager）。三条链的共同范式是**水平触发的幂等收敛**：每个循环只看"当前状态 vs 期望状态"，做最小必要动作，靠 resync/周期兜底纠正漂移。读源码时抓住这条主线，庞大代码库就会收敛为几个清晰的模式。

**参考来源**

- [kubernetes/kubernetes 仓库](https://github.com/kubernetes/kubernetes)
- [pkg/scheduler/framework 源码（接口与扩展点）](https://pkg.go.dev/k8s.io/kubernetes/pkg/scheduler/framework)
- [KEP-624 Scheduling Framework](https://github.com/kubernetes/enhancements/blob/master/keps/sig-scheduling/624-scheduling-framework/kep.yaml)
- [kubernetes-sigs/scheduler-plugins](https://scheduler-plugins.sigs.k8s.io/)
- [client-go Informer / WorkQueue](https://pkg.go.dev/k8s.io/client-go/tools/cache)
- [kubernetes-sigs/controller-runtime](https://pkg.go.dev/sigs.k8s.io/controller-runtime)
- [kubelet PLEG 与 syncPod（概念）](https://github.com/kubernetes/kubernetes/tree/master/pkg/kubelet)
