"""Tests for KubeRay mini-demo."""
from kuberay_mini import demo


def test_cluster_creation_converges():
    controller, apiserver, _ = demo.build()
    cluster = demo.make_ray_cluster("test-cluster", worker_replicas=2)
    apiserver.create(cluster)
    controller.run_until_quiescent()

    cluster = apiserver.get(demo.RAYCLUSTER_KIND, "default", "test-cluster")
    assert cluster["status"]["state"] == "ready"
    assert cluster["status"]["readyWorkerReplicas"] == 2
    assert cluster["status"]["observedGeneration"] == 1

    head_svc = apiserver.get(demo.SERVICE_KIND, "default", "test-cluster-head-svc")
    serve_svc = apiserver.get(demo.SERVICE_KIND, "default", "test-cluster-serve-svc")
    assert head_svc is not None
    assert serve_svc is not None

    pods = apiserver.list(demo.POD_KIND, "default")
    cluster_pods = [p for p in pods.values() if p["spec"].get("clusterName") == "test-cluster"]
    assert len(cluster_pods) == 3  # 1 head + 2 workers


def test_scale_out_and_in():
    controller, apiserver, _ = demo.build()
    cluster = demo.make_ray_cluster("scale-cluster", worker_replicas=1)
    apiserver.create(cluster)
    controller.run_until_quiescent()

    cluster = apiserver.get(demo.RAYCLUSTER_KIND, "default", "scale-cluster")
    assert cluster["status"]["readyWorkerReplicas"] == 1

    # Simulate autoscaler scale out
    cluster["spec"]["workerGroupSpecs"][0]["replicas"] = 3
    apiserver.update(cluster)
    controller.run_until_quiescent()

    cluster = apiserver.get(demo.RAYCLUSTER_KIND, "default", "scale-cluster")
    assert cluster["status"]["readyWorkerReplicas"] == 3

    # Scale back in
    cluster["spec"]["workerGroupSpecs"][0]["replicas"] = 1
    apiserver.update(cluster)
    controller.run_until_quiescent()

    cluster = apiserver.get(demo.RAYCLUSTER_KIND, "default", "scale-cluster")
    assert cluster["status"]["readyWorkerReplicas"] == 1


def test_rayjob_lifecycle():
    controller, apiserver, _ = demo.build()
    job = demo.make_ray_job("test-job", entrypoint="python train.py")
    apiserver.create(job)
    controller.run_until_quiescent()

    job = apiserver.get(demo.RAYJOB_KIND, "default", "test-job")
    assert job["status"]["jobDeploymentStatus"] == "Complete"
    assert job["status"]["jobStatus"] == "SUCCEEDED"

    # The owned RayCluster should be cleaned up
    assert apiserver.get(demo.RAYCLUSTER_KIND, "default", "test-job-cluster") is None


def test_run_demo_end_to_end():
    result = demo.run_demo()
    assert result["cluster_name"] == "example-cluster"
    assert result["final_worker_count"] == 4
    assert result["job_name"] == "example-job"
    assert result["job_status"] == "Complete"
    assert result["job_cluster_deleted"] is True
