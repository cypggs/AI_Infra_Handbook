# 7. Mini-Demo：用 300 行 Python 复刻 Kubernetes 核心机制

> 一句话理解：我们在一个单进程、确定性、零依赖的 Python 模拟器里，把 Kubernetes 的**调度框架、Device Plugin、控制器滚动升级、Gang 调度**四大机制跑给你看——没有真实集群，但每个设计权衡都是真的。

前面六章我们把 Kubernetes 从"设计动机 → 架构 → 源码"讲透了。但 Kubernetes 的精髓是**动态行为**：资源怎么被预占又回滚、滚动升级怎么一步步收敛、Gang 调度为什么"要么全成要么全败"。这些用文字描述总隔着一层。本章的 Mini-Demo 把这些动态过程变成**可运行、可断言、可反复重现**的代码，让你用 0.04 秒看明白真实集群要花几分钟才能观察到的东西。

> 配套代码位于 `docs/02-cloud-native/kubernetes/mini-demo/`，`README.md` 有完整运行说明，`tests/` 有 56 个通过的 pytest 用例。

## 7.1 为什么不用真实集群做演示

教学演示最"真实"的选择当然是起一个 minikube/kind 集群。但对**理解机制**而言，真实集群反而是糟糕的媒介：

| 问题 | 真实集群 | 本模拟器 |
|---|---|---|
| 环境门槛 | 要装 Docker/虚拟化、拉镜像、配 CNI | `python -m k8s_mini.demo` 即可 |
| 观测 | 要 `kubectl describe`、翻事件、看日志 | 每个 tick 的状态变化直接打印 |
| 时序 | 控制循环异步、并发、毫秒级交错 | 单线程串行，每步可见 |
| 确定性 | 调度顺序受负载/时间影响 | 无随机数，反复运行结果完全一致 |
| 成本 | 起一个 GPU 集群要钱、要卡 | CPU 即可，0 额外成本 |
| 可断言 | 写 e2e 测试要几分钟跑一次 | pytest 0.04 秒跑完 56 例 |

真实集群教会你**操作**，模拟器教会你**原理**。本章属于后者——当你能在模拟器里预测每一步的输出，再去操作真实集群时，你会在 `kubectl describe` 的每一行里看到熟悉的状态机。

## 7.2 整体设计：一个 tick 驱动的单线程控制循环

真实 Kubernetes 是多个**独立并发**的控制平面组件（apiserver/etcd/scheduler/controller-manager/kubelet）通过共享状态（etcd + watch）协作。本模拟器**保留了协作关系，去掉了并发**：用一个 `tick`（时钟周期）串行驱动所有组件，每个 tick 内按固定顺序收敛一次。

```python
# demo.py — MiniCluster.run()：一个 tick 的执行顺序
def run(self, ticks: int = 5) -> None:
    for _ in range(ticks):
        # 1. 控制器先跑：根据 Deployment/ReplicaSet 的"期望状态"创建/删除 Pod
        self.depc.reconcile()      # DeploymentController：管理新旧 RS，滚动升级
        self.rsc.reconcile()       # ReplicaSetController：维持副本数 + 级联 GC
        # 2. 调度器把 Pending Pod 绑定到节点（Filter → Score → Reserve → Bind）
        self.scheduler.run_once()
        # 3. 各节点 kubelet 启动已绑定 Pod、跑探针、分配 GPU、上报状态
        for kl in self.kubelets.values():
            kl.reconcile(self.tick)
        self.tick += 1
```

这个执行顺序**忠实反映了真实 K8s 的因果链**：控制器产出 Pod → 调度器决定节点 → kubelet 落地运行。区别只是真实集群里这三者是并发 + watch 驱动的，而这里用 tick 把它们排成队，让因果一目了然。

### 模块与真实组件的对应

