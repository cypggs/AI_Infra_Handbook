# gpu-scheduling-mini

一个纯 Python 标准库实现的 Kubernetes GPU 调度教学模拟器，对应 [AI Infra Handbook —— GPU 在 Kubernetes 上的调度](../index.md) 第 7 章。

## 快速开始

```bash
cd docs/02-cloud-native/gpu-scheduling/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m gpu_scheduling_mini.demo
```

## 端到端场景

| 场景 | 说明 | 对应真实组件 |
|------|------|--------------|
| 1. Device Plugin 注册与单卡分配 | NVIDIA Device Plugin 向 kubelet 注册并分配整卡 | `kubelet` / `device-plugin` |
| 2. Scheduler Filter / Score / Reserve / Bind | 调度器扩展点：过滤 → 打分 → 预留 → 绑定 | `kube-scheduler` / `Scheduler Framework` |
| 3. MIG Profile 资源调度 | 按 `nvidia.com/mig-1g.5gb` 等 profile 过滤打分 | `NVIDIA MIG Device Plugin` |
| 4. PodGroup Gang 调度 | Volcano 风格 all-or-nothing 调度 | `Volcano` / `Scheduler Plugins Coscheduling` |
| 5. 拓扑感知打分 | 单节点 8-GPU 训练任务优先选择同 NUMA / PCIe / NVSwitch | `GPU Topology Awareness` / `DCGM` |
| 6. GPU 共享约束 | MPS / time-slicing 共享下的显存与并发限制 | `NVIDIA MPS` / `time-slicing` |

## 目录结构

```
mini-demo/
├── pyproject.toml
├── README.md
├── conftest.py
├── gpu_scheduling_mini/
│   ├── __init__.py          # 导出与真实组件对照表
│   ├── clock.py             # 可注入时间源（FakeClock / RealClock）
│   ├── apiserver.py         # FakeApiServer：rv、乐观锁、generation、/status、watch
│   ├── model.py             # Resources / GPU / Node / Pod / PodGroup / Queue
│   ├── device_plugin.py     # NVIDIA Device Plugin 模拟
│   ├── kubelet.py           # kubelet device-manager 与 Pod 生命周期
│   ├── scheduler.py         # Filter / Score / Reserve / Bind
│   ├── topology.py          # NUMA / PCIe / NVSwitch 拓扑与打分
│   ├── gang.py              # PodGroup all-or-nothing Gang 调度
│   └── demo.py              # 6 个端到端场景入口
└── tests/
    ├── test_clock.py
    ├── test_apiserver.py
    ├── test_device_plugin.py
    ├── test_kubelet.py
    ├── test_scheduler.py
    ├── test_topology.py
    ├── test_gang.py
    └── test_demo.py
```

## 与真实组件对照

| 本模块 | 真实 K8s / NVIDIA 组件 | 保留的核心语义 |
|--------|------------------------|----------------|
| `clock.FakeClock` | 系统 wall-clock | 时间可步进、可复现 |
| `apiserver.FakeApiServer` | `kube-apiserver` + `etcd` | resourceVersion、乐观锁、generation、/status 子资源、watch 事件流 |
| `model.Resources` | `ResourceRequirements` | requests / limits、`nvidia.com/gpu`、`nvidia.com/mig-*` |
| `device_plugin.DevicePlugin` | `NVIDIA Device Plugin` | registration、`ListAndWatch`、`Allocate`、`PreStartContainer`、health check、release |
| `kubelet.Kubelet` | `kubelet` device-manager | `sync_pod` → Allocate → 注入 `NVIDIA_VISIBLE_DEVICES`；`delete_pod` 释放设备 |
| `scheduler.Scheduler` | `kube-scheduler` + Scheduler Framework | Filter / Score / Reserve / Bind、binpack / spread、MIG profile |
| `topology.TopologyScorer` | Topology-aware GPU scheduling | NUMA / PCIe / NVSwitch 亲和性打分 |
| `gang.GangScheduler` | `Volcano` / Coscheduling plugin | PodGroup `minMember`、all-or-nothing 原子预留与绑定 |

## 测试覆盖

共 44 个 pytest 用例，覆盖：

- `Clock` / `FakeClock` 步进
- `FakeApiServer` 的 rv、乐观锁、generation、status 子资源、watch 事件流
- `DevicePlugin` 注册、Allocate（互异设备索引）、health check、release
- `Kubelet` 整卡与 MIG 分配、环境变量注入、删除释放
- `Scheduler` Filter / Score / Reserve / Bind、binpack / spread、MIG profile
- `TopologyScorer` NUMA / PCIe / NVSwitch 亲和性
- `GangScheduler` PodGroup all-or-nothing、资源不足时拒绝、成功时原子绑定
- `demo.py` 全部 6 个场景主入口

## 诚实的边界

- **单线程模拟**：没有真实 gRPC / HTTP，所有组件运行在一个 Python 进程内。
- **无真实 GPU**：设备索引只是整数 UUID，不访问 `/dev/nvidia*` 或驱动。
- **简化调度周期**：Scheduler 是同步循环，未实现抢占、重调度、多调度器 leader 选举。
- **MIG / 共享模型化简**：只保留 profile 名称与容量计数，未模拟真实 MIG geometry 或 MPS 守护进程。
- **拓扑静态化**：拓扑由构造参数一次性给出，未模拟热插拔或动态 NVLink 探测。

## 返回章节

- [第七章：Mini Demo](../07-mini-demo.md)
- [第二章：核心概念](../02-core-ideas.md)
- [第八章：生产实践](../08-production-practice.md)
