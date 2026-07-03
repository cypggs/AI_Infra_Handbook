"""demo.py —— 端到端场景演示，精确复现第 4 章描述的收敛时间线。

四个场景：
  scenario_create      创建一个 InferenceService → 自动创建 Deployment+Service，多轮收敛到 Ready。
  scenario_scale_upgrade  复现第 4 章的"扩容 + 升级"：patch replicas 2→4 / image 0.6.3→0.7.0，
                          三次 reconcile 收敛（patch → 等 → Pod ready → Ready）。
  scenario_delete      带 finalizer 的删除：清理外部资源 → 移除 finalizer → 级联 GC 子资源。
  scenario_drift       漂移自愈：有人手动改了 Deployment 副本数，Operator 把它纠正回来。

运行：python -m operator_mini.demo
"""
from . import model
from .apiserver import FakeApiServer
from .workqueue import FakeClock
from .controller import Controller
from .reconciler import InferenceServiceReconciler


def build(ready_after=5.0, base_delay=5.0):
    """装配一整套：apiserver + 三类 informer + Controller + 平台模拟器。"""
    clock = FakeClock(0.0)
    apiserver = FakeApiServer()
    reconciler = InferenceServiceReconciler(apiserver, clock, ready_after)
    controller = Controller(
        "inferenceservice", reconciler, clock, base_delay=base_delay
    )
    reconciler._log_cb = controller._log
    reconciler.is_informer = controller.watch_main(apiserver, model.INFERENCE_SERVICE_KIND)
    reconciler.deploy_informer = controller.watch_owned(
        apiserver, model.DEPLOYMENT_KIND, model.INFERENCE_SERVICE_KIND
    )
    reconciler.svc_informer = controller.watch_owned(
        apiserver, model.SERVICE_KIND, model.INFERENCE_SERVICE_KIND
    )
    controller.attach_platform(apiserver, ready_after)
    return controller, apiserver, clock


def _print(lines, title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")
    for ln in lines:
        print(ln)


# --------------------------------------------------------------------------- #
def scenario_create():
    controller, apiserver, _ = build()
    log = controller.trace

    is_obj = model.make_inference_service("llama", image="vllm:0.6.3", replicas=2, model="Llama-3")
    apiserver.create(is_obj)
    controller.run_until_quiescent()

    final = apiserver.get(model.INFERENCE_SERVICE_KIND, "default", "llama")
    _print(log, "场景 1：创建 InferenceService（replicas=2）→ 自动收敛到 Ready")
    print(f"\n最终 status: {final['status']}")
    print(f"reconcile 次数={controller.reconcile_total}, 错误={controller.reconcile_errors}")
    return final


def scenario_scale_upgrade():
    controller, apiserver, clock = build()
    log = controller.trace

    apiserver.create(model.make_inference_service(
        "llama", image="vllm:0.6.3", replicas=2, model="Llama-3"))
    controller.run_until_quiescent()   # 先到稳态

    log.clear()
    # 用户扩容 + 升级（等价于 kubectl patch）
    cur = apiserver.get(model.INFERENCE_SERVICE_KIND, "default", "llama")
    cur["spec"]["replicas"] = 4
    cur["spec"]["image"] = "vllm:0.7.0"
    apiserver.update(cur)              # generation 3→4
    controller.run_until_quiescent()

    final = apiserver.get(model.INFERENCE_SERVICE_KIND, "default", "llama")
    _print(log, "场景 2：扩容 + 升级（replicas 2→4, image 0.6.3→0.7.0）→ 三次 reconcile 收敛")
    print(f"\n最终 status: {final['status']}")
    print(f"reconcile 次数={controller.reconcile_total}")
    return final


def scenario_delete():
    controller, apiserver, _ = build()
    log = controller.trace

    apiserver.create(model.make_inference_service(
        "llama", image="vllm:0.6.3", replicas=2, model="Llama-3"))
    controller.run_until_quiescent()

    log.clear()
    apiserver.delete(model.INFERENCE_SERVICE_KIND, "default", "llama")  # 触发 finalizer
    controller.run_until_quiescent()

    gone = apiserver.get(model.INFERENCE_SERVICE_KIND, "default", "llama") is None
    dep_gone = apiserver.get(model.DEPLOYMENT_KIND, "default", "llama") is None
    svc_gone = apiserver.get(model.SERVICE_KIND, "default", "llama") is None
    _print(log, "场景 3：删除 InferenceService → finalizer 清理 → 级联 GC 子资源")
    print(f"\nCR 已删除={gone}, Deployment 级联删除={dep_gone}, Service 级联删除={svc_gone}")
    return {"cr_gone": gone, "deploy_gone": dep_gone, "svc_gone": svc_gone}


def scenario_drift():
    controller, apiserver, _ = build()
    log = controller.trace

    apiserver.create(model.make_inference_service(
        "llama", image="vllm:0.6.3", replicas=3, model="Llama-3"))
    controller.run_until_quiescent()

    log.clear()
    # 有人手动改 Deployment 副本（漂移）—— Owns 会把事件映射回 owner CR
    dep = apiserver.get(model.DEPLOYMENT_KIND, "default", "llama")
    dep["spec"]["replicas"] = 99       # 与期望（3）严重偏离
    apiserver.update(dep)
    controller.run_until_quiescent()

    final_dep = apiserver.get(model.DEPLOYMENT_KIND, "default", "llama")
    _print(log, "场景 4：漂移自愈（手动改 Deployment replicas=99）→ level-triggered 纠回 3")
    print(f"\nDeployment 最终 replicas={final_dep['spec']['replicas']}（期望 3）")
    return {"restored": final_dep["spec"]["replicas"] == 3}


def run_demo():
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║   operator-mini：纯 Python 从零实现的 Kubernetes Operator            ║")
    print("║   CRD + level-triggered Reconcile + Finalizer + Status + Owner 级联   ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    scenario_create()
    scenario_scale_upgrade()
    scenario_delete()
    scenario_drift()


if __name__ == "__main__":
    run_demo()
