"""FakeApiServer —— 模拟 kube-apiserver + etcd 的核心语义。

重点实现四件真实 apiserver 做、但教学时常被忽略的事：

1. 乐观并发：每个对象有 resourceVersion；update 必须带上"读到的" rv，否则 409 Conflict。
2. generation：spec 变更才 +1，status 变更不 +1。
3. /status 子资源：单独写入路径，独立的 rv 校验，不触发 spec 的 generation 变化。
4. watch 事件流：维护单调递增的 ADDED/MODIFIED/DELETED 事件流。
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
        self._event_idx = itertools.count(1)   # 事件 index 从 1 开始
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
        if self._inject_conflict > 0:
            self._inject_conflict -= 1
            raise Conflict(f"{k} injected conflict")

        spec_changed = obj.get("spec") != cur.get("spec")
        obj["metadata"]["generation"] = cur["metadata"]["generation"] + (1 if spec_changed else 0)
        obj["metadata"]["resourceVersion"] = self._next_rv()
        self._store[k] = copy.deepcopy(obj)
        self._emit("MODIFIED", obj)
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
        self._emit("MODIFIED", cur)
        return copy.deepcopy(cur)

    def delete(self, kind, namespace, name):
        k = self._k(kind, namespace, name)
        cur = self._store.get(k)
        if cur is None:
            return None
        del self._store[k]
        self._emit("DELETED", cur)
        return copy.deepcopy(cur)

    # ---------------- 测试钩子 ---------------- #
    def inject_conflict(self, times=1):
        self._inject_conflict = times

    # ---------------- 辅助 ---------------- #
    def snapshot(self):
        """返回当前 store 的深拷贝，用于断言。"""
        return {k: copy.deepcopy(v) for k, v in self._store.items()}
