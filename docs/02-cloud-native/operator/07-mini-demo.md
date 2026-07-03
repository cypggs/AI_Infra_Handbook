# 7. Mini-Demo：用纯 Python 从零实现一个 Operator

> 一句话理解：理论读再多不如自己造一个——本章带你看完一个**零依赖、纯标准库、单进程**的 Kubernetes Operator 模拟器（`operator-mini`），它在一块代码里把前六章讲的全部机制（CRD、乐观并发、generation、/status 子资源、finalizer、级联 GC、Informer 缓存、Workqueue 去重退避、level-triggered Reconcile、漂移自愈）真实跑通，37 个测试守护，并用 `FakeClock` 精确复现第 4 章的收敛时间线。

## 7.1 为什么写这个 Demo

Operator 的难点不在任何单点，而在**机制如何咬合**：乐观并发怎样保证"读后写"安全、generation 怎样让 Controller 区分 spec 与 status 变更、finalizer 与 owner reference 怎样分工完成删除、Workqueue 去重怎样扛住事件风暴、Reconcile 怎样用 RequeueAfter 实现"不阻塞的等待"。

这些机制分散在 controller-runtime 几十万行 Go 代码里，初学者很难看清主干。`operator-mini` 把主干抽出来，**只保留控制平面语义**（这是 Operator 模式的本质），简化掉分布式系统工程（HTTP/etcd/鉴权/网络——那是 K8s 的事）。读完你能：

- 像读一段代码一样**追踪一次 Reconcile 的完整旅程**（对应第 4 章）。
- 理解每条"铁律"在代码里**具体怎么落地**，违反会怎样。
- 把这个模型**直接迁移**到理解真实 Operator（KubeRay 等）的源码。

## 7.2 场景：GPU 推理服务 Operator

Demo 实现一个 `InferenceService` Operator（贴近 KServe / vLLM Operator 的最小内核）：

> 用户声明一个 `InferenceService`（镜像 + 副本数 + 模型名），Operator 持续保证集群里有一个匹配的 `Deployment` + `Service`，并报告 Ready 状态；删除时先清理外部资源（注销云 LB）再级联删子资源。

```python
from operator_mini import model
is_obj = model.make_inference_service("llama", image="vllm:0.6.3", replicas=4, model="Llama-3")
apiserver.create(is_obj)
controller.run_until_quiescent()
# → 自动创建 Deployment + Service，多轮收敛后 status.ready = True
```

## 7.3 目录与模块映射

```
operator_mini/
├── model.py       # CRD 资源模型（InferenceService/Deployment/Service + 辅助函数）
├── apiserver.py   # FakeApiServer：乐观并发/generation//status/finalizer/级联GC/watch 事件流
├── informer.py    # SharedInformer：List+Watch→缓存；enqueue_self(For)/enqueue_owner(Owns)
├── workqueue.py   # RateLimitingQueue：去重 + add_after + add_rate_limited；Clock(Real/Fake)
├── platform.py    # 模拟内置 Deployment Controller：Pod readyReplicas 随时间推进
├── controller.py  # Controller：Source→Handler→Queue→Reconciler；step() + run_until_quiescent()
├── reconciler.py  # InferenceServiceReconciler：四条铁律全落地的业务逻辑
└── demo.py        # 装配 + 四个端到端场景
```

每个模块和 controller-runtime 一一对应（完整对照表见 `docs/02-cloud-native/operator/mini-demo/README.md`）。

## 7.4 关键代码：FakeApiServer 的四件"易被忽略的语义"

教学时常把 apiserver 当黑盒，但 Operator 的正确性恰恰建立在 apiserver 的四个语义上。Demo 把它们显式实现：

**① 乐观并发**——update 必须带"读到的" resourceVersion：

```python
def update(self, obj):
    cur = self._store.get(model.key(obj))
    if obj["metadata"].get("resourceVersion") != cur["metadata"]["resourceVersion"]:
        raise Conflict("resourceVersion mismatch (optimistic lock)")   # → Reconciler 报错 → 退避重试
```

