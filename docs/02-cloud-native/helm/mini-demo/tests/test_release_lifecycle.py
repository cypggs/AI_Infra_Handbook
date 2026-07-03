import pytest
from helm_mini.action import Configuration, Install, Upgrade, Rollback, Uninstall
from helm_mini.demo import build_chart
from helm_mini.release import ReleaseStatus
from helm_mini.storage import SecretDriver


def _cfg():
    return Configuration()


def test_install_creates_release_v1_and_resources():
    cfg = _cfg()
    r = Install(cfg).run("app", build_chart(), namespace="prod")
    assert r.version == 1
    assert r.status == ReleaseStatus.DEPLOYED
    # 部署了 Deployment + Service + PVC（HPA/Ingress 被 if 关闭）
    kinds = {k[0] for k in cfg.kube.cluster}
    assert kinds == {"Deployment", "Service", "PersistentVolumeClaim"}


def test_secret_name_follows_helm_convention():
    cfg = _cfg()
    Install(cfg).run("app", build_chart(), namespace="prod")
    key = "sh.helm.release.v1.app.v1"
    assert cfg.storage.driver.get(key) is not None


def test_upgrade_preserves_manual_scale_via_three_way_merge():
    cfg = _cfg()
    Install(cfg).run("app", build_chart(), namespace="prod")
    # 模拟 kubectl scale 到 10
    cfg.kube.apply_manual_change("Deployment", "prod", "app-inference",
                                 ["spec", "replicas"], 10)
    # 升级镜像，chart 没改 replicas
    ch = build_chart(tag="0.7.0")
    r2 = Upgrade(cfg).run("app", ch, namespace="prod", values=[{"image": {"tag": "0.7.0"}}])
    assert r2.version == 2
    deploy = cfg.kube.live("Deployment", "prod", "app-inference")
    assert deploy["spec"]["replicas"] == 10            # 手动扩容保留
    assert deploy["spec"]["template"]["spec"]["containers"][0]["image"].endswith("0.7.0")


def test_upgrade_superseded_old_revision():
    cfg = _cfg()
    Install(cfg).run("app", build_chart(), namespace="prod")
    Upgrade(cfg).run("app", build_chart(tag="0.7.0"), namespace="prod",
                     values=[{"image": {"tag": "0.7.0"}}])
    r1 = cfg.storage.get("app", 1)
    assert r1.status == ReleaseStatus.SUPERSEDED


def test_rollback_creates_new_revision_and_reverts_image():
    cfg = _cfg()
    Install(cfg).run("app", build_chart(), namespace="prod")          # v1, image 0.6.3
    Upgrade(cfg).run("app", build_chart(tag="0.7.0"), namespace="prod",
                     values=[{"image": {"tag": "0.7.0"}}])           # v2, image 0.7.0
    r3 = Rollback(cfg).run("app", 1, namespace="prod")               # 回到 v1
    assert r3.version == 3
    deploy = cfg.kube.live("Deployment", "prod", "app-inference")
    assert deploy["spec"]["template"]["spec"]["containers"][0]["image"].endswith("0.6.3")


def test_rollback_still_preserves_manual_scale():
    cfg = _cfg()
    Install(cfg).run("app", build_chart(), namespace="prod")
    cfg.kube.apply_manual_change("Deployment", "prod", "app-inference", ["spec", "replicas"], 10)
    Upgrade(cfg).run("app", build_chart(tag="0.7.0"), namespace="prod",
                     values=[{"image": {"tag": "0.7.0"}}])
    Rollback(cfg).run("app", 1, namespace="prod")
    deploy = cfg.kube.live("Deployment", "prod", "app-inference")
    assert deploy["spec"]["replicas"] == 10            # rollback 仍保留手动扩容


def test_history_lists_revisions_in_order():
    cfg = _cfg()
    Install(cfg).run("app", build_chart(), namespace="prod")
    Upgrade(cfg).run("app", build_chart(tag="0.7.0"), namespace="prod",
                     values=[{"image": {"tag": "0.7.0"}}])
    hist = cfg.storage.history("app")
    assert [r.version for r in hist] == [1, 2]


def test_uninstall_removes_resources_but_keeps_pvc():
    cfg = _cfg()
    Install(cfg).run("app", build_chart(), namespace="prod")
    Uninstall(cfg).run("app")
    # PVC 有 resource-policy=keep -> 保留；其余删除
    kinds = {k[0] for k in cfg.kube.cluster}
    assert kinds == {"PersistentVolumeClaim"}


def test_uninstall_without_keep_history_clears_secrets():
    cfg = _cfg()
    Install(cfg).run("app", build_chart(), namespace="prod")
    Uninstall(cfg).run("app")
    assert cfg.storage.revisions("app") == []


def test_uninstall_with_keep_history_retains_secrets():
    cfg = _cfg()
    Install(cfg).run("app", build_chart(), namespace="prod")
    Uninstall(cfg, keep_history=True).run("app")
    revs = cfg.storage.revisions("app")
    assert len(revs) == 1
    assert revs[0].status == ReleaseStatus.UNINSTALLED


def test_conditional_resources_toggle():
    cfg = _cfg()
    Install(cfg).run("app", build_chart(), namespace="prod",
                     values=[{"autoscaling": {"enabled": True, "minReplicas": 2, "maxReplicas": 8},
                              "ingress": {"enabled": True, "host": "x.com"}}])
    kinds = {k[0] for k in cfg.kube.cluster}
    assert "HorizontalPodAutoscaler" in kinds
    assert "Ingress" in kinds


def test_upgrade_to_nonexistent_release_raises():
    cfg = _cfg()
    with pytest.raises(RuntimeError):
        Upgrade(cfg).run("ghost", build_chart(), namespace="prod")


def test_history_max_prunes_old_superseded():
    from helm_mini.storage import Storage
    cfg = Configuration(storage=Storage(history_max=2))
    ch = build_chart()
    Install(cfg).run("app", ch, namespace="prod")
    for i in range(5):
        Upgrade(cfg).run("app", ch, namespace="prod", values=[{"replicaCount": i}])
    revs = cfg.storage.revisions("app")
    # history_max=2：只保留最近 2 个 revision
    assert len(revs) <= 2