| 模拟器模块 | 真实组件 | 关键职责 |
|---|---|---|
| `store.py` | etcd | 唯一真相源；`add_watcher` = informer 的 list+watch |
| `apiserver.py` | kube-apiserver | CRUD + Mutating/Validating 准入链 |
| `scheduler.py` | kube-scheduler | 调度框架核心扩展点 + Gang + 抢占 |
| `device_plugin.py` | NVIDIA Device Plugin | 上报 `nvidia.com/gpu` 容量 + Allocate |
| `kubelet.py` | kubelet | PLEG + syncPod + 探针 |
| `controller.py` | controller-manager | ReplicaSet/Deployment reconcile + 滚动 |

## 7.3 机制一：调度框架（Filter / Score / Reserve / Bind）

这是整个模拟器最有教学价值的部分。真实 K8s 的调度框架有 12 个扩展点（见第 5 章），本模拟器实现了其中最核心的几个，且**结构上完全对应**——`_schedule_one` 就是 `scheduleOne` 的缩影：

```python
# scheduler.py — 单 Pod 调度，对应 kube-scheduler 的 scheduleOne
def _schedule_one(self, pod: Pod) -> None:
    req = pod.total_request                          # PreFilter：算总请求
    feasible = self._filter_nodes(pod, req)          # Filter：NodeResourcesFit/NodeAffinity/TaintToleration
    if not feasible:
        if self.config.enable_preemption:
            node = self._try_preempt(pod, req)       # PostFilter：抢占
            if node is not None:
                self._reserve_and_bind(pod, node)
        return
    node = self._score(pod, feasible)                # Score：binpack/spread/balanced
    self._reserve_and_bind(pod, node)                # Reserve → Bind
```

三种打分策略精确对应真实 K8s 的评分插件：

```python
def _score(self, pod, feasible):
    if self.config.strategy == "spread":
        # LeastAllocated + SelectorSpread：偏好剩余容量多的节点（打散）
        return max(feasible, key=lambda n: (n.allocatable.cpu + n.allocatable.memory, n.name))
    if self.config.strategy == "balanced":
        # NodeResourcesBalancedAllocation：放进去后 cpu/mem 利用率最接近
        return max(feasible, key=lambda n: -abs(cpu_ratio(n) - mem_ratio(n)))
    # 默认 binpack：MostAllocated：偏好已用最多的节点（装箱，提高密度）
    return max(feasible, key=lambda n: (n.allocated.cpu + n.allocated.memory, n.name))
```

**运行场景 1**（3 个 Pod × 3 个等量节点），两种策略产生截然不同的落点：

```
binpack 分布: {'node-a': 0, 'node-b': 0, 'node-c': 3}   ← 全聚到一个节点（密度）
spread  分布: {'node-a': 1, 'node-b': 1, 'node-c': 1}   ← 打散到不同节点（容错）
```

**为什么这个对比有教学价值**：它直观展示了 K8s 默认 `MostAllocated`（binpack 倾向）和 AI 场景常配的 `LeastAllocated`（spread）的本质差异——前者省机器（适合在线服务），后者抗故障（适合有状态/训练）。AI 平台常在 GPU 节点上**关闭 binpack**，避免单节点故障打掉太多训练 worker。

`_reserve_and_bind` 还演示了 **Reserve 扩展点**的回滚语义：资源先预占，绑定失败时 `Unreserve` 释放——这是 Gang 调度 all-or-nothing 能成立的基础。

## 7.4 机制二：Device Plugin + GPU 调度

真实 K8s 里 GPU 是"扩展资源"，不是内置的。它的容量来自 Device Plugin 的上报，分配发生在 kubelet 的 syncPod。模拟器复刻了这条链：

```python
# device_plugin.py — 注册即把容量并入节点
def register(self, node: Node) -> None:
    node.capacity.gpu += self.gpu_count              # ListAndWatch 上报 nvidia.com/gpu
    node.labels.setdefault("nvidia.com/gpu.present", "true")

# kubelet.py — syncPod 时分配具体设备
def _sync_pod(self, pod, node, tick):
    gpu_req = pod.total_request.gpu
    if gpu_req > 0 and self.gpu_plugin is not None:
        idx = self.gpu_plugin.allocate(gpu_req)      # Allocate gRPC：返回设备索引
        pod.gpu_devices = list(idx)                  # 等价于注入 NVIDIA_VISIBLE_DEVICES
```

