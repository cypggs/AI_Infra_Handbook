"""platform.py —— 模拟 K8s 内置的 Deployment Controller（平台层）。

真实集群里，Operator 创建 Deployment 后，是 kube-controller-manager + endpoint controller
负责让 Pod 变 ready、把 readyReplicas 写进 Deployment.status。Operator 只是读这个 status。

为了让模拟"收敛过程"可观测（模型加载需要时间），这里用一个极简的 Deployment 控制器：
Deployment 的 spec（replicas/image）每变化一次，readyReplicas 在 ready_after 秒后
从 0 翻到目标值。Operator 据此读到"还不 ready → RequeueAfter"，从而复现第 4 章的多轮收敛。
"""


def reconcile_deployments(apiserver, clock, ready_after, state):
    """推进所有 Deployment 的 readyReplicas。

    state: dict[key] = (generation, stable_since)。spec 变化时重置 stable_since。
    """
    changed = 0
    for k, dep in list(apiserver.list("Deployment").items()):
        gen = dep["metadata"]["generation"]
        prev = state.get(k)
        if prev is None or prev[0] != gen:
            stable_since = clock.now()
            state[k] = (gen, stable_since)
        else:
            stable_since = prev[1]

        target = dep["spec"]["replicas"]
        ready = target if (clock.now() - stable_since) >= ready_after else 0
        if dep["status"].get("readyReplicas") != ready:
            dep["status"]["readyReplicas"] = ready
            apiserver.update_status(dep)   # 平台写 status（不 bump generation）
            changed += 1
    return changed
