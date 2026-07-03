"""demo —— 端到端演示：Chart 渲染 + Release 生命周期 + 三方合并。

跑 ``python -m helm_mini.demo`` 即可看到完整时序。
场景见 README.md；这里把 chart 内联，便于单文件阅读。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from .action import Configuration, Install, Rollback, Uninstall, Upgrade
from .chart import Chart, ChartMetadata
from .storage import Storage, SecretDriver
from .values import merge_values


# --------------------------------------------------------------------------- #
# 一个“生产级 GPU 推理服务”Chart（极简但真实）
# --------------------------------------------------------------------------- #
HELPERS = """\
{{- define "app.fullname" -}}
{{- .Release.Name }}-{{ .Values.nameOverride | default .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "app.labels" -}}
app: {{ include "app.fullname" . }}
chart: {{ .Chart.Name }}-{{ .Chart.Version }}
release: {{ .Release.Name }}
managed-by: {{ .Release.Service }}
{{- end -}}
"""

DEPLOYMENT = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "app.fullname" . }}
  labels:
    {{- include "app.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ include "app.fullname" . }}
  template:
    metadata:
      labels:
        app: {{ include "app.fullname" . }}
    spec:
      containers:
        - name: server
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.service.port }}
              protocol: TCP
          env:
            - name: MODEL_NAME
              value: {{ .Values.model.name | quote }}
            - name: MAX_MODEL_LEN
              value: {{ .Values.model.maxModelLen | quote }}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
"""

SERVICE = """\
apiVersion: v1
kind: Service
metadata:
  name: {{ include "app.fullname" . }}
spec:
  type: {{ .Values.service.type }}
  selector:
    app: {{ include "app.fullname" . }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: http
      protocol: TCP
      name: http
"""

HPA = """\
{{- if .Values.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "app.fullname" . }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "app.fullname" . }}
  minReplicas: {{ .Values.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.autoscaling.maxReplicas }}
{{- end }}
"""

INGRESS = """\
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "app.fullname" . }}
spec:
  rules:
    - host: {{ .Values.ingress.host | quote }}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {{ include "app.fullname" . }}
                port:
                  number: {{ .Values.service.port }}
{{- end }}
"""

# 保留策略演示：PVC 用 resource-policy=keep，uninstall 时保留
PVC = """\
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ include "app.fullname" . }}-cache
  annotations:
    helm.sh/resource-policy: keep
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: {{ .Values.cache.size | quote }}
"""

DEFAULT_VALUES: Dict[str, Any] = {
    "replicaCount": 2,
    "nameOverride": "",
    "image": {"repository": "vllm/vllm-openai", "tag": "0.6.3", "pullPolicy": "IfNotPresent"},
    "model": {"name": "meta-llama/Llama-3-8B-Instruct", "maxModelLen": 8192},
    "service": {"port": 8000, "type": "ClusterIP"},
    "resources": {
        "limits": {"nvidia.com/gpu": 1, "memory": "24Gi"},
        "requests": {"cpu": "4", "memory": "16Gi"},
    },
    "ingress": {"enabled": False, "host": "inference.example.com"},
    "autoscaling": {"enabled": False, "minReplicas": 2, "maxReplicas": 8},
    "cache": {"size": "50Gi"},
}


def build_chart(tag: str = "0.6.3") -> Chart:
    return Chart(
        metadata=ChartMetadata(
            name="inference",
            version="0.1.0",
            appVersion=tag,
            apiVersion="v2",
            description="A GPU LLM inference service chart",
        ),
        templates=[
            ("templates/_helpers.tpl", HELPERS),
            ("templates/deployment.yaml", DEPLOYMENT),
            ("templates/service.yaml", SERVICE),
            ("templates/hpa.yaml", HPA),
            ("templates/ingress.yaml", INGRESS),
            ("templates/pvc.yaml", PVC),
        ],
        values=deepcopy(DEFAULT_VALUES),
    )


def _live_deploy(cfg: Configuration, release_name: str):
    return cfg.kube.live("Deployment", "prod", f"{release_name}-inference")


