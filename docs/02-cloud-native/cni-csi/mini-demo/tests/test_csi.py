"""CSI 测试：provision/attach/stage/publish/snapshot/expand。"""
import pytest

from cni_csi_mini.csi import (
    VolumeStore, NodeVolumeStore, ControllerServer, NodeServer,
    FailedPrecondition, NotFound, InvalidArgument,
)


def make_env(node_name="node-1"):
    store = VolumeStore()
    ctrl = ControllerServer(store)
    node_store = NodeVolumeStore(node_name)
    node = NodeServer(store, node_name, node_store)
    return store, ctrl, node_store, node


def test_create_volume_idempotent():
    store, ctrl, _, _ = make_env()
    v1 = ctrl.create_volume("vol1", size_gi=5)
    v2 = ctrl.create_volume("vol1", size_gi=5)
    assert v1["volume_id"] == v2["volume_id"]


def test_delete_volume_recycles():
    store, ctrl, _, _ = make_env()
    vol = ctrl.create_volume("vol1", size_gi=5)
    ctrl.delete_volume(vol["volume_id"])
    assert store.get_volume(vol["volume_id"]) is None


def test_rwo_single_attach():
    store, ctrl, _, _ = make_env()
    vol = ctrl.create_volume("vol1", size_gi=5, access_modes=["ReadWriteOnce"])
    ctrl.controller_publish_volume(vol["volume_id"], "node-1")
    with pytest.raises(FailedPrecondition):
        ctrl.controller_publish_volume(vol["volume_id"], "node-2")


def test_rox_multi_node_read_only():
    store, ctrl, _, _ = make_env()
    vol = ctrl.create_volume("vol1", size_gi=5, access_modes=["ReadOnlyMany"])
    ctrl.controller_publish_volume(vol["volume_id"], "node-1", read_only=True)
    ctrl.controller_publish_volume(vol["volume_id"], "node-2", read_only=True)
    assert store.is_attached_to(vol["volume_id"], "node-1")
    assert store.is_attached_to(vol["volume_id"], "node-2")


def test_rox_requires_read_only_attach():
    store, ctrl, _, _ = make_env()
    vol = ctrl.create_volume("vol1", size_gi=5, access_modes=["ReadOnlyMany"])
    with pytest.raises(FailedPrecondition):
        ctrl.controller_publish_volume(vol["volume_id"], "node-1", read_only=False)


def test_stage_before_publish_required():
    store, ctrl, node_store, node = make_env()
    vol = ctrl.create_volume("vol1", size_gi=5)
    ctrl.controller_publish_volume(vol["volume_id"], "node-1")
    with pytest.raises(FailedPrecondition):
        node.node_publish_volume(vol["volume_id"], "sb1", "/target")
    node.node_stage_volume(vol["volume_id"], "/staging")
    node.node_publish_volume(vol["volume_id"], "sb1", "/target")
    assert node_store.is_published_to_pod(vol["volume_id"], "sb1")


def test_unpublish_before_unstage_required():
    store, ctrl, node_store, node = make_env()
    vol = ctrl.create_volume("vol1", size_gi=5)
    ctrl.controller_publish_volume(vol["volume_id"], "node-1")
    node.node_stage_volume(vol["volume_id"], "/staging")
    node.node_publish_volume(vol["volume_id"], "sb1", "/target")
    with pytest.raises(FailedPrecondition):
        node.node_unstage_volume(vol["volume_id"])
    node.node_unpublish_volume(vol["volume_id"], "sb1")
    node.node_unstage_volume(vol["volume_id"])
    assert not node_store.is_staged(vol["volume_id"])


def test_snapshot_restore():
    store, ctrl, _, _ = make_env()
    vol = ctrl.create_volume("db", size_gi=10)
    ctrl.create_snapshot(vol["volume_id"], "snap1")
    restored = ctrl.create_volume("db-restore", size_gi=10, source_snapshot="snap1")
    assert restored["sourceSnapshot"] == "snap1"


def test_expand_requires_controller_first():
    store, ctrl, node_store, node = make_env()
    vol = ctrl.create_volume("vol1", size_gi=10)
    ctrl.controller_publish_volume(vol["volume_id"], "node-1")
    node.node_stage_volume(vol["volume_id"], "/staging")
    with pytest.raises(FailedPrecondition):
        node.node_expand_volume(vol["volume_id"])
    ctrl.controller_expand_volume(vol["volume_id"], 20)
    node.node_expand_volume(vol["volume_id"])
    assert store.get_volume(vol["volume_id"])["status"]["node_expanded"] is True


def test_expand_cannot_shrink():
    store, ctrl, _, _ = make_env()
    vol = ctrl.create_volume("vol1", size_gi=10)
    with pytest.raises(InvalidArgument):
        ctrl.controller_expand_volume(vol["volume_id"], 5)


def test_volume_attachment_consistency():
    store, ctrl, _, _ = make_env()
    vol = ctrl.create_volume("vol1", size_gi=5)
    va = ctrl.controller_publish_volume(vol["volume_id"], "node-1")
    assert va["status"]["attached"] is True
    assert store.get_attachment(vol["volume_id"], "node-1")["spec"]["nodeName"] == "node-1"
    ctrl.controller_unpublish_volume(vol["volume_id"], "node-1")
    assert store.get_attachment(vol["volume_id"], "node-1") is None


def test_delete_volume_fails_while_attached():
    store, ctrl, _, _ = make_env()
    vol = ctrl.create_volume("vol1", size_gi=5)
    ctrl.controller_publish_volume(vol["volume_id"], "node-1")
    with pytest.raises(FailedPrecondition):
        ctrl.delete_volume(vol["volume_id"])
