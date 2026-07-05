# 7. 工程实践：Mini Demo

> 一句话理解：**`gpu_scheduling_mini` 用一个纯 Python 进程把 Device Plugin 注册、kubelet 分配、scheduler Filter/Score/Reserve/Bind、MIG 调度、Gang all-or-nothing、拓扑感知打分、GPU 共享约束全部串起来跑通**——没有真实 GPU，但保留了所有关键语义。

## 7.1 为什么需要这个 Mini Demo

GPU 调度涉及多个组件跨节点/跨进程协作，真实环境排障成本高。Mini Demo 把核心机制压缩到一个 CPU 可运行的 Python 包里，让你可以：

- 单步跟踪“Pod 创建 → 调度 → Allocate → 容器可见 GPU”的完整链路。
- 用 `FakeClock` 把调度时间线精确复现。
- 在不接触真实集群的情况下验证 Gang、拓扑、MIG、共享等调度语义。
- 作为理解源码和写插件的“可运行草图”。

## 7.2 快速开始

```bash
cd docs/02-cloud-native/gpu-scheduling/mini-demo
pip install -e ".[dev]"          # 仅依赖 pytest，包本体零依赖
pytest tests/ -v                 # 44 个测试全绿
python -m gpu_scheduling_mini.demo  # 跑六个端到端场景
```

## 7.3 六个端到端场景

| 场景 | 演示的核心机制 | 对应真实组件 |
|---|---|---|
| **1. Device Plugin 注册与单卡分配** | Device Plugin 向 kubelet 注册，`sync_pod` 调用 `Allocate` 并注入 `NVIDIA_VISIBLE_DEVICES` | `kubelet` / `NVIDIA Device Plugin` |
| **2. Scheduler Filter/Score/Reserve/Bind** | 调度器按资源请求过滤节点、按 binpack/拓扑打分、绑定 Pod | `kube-scheduler` / `Scheduler Framework` |
| **3. MIG Profile 资源调度** | 按 `nvidia.com/mig-1g.5gb` 等 profile 过滤打分 | `NVIDIA MIG Device Plugin` |
| **4. PodGroup Gang 调度** | 资源不足时一个都不调，资源足够时原子绑定全部 Pod | `Volcano` / `scheduler-plugins Coscheduling` |
| **5. 拓扑感知打分** | 单节点 8-GPU 训练任务优先选择同 NUMA / PCIe / NVSwitch | `NodeResourceTopology` / GPU topology-aware scheduler |
| **6. GPU 共享约束** | MPS/time-slicing 抽象下，共享切片容量耗尽后拒绝新 Pod | `NVIDIA MPS` / `time-slicing` |

## 7.4 运行示例

```text
=== 场景 1：Device Plugin 注册与单卡分配 ===
Pod phase: Running
Allocated devices: {'train': [0]}
NVIDIA_VISIBLE_DEVICES=GPU-0000

=== 场景 2：Scheduler Filter/Score/Reserve/Bind ===
Schedule success: True
Pod bound to: node-2
Allocated devices: {'nvidia.com/gpu': [0, 1]}

=== 场景 3：MIG Profile 资源调度 ===
Schedule success: True
Pod bound to: mig-node
Allocated MIG devices: {'nvidia.com/mig-1g.5gb': [0, 1]}

=== 场景 4：PodGroup Gang 调度（all-or-nothing） ===
First attempt: ok=False, msg=pod gang-worker-1 has no feasible node
Second attempt: ok=True, msg=scheduled 2 pods

=== 场景 5：拓扑感知打分（单节点 8-GPU 训练） ===
Schedule success: True
Allocated GPUs: {'nvidia.com/gpu': [0, 1, 2, 3]}

=== 场景 6：GPU 共享约束（MPS/time-slicing） ===
Scheduled 10/10 shared pods on 1 GPU
Overflow pod correctly rejected

✅ 全部 6 个 GPU 调度场景通过
```

## 7.5 目录结构与模块对照

```text
gpu_scheduling_mini/
├── __init__.py          # 导出与真实组件对照表
├── clock.py             # Clock / FakeClock / RealClock
├── apiserver.py         # FakeApiServer：rv、乐观锁、generation、/status、watch
├── model.py             # Resources / GPU / Node / Pod / PodGroup / Queue
├── device_plugin.py     # NVIDIA Device Plugin 模拟
├── kubelet.py           # kubelet device-manager：sync_pod / delete_pod
├── scheduler.py         # Filter / Score / Reserve / Bind
├── topology.py          # NUMA / PCIe / NVSwitch 拓扑与打分
├── gang.py              # PodGroup all-or-nothing Gang 调度
└── demo.py              # 6 个端到端场景入口
```

| 本模块 | 真实组件 | 保留的核心语义 |
|---|---|---|
| `FakeApiServer` | `kube-apiserver` + `etcd` | resourceVersion、乐观锁、generation、/status 子资源、watch 事件流 |
| `DevicePlugin` | `NVIDIA Device Plugin` | registration、`ListAndWatch`、`Allocate`、health check、release |
| `Kubelet` | `kubelet` device-manager | `sync_pod` → Allocate → 注入 `NVIDIA_VISIBLE_DEVICES`；`delete_pod` 释放设备 |
| `Scheduler` | `kube-scheduler` + Scheduler Framework | Filter / Score / Reserve / Bind、binpack、MIG profile |
| `TopologyScorer` | Topology-aware GPU scheduling | NUMA / PCIe / NVSwitch 亲和性打分 |
| `GangScheduler` | `Volcano` / Coscheduling plugin | PodGroup `minMember`、all-or-nothing 原子预留与绑定 |

