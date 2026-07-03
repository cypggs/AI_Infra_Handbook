"""operator_mini —— 用纯标准库从零实现的 Kubernetes Operator 教学模拟器。

把 controller-runtime 的核心机制在一个进程里重建出来，对应关系：

    本模块            controller-runtime / K8s
    ────────────────  ─────────────────────────────────
    model.py          CRD 定义（InferenceService/Deployment/Service 资源模型）
    apiserver.py      kube-apiserver + etcd（乐观并发、generation、finalizer、级联 GC、watch 事件流）
    informer.py       client-go SharedInformer（List + Watch → 本地缓存 → EventHandler）
    workqueue.py      client-go workqueue（去重 + 指数退避 + 延迟重排）
    controller.py     controller-runtime Controller（Source→Handler→Queue→Reconciler 流水线）
    reconciler.py     开发者写的 Reconcile 业务逻辑（level-triggered / 幂等 / 不阻塞）
    platform.py       K8s 内置 Deployment Controller（模拟 Pod 模型加载延迟，让 readyReplicas 随时间推进）
    demo.py           端到端场景演示

整个系统是单线程、可步进的确定性模拟：用 FakeClock 替代真实时间，于是第 4 章描述的
"t=0 patch → reconcile #1 → t=5 reconcile #2 → t=10 reconcile #3 收敛" 的时间线可以精确复现。
"""
