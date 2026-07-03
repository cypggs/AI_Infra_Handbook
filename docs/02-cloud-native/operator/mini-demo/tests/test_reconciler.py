"""端到端 Reconcile 行为测试：收敛、幂等、observedGeneration、删除、级联、漂移、退避。"""
from operator_mini import model
from operator_mini.demo import build


def test_create_converges_to_ready():
    controller, apiserver, _ = build()
    apiserver.create(model.make_inference_service(
        "llama", image="vllm:0.6.3", replicas=3, model="Llama-3"))
    controller.run_until_quiescent()

    is_obj = apiserver.get(model.INFERENCE_SERVICE_KIND, "default", "llama")
    dep = apiserver.get(model.DEPLOYMENT_KIND, "default", "llama")
    svc = apiserver.get(model.SERVICE_KIND, "default", "llama")
    assert svc is not None, "Service 应被创建"
    assert dep is not None, "Deployment 应被创建"
    assert is_obj["status"]["ready"] is True
    assert is_obj["status"]["readyReplicas"] == 3


def test_idempotent_multiple_runs_no_duplicate_children():
    controller, apiserver, _ = build()
    apiserver.create(model.make_inference_service(
        "llama", image="vllm:0.6.3", replicas=2, model="Llama-3"))
    controller.run_until_quiescent()
    controller.run_until_quiescent()   # 再跑一遍
    controller.run_until_quiescent()   # 再跑一遍

    deps = apiserver.list(model.DEPLOYMENT_KIND)
    svcs = apiserver.list(model.SERVICE_KIND)
    assert len(deps) == 1, "幂等：不应创建多个 Deployment"
    assert len(svcs) == 1, "幂等：不应创建多个 Service"


def test_observed_generation_tracks_spec():
    controller, apiserver, _ = build()
    apiserver.create(model.make_inference_service(
        "llama", image="vllm:0.6.3", replicas=2, model="Llama-3"))
    controller.run_until_quiescent()

    obj = apiserver.get(model.INFERENCE_SERVICE_KIND, "default", "llama")
    obj["spec"]["replicas"] = 5                       # spec 变 → generation +1
    apiserver.update(obj)
    controller.run_until_quiescent()

    final = apiserver.get(model.INFERENCE_SERVICE_KIND, "default", "llama")
    assert final["metadata"]["generation"] == 2
    assert final["status"]["observedGeneration"] == 2, "observedGeneration 必须追上 generation"
    assert final["status"]["ready"] is True
    assert final["status"]["readyReplicas"] == 5


def test_scale_upgrade_three_reconciles():
    """复现第 4 章：扩容+升级需多次 reconcile 才收敛（Pod 模型加载需要时间）。"""
    controller, apiserver, _ = build()
    apiserver.create(model.make_inference_service(
        "llama", image="vllm:0.6.3", replicas=2, model="Llama-3"))
    controller.run_until_quiescent()

    obj = apiserver.get(model.INFERENCE_SERVICE_KIND, "default", "llama")
    obj["spec"]["replicas"] = 4
    obj["spec"]["image"] = "vllm:0.7.0"
    apiserver.update(obj)
    controller.run_until_quiescent()

    final = apiserver.get(model.INFERENCE_SERVICE_KIND, "default", "llama")
    dep = apiserver.get(model.DEPLOYMENT_KIND, "default", "llama")
    assert dep["spec"]["replicas"] == 4
    assert dep["spec"]["image"] == "vllm:0.7.0"
    assert final["status"]["ready"] is True
    assert final["status"]["readyReplicas"] == 4
    assert controller.reconcile_total > 1, "扩容升级应经历多次 reconcile"


def test_finalizer_cleanup_then_cascade():
    controller, apiserver, _ = build()
    apiserver.create(model.make_inference_service(
        "llama", image="vllm:0.6.3", replicas=2, model="Llama-3"))
    controller.run_until_quiescent()

    apiserver.delete(model.INFERENCE_SERVICE_KIND, "default", "llama")
    controller.run_until_quiescent()

    assert apiserver.get(model.INFERENCE_SERVICE_KIND, "default", "llama") is None, "CR 应已删除"
    assert apiserver.get(model.DEPLOYMENT_KIND, "default", "llama") is None, "Deployment 应级联删除"
    assert apiserver.get(model.SERVICE_KIND, "default", "llama") is None, "Service 应级联删除"
    assert controller.reconciler.cleanup_calls == 1, "外部清理应被调用一次"


def test_drift_self_heals():
    """有人手动改 Deployment 副本 → Owns 事件映射回 CR → level-triggered 纠回期望。"""
    controller, apiserver, _ = build()
    apiserver.create(model.make_inference_service(
        "llama", image="vllm:0.6.3", replicas=3, model="Llama-3"))
    controller.run_until_quiescent()

    dep = apiserver.get(model.DEPLOYMENT_KIND, "default", "llama")
    dep["spec"]["replicas"] = 99
    apiserver.update(dep)             # 人为漂移
    controller.run_until_quiescent()

    final_dep = apiserver.get(model.DEPLOYMENT_KIND, "default", "llama")
    assert final_dep["spec"]["replicas"] == 3, "漂移应被纠回期望值"


def test_backoff_on_conflict_then_recovers():
    """注入一次 apiserver 冲突 → reconcile 报错 → 指数退避 → 重试成功。"""
    controller, apiserver, _ = build(base_delay=5.0)
    apiserver.create(model.make_inference_service(
        "llama", image="vllm:0.6.3", replicas=2, model="Llama-3"))
    # 在第一次写 status 时注入冲突
    apiserver.inject_conflict(1)
    controller.run_until_quiescent()

    final = apiserver.get(model.INFERENCE_SERVICE_KIND, "default", "llama")
    assert controller.reconcile_errors >= 1, "应有至少一次失败"
    assert final["status"]["ready"] is True, "退避重试后最终收敛"


def test_nonblocking_uses_requeue_after():
    """Reconcile 不应阻塞；未收敛时用 RequeueAfter（时间推进）而非 sleep。"""
    controller, apiserver, clock = build(ready_after=5.0)
    apiserver.create(model.make_inference_service(
        "llama", image="vllm:0.6.3", replicas=2, model="Llama-3"))
    controller.run_until_quiescent()
    # 时间被推进过（Pod ready 需要等 5s），证明走的是 RequeueAfter 而非立即就绪
    assert clock.now() >= 5.0
