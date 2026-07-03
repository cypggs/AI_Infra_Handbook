"""FakeApiServer —— 模拟 kube-apiserver + etcd 的核心语义。

不是 HTTP server，而是一个内存存储 + 一组 K8s 语义操作。重点实现四件真实 apiserver
做、但教学时常被忽略的事：

1. 乐观并发：每个对象有 resourceVersion；update 必须带上"读到的" rv，否则 409 Conflict。
   Reconciler"先读后写"的并发安全完全依赖它。
2. generation：spec 变更才 +1，status 变更不 +1。让 Controller 能区分"用户改了 spec"和
   "我自己写了 status"。
3. /status 子资源：单独写入路径，独立的 rv 校验，不触发 spec 的 generation 变化。
4. finalizer + 级联 GC：有 finalizer 的对象 delete 只设 deletionTimestamp；最后一个 finalizer
   被移除（且 deletionTimestamp 已设）时才真删；删除对象时递归 GC 它的 controller 子资源。

还维护一条单调递增的事件流（ADDED/MODIFIED/DELETED），供 Informer Watch。
"""
import copy
import itertools

from . import model


class ApiError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class Conflict(ApiError):
    def __init__(self, message):
        super().__init__(409, message)


class NotFound(ApiError):
    def __init__(self, message):
        super().__init__(404, message)


class FakeApiServer:
    def __init__(self):
        self._store = {}                       # key -> 资源 dict
        self._events = []                      # 事件流：[{index, type, key, object}]
        self._rv = itertools.count(1)          # 全局 resourceVersion 生成器
        self._event_idx = itertools.count(1)   # 事件 index 从 1 开始，使空库 event_index()==0，
                                               # Informer 首次 events_since(0) 能正确捕获第一个事件
        self._inject_conflict = 0              # 测试钩子：下一次 update 强制 Conflict

    # ---------------- 内部 ---------------- #
    @staticmethod
    def _k(kind, namespace, name):
        return (kind, namespace, name)

    def _next_rv(self):
        return str(next(self._rv))

    def _emit(self, etype, obj):
        ev = {
            "index": next(self._event_idx),
            "type": etype,
            "key": model.key(obj),
            "object": copy.deepcopy(obj),
        }
        self._events.append(ev)

    def event_index(self):
        """当前事件流末端 index（Informer 用它做"从哪继续 watch"的游标）。"""
        return self._events[-1]["index"] if self._events else 0

    def events_since(self, idx):
        return [e for e in self._events if e["index"] > idx]

    # ---------------- 读 ---------------- #
    def get(self, kind, namespace, name):
        obj = self._store.get(self._k(kind, namespace, name))
        return copy.deepcopy(obj) if obj is not None else None

    def list(self, kind=None, namespace=None):
        out = {}
        for k, v in self._store.items():
            if kind and k[0] != kind:
                continue
            if namespace and k[1] != namespace:
                continue
            out[k] = copy.deepcopy(v)
        return out

    # ---------------- 写 ---------------- #
    def create(self, obj):
        k = model.key(obj)
        if k in self._store:
            raise Conflict(f"{k} already exists")
        obj["metadata"]["resourceVersion"] = self._next_rv()
        obj["metadata"]["generation"] = max(1, obj["metadata"].get("generation") or 1)
        self._store[k] = copy.deepcopy(obj)
        self._emit("ADDED", obj)
        return copy.deepcopy(obj)

    def update(self, obj):
        """全量更新。校验 resourceVersion（乐观锁）；spec 变化才 bump generation。"""
        k = model.key(obj)
        cur = self._store.get(k)
        if cur is None:
            raise NotFound(f"{k} not found")
        if obj["metadata"].get("resourceVersion") != cur["metadata"]["resourceVersion"]:
            raise Conflict(f"{k} resourceVersion mismatch (optimistic lock)")
        if self._inject_conflict > 0:           # 测试钩子：模拟并发写
            self._inject_conflict -= 1
            raise Conflict(f"{k} injected conflict")

        spec_changed = obj.get("spec") != cur.get("spec")
        obj["metadata"]["generation"] = cur["metadata"]["generation"] + (1 if spec_changed else 0)
        obj["metadata"]["resourceVersion"] = self._next_rv()
        self._store[k] = copy.deepcopy(obj)
        self._emit("MODIFIED", obj)

        # finalizer 路径：删除中 + 已无 finalizer → 真正删除 + 级联 GC
        if model.is_being_deleted(obj) and not obj["metadata"].get("finalizers"):
            del self._store[k]
            self._emit("DELETED", obj)
            self._gc_children(obj)
            return copy.deepcopy(obj)
        return copy.deepcopy(obj)

    def update_status(self, obj):
        """/status 子资源：只写 status，不 bump generation，独立 rv 校验。"""
        k = model.key(obj)
        cur = self._store.get(k)
        if cur is None:
            raise NotFound(f"{k} not found")
        if obj["metadata"].get("resourceVersion") != cur["metadata"]["resourceVersion"]:
            raise Conflict(f"{k} status resourceVersion mismatch")
        cur["status"] = copy.deepcopy(obj.get("status", {}))
        cur["metadata"]["resourceVersion"] = self._next_rv()
        # 注意：generation 不变
        self._emit("MODIFIED", cur)
        return copy.deepcopy(cur)

    def delete(self, kind, namespace, name):
        k = self._k(kind, namespace, name)
        cur = self._store.get(k)
        if cur is None:
            return None
        if cur["metadata"].get("finalizers"):
            # 有 finalizer：只设 deletionTimestamp，等 Controller 清理后移除 finalizer
            if not cur["metadata"].get("deletionTimestamp"):
                cur["metadata"]["deletionTimestamp"] = "2026-07-04T00:00:00Z"
                cur["metadata"]["resourceVersion"] = self._next_rv()
                self._emit("MODIFIED", cur)
            return copy.deepcopy(cur)
        # 无 finalizer：直接删 + 级联 GC
        del self._store[k]
        self._emit("DELETED", cur)
        self._gc_children(cur)
        return copy.deepcopy(cur)

    def _gc_children(self, owner):
        """递归删除所有 controller owner 指向 owner 的对象（级联垃圾回收）。"""
        owner_id = (owner["kind"], owner["metadata"]["namespace"], owner["metadata"]["name"])
        children = [k for k, v in self._store.items()
                    if model.controller_owner_id(v) == owner_id]
        for ck in children:
            child = self._store.pop(ck)
            self._emit("DELETED", child)
            self._gc_children(child)

    # ---------------- 测试钩子 ---------------- #
    def inject_conflict(self, times=1):
        self._inject_conflict = times