`MiniCluster.add_node` 故意**不直接给 Node 传 gpu 容量**，而是让 Device Plugin 注册时上报——这正是真实 K8s 的行为（`node.status.capacity` 里的 `nvidia.com/gpu` 是 kubelet 通过 Device Plugin 报上去的，不是用户写的）。这个细节如果省掉，会让学生误以为 GPU 是"自带"的资源。

**运行场景 2**（2 个 GPU 节点各 2 卡，3 个 vLLM Pod 各要 1 卡）：

```
vllm-0 → gpu-node-2 (Running), GPU devices allocated=[0]
vllm-1 → gpu-node-2 (Running), GPU devices allocated=[1]
vllm-2 → gpu-node-1 (Running), GPU devices allocated=[0]
节点剩余 GPU: {'gpu-node-1': 1, 'gpu-node-2': 0}
```

注意每个 Pod 拿到的**设备索引互不相同**——这正是 Device Plugin `Allocate` 的核心保证：GPU 默认整卡独占（除非用 MIG/MPS），两个 Pod 不会分到同一张卡。

## 7.5 机制三：控制器滚动升级 + 自愈

这是模拟器里**逻辑最绕、调试最久**的部分，也最能体现"水平触发 + 期望状态"的威力。`DeploymentController._reconcile_deployment` 实现了真实的滚动升级算法：

```python
# controller.py — 滚动升级：先 surge（增新）再 drain（缩旧）
def _reconcile_deployment(self, dep):
    # 1. 模板指纹变了 → 创建新 RS（真实 K8s 用 pod-template-hash）
    desired_hash = _template_hash(dep)
    current = ensure_rs_with_hash(dep, desired_hash)
    new_rs, old_rs = current, [...]; 

    # 2. Surge：新 RS 增长，受 (replicas + maxSurge - old_replicas) 上限约束
    surge_cap = dep.replicas + dep.max_surge - old_replicas
    target_new = min(dep.replicas, max(0, surge_cap))
    if new_rs.replicas < target_new:
        new_rs.replicas += 1                        # 每 tick +1（模拟渐进）

    # 3. Drain：新 RS 就绪数足够维持 (replicas - maxUnavailable) 可用时，才缩旧
    if old_rs and new_ready > 0 \
            and (new_ready + old_ready - 1) >= dep.replicas - dep.max_unavailable:
        victim_rs = max(old_rs, key=lambda r: (r.replicas, r.name))
        victim_rs.replicas -= 1                     # 每 tick -1

    # 4. 旧 RS 缩到 0 → 删除（真实 K8s 保留 revision 供回滚）
    for rs in old_rs:
        if rs.replicas == 0:
            self.api.delete_replicaset(rs.name)
```

关键约束 `maxSurge` / `maxUnavailable` 决定了滚动是"先增后删"（默认 `1/0`，最稳妥，永远不低于期望副本数）。**运行场景 3**（replicas=3，v1→v2）的收敛过程：

```
v1 阶段 Pod: ['web-...-0', 'web-...-1', 'web-...-2']        ← 模板指纹 abc
v2 阶段 Pod: ['web-...-0', 'web-...-1', 'web-...-2']        ← 模板指纹 xyz（新 RS）
滚动后镜像: {'web-...-0': 'app:v2', ...} 全部 v2
自愈: 删除前 running=3 → 补齐后 running=3
```

实现中踩过两个真实控制器的坑，值得点名：