## 7.6 关键代码片段解读

### Device Plugin Allocate

```python
# gpu_scheduling_mini/device_plugin.py
def allocate(self, device_ids):
    indices = [int(x) for x in device_ids]
    for idx in indices:
        dev = self.devices.get(idx)
        if dev.health != "Healthy":
            raise DevicePluginError(f"device {idx} is unhealthy")
        if idx in self._allocated:
            raise DevicePluginError(f"device {idx} already allocated")
    for idx in indices:
        self._allocated.add(idx)
    return {
        "envs": {"NVIDIA_VISIBLE_DEVICES": ",".join(str(self.devices[idx].uuid) for idx in indices)},
        "mounts": [],
        "devices": [{"id": str(idx), "uuid": self.devices[idx].uuid} for idx in indices],
    }
```

真实 Allocate 返回的是 gRPC `ContainerAllocateResponse`，结构更复杂（包含 mounts、devices、envs），但核心语义完全一致：检查健康、去重、返回环境变量。

### Scheduler Filter / Score / Bind

```python
# gpu_scheduling_mini/scheduler.py
def schedule_one(self, pod):
    result = self.find_best_node(pod)   # Filter + Score
    if result is None:
        return False
    node_name, indices, rtype, _ = result
    return self.assign(pod, node_name, indices, rtype)  # Reserve + Bind
```

这里的 `assign` 做了真实调度器里 `Reserve` + `Bind` 两件事：先在节点上分配设备，再把 `pod.spec.nodeName` 写回 apiserver。

### Gang 调度的两阶段提交

```python
# gpu_scheduling_mini/gang.py
def schedule_group(self, pod_group):
    for pod in pods:
        result = self.scheduler.find_best_node(pod)
        if result is None:
            self._rollback(committed)
            return False, "..."
        ok = self.scheduler.assign(pod, node_name, indices, rtype)
        if not ok:
            self._rollback(committed)
            return False, "..."
        committed.append(pod)
    return True, "scheduled"
```

这就是 Volcano / Coscheduling 的核心思想：**不是逐个提交，而是全部检查通过后再统一提交；中途失败就全部回滚**。

## 7.7 测试覆盖

共 44 个 pytest 用例，覆盖：

- `Clock` / `FakeClock` 步进与单调性
- `FakeApiServer` 的 rv、乐观锁、generation、status 子资源、watch 事件流
- `DevicePlugin` 注册、Allocate（互异设备索引）、health check、release
- `Kubelet` 整卡与 MIG 分配、环境变量注入、删除释放、跨节点拒绝
- `Scheduler` Filter / Score / Reserve / Bind、binpack、MIG profile、共享切片
- `TopologyScorer` NUMA / PCIe / NVSwitch 亲和性
- `GangScheduler` PodGroup all-or-nothing、资源不足时拒绝、成功时原子绑定
- `demo.py` 全部 6 个场景主入口

## 7.8 诚实的边界

本 Mini Demo 故意只保留教学所需的最小语义，以下真实复杂度被省略：

1. **没有真实 GPU**：设备索引只是整数 UUID，不访问 `/dev/nvidia*` 或驱动。
2. **没有 gRPC/HTTP**：所有调用都是本地 Python 方法调用。
3. **没有并发**：单线程、同步执行；真实 kube-scheduler 和 kubelet 都是高度并发的。
4. **没有抢占/重调度**：Pod 一旦绑定就不会被赶走。
5. **MIG/共享模型化简**：只保留 profile 名称与容量计数，未模拟真实 MIG geometry 或 MPS 守护进程。
6. **拓扑静态化**：拓扑由构造参数一次性给出，未模拟热插拔或动态 NVLink 探测。

这些省略不会妨碍理解 GPU 调度的核心概念与数据流；在真实集群里，这些语义被相同的 API 调用序列执行。

## 7.9 本章小结

Mini Demo 把本章之前学到的所有概念串成了一条可执行的链路：

```text
Pod → apiserver → scheduler(Filter/Score/Reserve/Bind) → kubelet → DevicePlugin.Allocate → 容器启动
```

同时它也是一个可扩展的骨架：你可以在上面增加显存感知调度、自定义拓扑策略、抢占、队列等实验，而不用改动生产集群。

## 7.10 进一步阅读

- 机制基础见 [第 2 章 核心思想](02-core-ideas) 与 [第 3 章 架构设计](03-architecture)。
- 完整流程见 [第 4 章 调度工作流程](04-scheduling-workflow)。
- 模块细节见 [第 5 章 核心模块](05-core-modules)。
- 源码入口见 [第 6 章 源码分析](06-source-analysis)。
- 生产落地见 [第 8 章 企业生产实践](08-production-practice) 与 [第 9 章 最佳实践](09-best-practices)。