**② generation**——spec 变才 +1（让 Controller 区分"用户改 spec"和"我自己写 status"）：

```python
spec_changed = obj.get("spec") != cur.get("spec")
obj["metadata"]["generation"] = cur["metadata"]["generation"] + (1 if spec_changed else 0)
```

**③ /status 子资源**——单独写入路径，独立 rv，**不 bump generation**（否则写 status → 触发 reconcile → 又写 status，死循环）：

```python
def update_status(self, obj):
    # 校验 rv，写 status，bump rv，但不改 generation
    cur["status"] = obj["status"]; self._emit("MODIFIED", cur)
```

**④ finalizer + 级联 GC**——有 finalizer 只设 deletionTimestamp；最后一个 finalizer 移除（且在删除中）才真删；删除时递归 GC controller 子资源：

```python
# update() 末尾：
if is_being_deleted(obj) and not obj["metadata"]["finalizers"]:
    del self._store[k]; self._emit("DELETED", obj); self._gc_children(obj)  # 递归删子资源
```

## 7.5 关键代码：Reconcile 的四条铁律逐条落地

```python
def reconcile(self, kind, namespace, name):
    is_obj = self.is_informer.get(kind, namespace, name)
    if is_obj is None:
        return {}, None                                  # level-triggered：CR 没了就没事

    if is_being_deleted(is_obj):
        return self._reconcile_delete(is_obj)            # finalizer 删除分支

    if not has_finalizer(is_obj):
        add_finalizer(is_obj); self.apiserver.update(is_obj)
        return {"requeue": True}, None                   # 幂等：第一次加，之后跳过

    svc = self.svc_informer.get(SERVICE_KIND, namespace, name)   # 读现状（缓存）
    dep = self.deploy_informer.get(DEPLOYMENT_KIND, namespace, name)
    svc = self._reconcile_service(is_obj, svc)           # 先 Get 再 Create/Patch —— 幂等
    dep = self._reconcile_deployment(is_obj, dep)

    ready = dep["status"].get("readyReplicas", 0)
    new_status = {"observedGeneration": is_obj["metadata"]["generation"], "readyReplicas": ready, ...}
    if is_obj["status"] != new_status:
        is_obj["status"] = new_status
        self.apiserver.update_status(is_obj)             # /status 子资源
    if ready < is_obj["spec"]["replicas"]:
        return {"requeue_after": self.ready_after}, None # 不阻塞：稍后再看
    return {}, None                                      # 收敛
```

- **level-triggered**：每次从缓存读全量算 diff，不依赖事件序列；CR 不存在直接返回。
- **幂等**：子资源先 Get 再决定 Create/Patch；状态没变不写 status（`!= new_status` 守卫）。
- **不阻塞**：Pod 没 ready 时返回 `requeue_after`，绝不在 reconcile 里 sleep。
- **乐观**：写靠 apiserver 的 rv 锁；Conflict 抛错 → Controller 退避重试。

## 7.6 关键代码：Workqueue 与 Requeue 语义

```python
key = self.queue.get()                      # 只返回已到期项
result, err = self.reconciler.reconcile(*key)
self.queue.done(key)
if err is not None:
    self.queue.add_rate_limited(key)        # 指数退避：5→10→20→…→1000
elif result.get("requeue_after"):
    self.queue.forget(key); self.queue.add_after(key, result["requeue_after"])  # 定时重排
elif result.get("requeue"):
    self.queue.add(key)                     # 立即重排（少用）
else:
    self.queue.forget(key)                  # 收敛
```

这与第 6.4 节 controller-runtime 源码 `processNextWorkItem` 的 switch 分支**逐行对应**。

## 7.7 复现第 4 章的收敛时间线

Demo 用 `FakeClock`，于是"扩容 + 升级"的三次 reconcile 能精确打印成时间线（与第 4.8 节一模一样）：

```
场景 2：扩容 + 升级（replicas 2→4, image 0.6.3→0.7.0）
[   5.0s] patched Deployment llama (image=vllm:0.7.0, replicas=4)
[   5.0s] status gen=2 ready=2/4 observedGen=2     # reconcile #1：patch 完，新 Pod 还没 ready
[  10.0s] status gen=2 ready=4/4 observedGen=2     # reconcile #3：Pod ready，收敛
```