1. **孤儿 Pod**：旧 RS 被删到 0 后删除，但它名下的 Pod 没人管了，变成孤儿。真实 K8s 用 owner-reference + garbage collector 解决；模拟器加了 `_garbage_collect_orphan_pods()`——删除 `owner_rs` 指向已不存在 RS 的 Pod。没有这步，滚动会"看似完成"但残留一堆旧 Pod。

2. **滚动条件错误**导致反复抖动（flapping）：最初用 `if available_new >= 1 and total > replicas or new_rs.replicas >= replicas` 这种复合条件，新旧 RS 来回增减。正确做法是**用就绪计数**显式表达 `maxSurge`/`maxUnavailable` 约束，每 tick 只做一次最小动作。这正是水平触发的精髓——不看历史，只看当前期望与实际的差值。

**自愈**演示更简单：删掉一个 v2 Pod，`ReplicaSetController.reconcile` 发现 `replicas - running = 1`，立即创建一个补齐——这正是 K8s "声明期望状态，控制器负责收敛"的核心契约。

## 7.6 机制四：Gang 调度（all-or-nothing）

分布式训练（DDP/FSDP/Megatron）要求所有 worker 同时启动，否则先起来的会卡在 `init_process_group` 等同伴，最终超时失败。Gang 调度就是"要么全部调度成功，要么一个都不调度"。模拟器复刻了 v1.36 原生 PodGroup（KEP-4671）/ Volcano 的核心逻辑：

```python
# scheduler.py — _schedule_gang：先全部 Reserve，够法定数才 Bind，否则全回滚
def _schedule_gang(self, members):
    min_available = members[0].gang_min_available
    reserved = []
    for p in sorted(members, key=lambda p: (-p.priority.value, p.name)):  # 确定性
        if len(reserved) >= min_available:
            break
        feasible = self._filter_nodes(p, p.total_request)
        if not feasible:
            continue
        node = self._score(p, feasible)
        node.allocate(p.total_request)              # Reserve：预占，不 Bind
        reserved.append((p, node))

    if len(reserved) >= min_available:
        for p, node in reserved:
            self._bind(p, node)                     # Permit 放行：全部绑定
    else:
        for p, node in reserved:
            node.release(p.total_request)           # Unreserve：回滚所有预占
```

**运行场景 4**（两个 gang：`gang-ok` 资源够，`gang-fail` 资源不够）：

```
各 gang 状态: {'gang-ok': '2/2 scheduled', 'gang-fail': '0/3 scheduled'}
gang-ok  已调度: 2（应=2，全部成功）
gang-fail 已调度: 0（应=0，资源不足整体拒绝）
```

最关键的断言是 `gang_fail` 失败后**节点资源被完整回滚**（`node.allocated` 回到 0）——这正是 all-or-nothing 的难点：不是"调一部分"，而是"预占失败就把已占的还回去"，避免资源碎片化卡死后续 gang。`test_gang.py::test_gang_all_or_nothing_with_rollback` 专门验证了这一点。

> 这也解释了为什么 K8s 社区从 Volcano/scheduler-plugins 的"外挂调度器"方案，演进到 v1.36 的**原生 PodGroup**——all-or-nothing 涉及 Reserve/Unreserve 的资源生命周期，必须由主调度器统一管理，外挂调度器很难做对（详见第 1、5 章）。

## 7.7 测试：把演示输出变成可回归的契约

56 个 pytest 用例不只是"跑通"，而是把每个机制的关键不变量固化为**契约**。例如：

```python
# test_scheduler.py — binpack 必须聚到一个节点
def test_binpack_packs_pods_onto_one_node():
    ...
    assert max(counts.values()) == 3              # 全在一个节点
    assert sum(1 for c in counts.values() if c > 0) == 1

# test_gang.py — all-or-nothing + 资源回滚
def test_gang_all_or_nothing_with_rollback():
    ...                                           # 单节点 2 核，gang 要 3 个 1 核 worker
    assert status["gang-bad"] == "0/3 scheduled"
    assert (node.allocated.cpu, node.allocated.memory) == (0, 0)  # 回滚

# test_controller.py — 滚动必须全部收敛到 v2
def test_rollout_converges_to_new_image():
    ...
    assert all(p.containers[0].image == "app:v2" for p in running)
```