def run_demo(verbose: bool = True) -> dict:
    """跑完整时序，返回关键断言点（供测试）。"""
    cfg = Configuration(storage=Storage(SecretDriver(), history_max=10))
    ns = "prod"
    release_name = "myrelease"
    trace: list = []

    def log(msg: str):
        trace.append(msg)
        if verbose:
            print(msg)

    log("=" * 70)
    log("场景 1：helm install —— 首次部署（chart v1, image 0.6.3, replicas=2）")
    chart = build_chart()
    r1 = Install(cfg).run(release_name, chart, namespace=ns)
    log(f"  → release v{r1.version} status={r1.status.value}")
    log(f"  → Secret: {cfg.storage.driver.secret_name(release_name, 1)}")
    deploy1 = _live_deploy(cfg, release_name)
    log(f"  → 集群 Deployment: replicas={deploy1['spec']['replicas']}, "
        f"image={deploy1['spec']['template']['spec']['containers'][0]['image']}")
    log("  → 资源数（Deployment/Service/PVC，HPA/Ingress 被 if 关闭）= "
        f"{len(cfg.kube.cluster)}")

    log("\n" + "=" * 70)
    log("场景 2：人工扩容（模拟 kubectl scale --replicas=10）")
    cfg.kube.apply_manual_change("Deployment", ns, f"{release_name}-inference",
                                 ["spec", "replicas"], 10)
    log(f"  → 集群 replicas 现为 {_live_deploy(cfg, release_name)['spec']['replicas']}")

    log("\n" + "=" * 70)
    log("场景 3：helm upgrade —— 升级镜像到 0.7.0（chart replicas 仍=2）")
    log("  ★ 三方合并：replicas 在 chart 里没变（2→2），集群被人工改成 10 → 保留 10")
    chart2 = build_chart(tag="0.7.0")
    chart2.values["image"]["tag"] = "0.7.0"
    r2 = Upgrade(cfg).run(release_name, chart2, namespace=ns,
                          values=[{"image": {"tag": "0.7.0"}}])
    deploy2 = _live_deploy(cfg, release_name)
    log(f"  → release v{r2.version} status={r2.status.value}")
    log(f"  → image={deploy2['spec']['template']['spec']['containers'][0]['image']} "
        f"(应为 0.7.0)")
    log(f"  → replicas={deploy2['spec']['replicas']} (应为 10，人工扩容被保留)")

    log("\n" + "=" * 70)
    log("场景 4：helm rollback 1 —— 回滚到 v1")
    log("  ★ rollback 会新增 revision（内容=v1），三方合并仍保留 replicas=10")
    r3 = Rollback(cfg).run(release_name, 1, namespace=ns)
    deploy3 = _live_deploy(cfg, release_name)
    log(f"  → release v{r3.version} status={r3.status.value} (rollback to 1)")
    log(f"  → image={deploy3['spec']['template']['spec']['containers'][0]['image']} "
        f"(应回到 0.6.3)")
    log(f"  → replicas={deploy3['spec']['replicas']} (应为 10，仍保留)")

    log("\n" + "=" * 70)
    log("场景 5：helm upgrade —— chart 主动改 replicas=4（chart-driven 变更）")
    log("  ★ 这次 chart 改了 replicas（2→4），三方合并采用 chart 的新值")
    chart3 = build_chart(tag="0.6.3")
    r4 = Upgrade(cfg).run(release_name, chart3, namespace=ns,
                          values=[{"replicaCount": 4}])
    deploy4 = _live_deploy(cfg, release_name)
    log(f"  → release v{r4.version} status={r4.status.value}")
    log(f"  → replicas={deploy4['spec']['replicas']} (应为 4，chart 覆盖)")

    log("\n" + "=" * 70)
    log("场景 6：开 HPA + Ingress（values 覆盖），看条件渲染")
    chart4 = build_chart(tag="0.6.3")
    r5 = Upgrade(cfg).run(release_name, chart4, namespace=ns, values=[{
        "autoscaling": {"enabled": True, "minReplicas": 2, "maxReplicas": 8},
        "ingress": {"enabled": True, "host": "inference.prod.example.com"},
    }])
    log(f"  → release v{r5.version}，资源数={len(cfg.kube.cluster)} (新增 HPA + Ingress)")
    kinds = sorted({k[0] for k in cfg.kube.cluster})
    log(f"  → 资源种类: {kinds}")

    log("\n" + "=" * 70)
    log("场景 7：helm uninstall —— 卸载，但 PVC 因 resource-policy=keep 保留")
    before = set(cfg.kube.cluster)
    Uninstall(cfg).run(release_name)
    after = set(cfg.kube.cluster)
    log(f"  → 卸载前资源: {sorted(k[0] for k in before)}")
    log(f"  → 卸载后资源: {sorted(k[0] for k in after)} (PVC 应保留)")

    log("\n" + "=" * 70)
    log("release 历史（Secret 列表）:")
    for k in cfg.storage.driver.keys():
        log(f"  - {k}")

    # 返回断言点
    return {
        "v1_replicas": deploy1["spec"]["replicas"],
        "v2_image": deploy2["spec"]["template"]["spec"]["containers"][0]["image"],
        "v2_replicas_preserved": deploy2["spec"]["replicas"],
        "v3_image": deploy3["spec"]["template"]["spec"]["containers"][0]["image"],
        "v3_replicas_preserved": deploy3["spec"]["replicas"],
        "v4_replicas_chart_driven": deploy4["spec"]["replicas"],
        "kinds_after_conditional": kinds,
        "pvc_kept_after_uninstall": any(k[0] == "PersistentVolumeClaim" for k in after),
        "trace": trace,
    }


if __name__ == "__main__":
    run_demo()