`run_until_quiescent` 的循环逻辑就是这套语义的驱动器：调和到没有到期项时，若队列还有延迟项，就把 `FakeClock` 推进到最近的到期时刻（对应真实集群里"时间自然流逝"），再继续。

## 7.8 四个场景验证的能力

| 场景 | 验证的能力 | 关键断言 |
|---|---|---|
| 创建 | 自动建子资源 + 多轮收敛 | `status.ready == True`, `readyReplicas == 2` |
| 扩容+升级 | spec 变 → generation +1 → observedGeneration 追上 → 收敛 | `observedGeneration == 2`, `reconcile_total > 1` |
| 删除 | finalizer 清理 + 级联 GC | CR/Deployment/Service 全部消失，`cleanup_calls == 1` |
| 漂移自愈 | Owns 事件回流 + level-triggered 纠偏 | 手改 replicas=99 → 被纠回 3 |

## 7.9 测试结果

```bash
$ pytest tests/ -v
============================== 37 passed in 0.04s ==============================
```

测试分四层：`test_apiserver`（10，apiserver 语义）、`test_informer`（5，缓存与事件映射）、`test_workqueue`（8，去重/退避/到期）、`test_reconciler`（8，端到端收敛/幂等/级联/漂移/退避）、`test_demo`（6，场景）。每一层只测自己那块机制，失败时能精确定位。

## 7.10 Demo 与生产的差异（诚实声明）

为保持"看清主干"，Demo 做了有意简化，**不要把它当生产参考**：

| 维度 | Demo | 生产 controller-runtime |
|---|---|---|
| apiserver | 内存 dict，无 HTTP/鉴权/RBAC | 真实 etcd + apiserver + RBAC + 审计 |
| Informer | `pump()` 显式驱动（同步） | 长连接 Watch + 后台 goroutine，自动重连/resync |
| 并发 | 单 worker（`max_concurrent=1`） | 多 worker + leader election（多副本单干活） |
| 限流 | 仅指数退避 | 指数退避 + 令牌桶 + per-key 自定义限流器 |
| Pod 就绪 | 时间阈值模拟 | 真实 Pod 生命周期 + readiness/liveness probe + endpoint controller |
| 级联 GC | 同步递归删 | 垃圾回收控制器，支持 Foreground/Background/Orphan 策略 |
| Webhook | 无 | mutating/validating/conversion + mTLS 证书 |

**保留的是 Operator 模式的本质**（声明式 + 控制循环 + 乐观并发 + level-triggered），**简化的是 K8s 的分布式系统工程**。理解了前者，读真实源码时后者只是"工程实现细节"。

## 本章小结

- **Demo 价值**：把前六章机制在一块纯 Python 代码里咬合跑通，让"控制平面语义"可追踪、可测试、可复现。
- **FakeApiServer 四语义**：乐观并发（rv）、generation（spec+1）、/status 子资源（独立 rv 不 bump gen）、finalizer+级联 GC——Operator 正确性的基石。
- **Reconcile 四铁律**在代码里逐条落地：level-triggered（读全量）、幂等（先 Get 再 act）、不阻塞（RequeueAfter）、乐观（Conflict 重试）。
- **Workqueue 三语义**与 controller-runtime 源码逐行对应：error→退避、RequeueAfter→定时、Requeue→立即、else→收敛。
- **FakeClock** 让第 4 章的收敛时间线精确复现：`t=5 patch → reconcile #1 → t=10 reconcile #3 收敛`。
- **37 测试**覆盖四层；**诚实差异表**声明了简化项，避免被误当生产参考。

**参考来源**

- 本手册配套代码：`docs/02-cloud-native/operator/mini-demo/`（`operator-mini` 包 + 测试 + README）。
- 对照真实实现：[controller-runtime 源码](https://github.com/kubernetes-sigs/controller-runtime)（第 6 章）。
- 机制基础：本手册第 2、3、4、5 章。