为什么这很重要：当你将来改动模拟器（比如加 `balanced` 评分、加 `PriorityClass` 抢占策略），`pytest` 会立刻告诉你有没有破坏已有机制。这就是**测试即文档**——断言比注释更可靠。

```bash
$ pytest tests/ -q
........................................................                 [100%]
56 passed in 0.04s
```

## 7.8 模拟器与真实集群的本质差异（诚实的边界）

为避免过度自信，必须讲清模拟器**故意省略**了什么：

| 维度 | 模拟器 | 真实集群 | 为什么省略 / 影响 |
|---|---|---|---|
| **并发** | 单线程串行 tick | apiserver/etcd/scheduler/kubelet 各自并发 | 省略后失去了"乐观并发 + 重试"的复杂性，但真实 etcd 事务、scheduler 乐观锁（`resourceVersion`）无法体现 |
| **网络** | 伪造 Pod IP 字符串 | CNI 真实组网、kube-proxy 转发 | Service/EndpointSlice/Ingress 的网络行为完全没模拟 |
| **容器运行时** | 不起任何容器 | CRI（containerd）真正拉镜像、起进程 | "启动延迟"用 `startup_ticks` 近似，真实还有镜像拉取、cgroup 设置 |
| **持久化** | 进程结束即丢 | etcd 强一致持久化 | 重启即全新，无法演示"节点重启后状态恢复" |
| **一致性** | 每步同步完成 | 最终一致（多循环异步收敛） | 真实 K8s 的"抖动期"（多个控制器短暂不一致）看不到 |
| **调度吞吐** | 一次调一个 | 批量、队列、优先级队列 | 无法体现 QueueSort 扩展点和调度吞吐优化 |

**结论**：模拟器是理解 K8s **机制与设计权衡**的最佳工具，但它**不能替代**真实集群的操作经验和故障排查直觉。学完本章后，强烈建议在 kind/minikube 上把同样的 Deployment/GPU Job 跑一遍，对照 `kubectl describe` 的输出与模拟器的 trace，你会对两者都有更深的理解。

## 本章小结

本章用 `docs/02-cloud-native/kubernetes/mini-demo/` 这个约 300 行核心逻辑的模拟器，把前六章的抽象概念变成了**可运行、可断言、可重现**的动态过程。四个机制各对应一个演示场景与一组测试：**调度框架**（Filter/Score/Reserve/Bind 三策略 + 抢占）、**Device Plugin/GPU**（扩展资源上报与独占分配）、**控制器滚动升级**（maxSurge/maxUnavailable + 级联 GC + 自愈）、**Gang 调度**（all-or-nothing + 资源回滚）。模拟器通过"单线程 tick 驱动"保留了真实 K8s 的因果链与设计权衡，同时用确定性换取了可教学、可测试的清晰时序。它的价值不在"替代真实集群"，而在让你在 0.04 秒内看明白真实集群要几分钟才能观察到的动态收敛——当你能在模拟器里预测每一步，真实集群的每一次 `kubectl describe` 都会变得可读。

**参考来源**

- 本手册配套代码：`docs/02-cloud-native/kubernetes/mini-demo/`（含 `README.md` 与 56 个测试）
- [Kubernetes Scheduling Framework（概念）](https://kubernetes.io/zh-cn/docs/concepts/scheduling-eviction/scheduling-framework/)
- [KEP-4671 Gang Scheduling / PodGroup](https://github.com/kubernetes/enhancements/tree/master/keps/sig-scheduling/4671-foo)
- [NVIDIA GPU Operator 与 Device Plugin 文档](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/overview.html)
- [Volcano Gang Scheduling 设计](https://volcano.sh/en/docs/v1.9.0/scheduling_algorithm/#gang-scheduling)
