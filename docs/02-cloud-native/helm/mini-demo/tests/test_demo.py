import pytest
from helm_mini.demo import run_demo


def test_demo_end_to_end_assertions():
    out = run_demo(verbose=False)

    # 场景 1：v1 首次部署
    assert out["v1_replicas"] == 2

    # 场景 3：升级镜像，人工扩容被三方合并保留
    assert out["v2_image"].endswith("0.7.0")
    assert out["v2_replicas_preserved"] == 10

    # 场景 4：回滚到 v1，镜像回退，扩容仍保留
    assert out["v3_image"].endswith("0.6.3")
    assert out["v3_replicas_preserved"] == 10

    # 场景 5：chart 主动改 replicas -> 生效
    assert out["v4_replicas_chart_driven"] == 4

    # 场景 6：条件资源被打开
    assert set(["Deployment", "HorizontalPodAutoscaler", "Ingress",
                "PersistentVolumeClaim", "Service"]).issubset(set(out["kinds_after_conditional"]))

    # 场景 7：PVC 因 resource-policy=keep 在卸载后保留
    assert out["pvc_kept_after_uninstall"] is True


def test_demo_trace_has_all_scenarios():
    out = run_demo(verbose=False)
    trace = "\n".join(out["trace"])
    for marker in ["场景 1", "场景 2", "场景 3", "场景 4", "场景 5", "场景 6", "场景 7"]:
        assert marker in trace
