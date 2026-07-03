"""Informer —— 模拟 client-go SharedInformer：List 建立 cache 基线，Watch 增量更新。

Reconciler 永远从 Informer 的本地缓存读资源（快、不压 apiserver）。Informerr 把
apiserver 的事件流翻译成"缓存更新 + 回调 EventHandler"。EventHandler 决定"哪个 CR 该入队"。

真实 Informer 用长连接 Watch + 后台 goroutine；这里用 pump() 显式驱动（单线程可步进），
语义一致：每次 pump 拉取新事件、更新缓存、调用 handler。
"""
import copy

from . import model


class Informer:
    def __init__(self, apiserver, kind, handler):
        self.apiserver = apiserver
        self.kind = kind
        self.handler = handler           # callable(event_type, object)
        self.cache = {}                  # key -> object（本地缓存）
        self._idx = 0
        self._full_sync()                # 启动时 List 全量建立基线

    def _full_sync(self):
        for k, v in self.apiserver.list(self.kind).items():
            self.cache[k] = copy.deepcopy(v)
        self._idx = self.apiserver.event_index()

    # ---- 读（命中本地缓存，O(1)） ---- #
    def get(self, kind, namespace, name):
        obj = self.cache.get((kind, namespace, name))
        return copy.deepcopy(obj) if obj is not None else None

    def list(self, namespace=None, label_selector=None):
        out = {}
        for k, v in self.cache.items():
            if namespace and k[1] != namespace:
                continue
            if label_selector and not _labels_match(v, label_selector):
                continue
            out[k] = copy.deepcopy(v)
        return out

    # ---- Watch 推进 ---- #
    def pump(self):
        """消费新事件：更新缓存 + 回调 handler。返回处理的事件数。"""
        events = self.apiserver.events_since(self._idx)
        for ev in events:
            k = ev["key"]
            if ev["type"] in ("ADDED", "MODIFIED"):
                self.cache[k] = copy.deepcopy(ev["object"])
                self.handler(ev["type"], copy.deepcopy(ev["object"]))
            elif ev["type"] == "DELETED":
                self.cache.pop(k, None)
                self.handler("DELETED", copy.deepcopy(ev["object"]))
        self._idx = self.apiserver.event_index()
        return len(events)


def _labels_match(obj, selector):
    labels = obj.get("metadata", {}).get("labels", {})
    return all(labels.get(lk) == lv for lk, lv in selector.items())


# --------------------------------------------------------------------------- #
# EventHandlers —— 把"资源事件"翻译成"该调和哪个 ns/name"，塞进 workqueue。
# --------------------------------------------------------------------------- #
def enqueue_self(queue):
    """主资源用：事件 → 把对象自己入队（For）。"""
    def handler(_etype, obj):
        queue.add(model.key(obj))
    return handler


def enqueue_owner(queue, owner_kind):
    """子资源用：事件 → 反查 ownerReference，把 controller owner 入队（Owns）。"""
    def handler(_etype, obj):
        owner = model.controller_owner(obj)
        if owner and owner["kind"] == owner_kind:
            queue.add((owner_kind, obj["metadata"]["namespace"], owner["name"]))
    return handler
