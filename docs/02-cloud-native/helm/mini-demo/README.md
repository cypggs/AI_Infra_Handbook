# Helm Mini-Demo —— 微型 Helm 教学模拟器

一个**纯 Python、零第三方依赖**的 Helm 内核模拟器：把 Helm 的核心机制
（Chart 结构 → values 深合并 → Go template 渲染 → Release 生命周期 → 三方合并 Patch）
用几百行可读代码实现，让你**读着代码**就能理解 Helm 的设计动机与运行机制，
而不必先搭一个 K8s 集群。

> 与容器运行时 mini-demo 一致的“纯 Python、无需安装”理念：YAML 用自带的
> `yaml_lite` 实现（见下“与真实 Helm 差异表”）。

## 快速开始

```bash
cd docs/02-cloud-native/helm/mini-demo

# 跑完整时序演示
python3 -m helm_mini.demo

# 跑测试（55 个）
python3 -m pytest tests/ -q
```

无需 `pip install`：`conftest.py` 已把本目录加入 `sys.path`。

## 演示场景（`run_demo()` 的 7 个场景）

| 场景 | 命令 | 验证点 |
|---|---|---|
| 1 | `helm install`（chart v1, image 0.6.3, replicas=2） | release v1 deployed；Secret `sh.helm.release.v1.<name>.v1`；集群 3 个资源（HPA/Ingress 被 `if` 关闭） |
| 2 | 人工 `kubectl scale --replicas=10` | 集群 replicas=10（模拟 chart 之外的手动改动） |
| 3 | `helm upgrade` 换镜像 0.7.0（chart replicas 仍=2） | **三方合并：replicas 保留 10，image→0.7.0** |
| 4 | `helm rollback 1` | **rollback 新增 revision**，image 回 0.6.3，replicas 仍保留 10 |
| 5 | `helm upgrade`，chart 主动改 replicas=4 | **chart-driven 变更**：replicas→4（覆盖手动值） |
| 6 | values 开 HPA + Ingress | 条件渲染：新增 HPA、Ingress |
| 7 | `helm uninstall` | 资源被删，但 PVC 因 `helm.sh/resource-policy: keep` **保留** |

核心看点是**场景 3/4**：Helm v3 的三方合并如何在升级/回滚时**保留 chart 之外的手动改动**，
同时**正确应用 chart 自身的变化**。这是 Helm 相比“裸 `kubectl apply`”的根本安全优势。

## 目录结构

```
helm_mini/
├── chart.py        # Chart / ChartMetadata（version vs appVersion vs apiVersion）
├── values.py       # deep_merge / merge_values（map 递归、list 整体替换、优先级）
├── template.py     # 模板引擎：Go template + Sprig 子集（if/with/range/include/管道/修剪）
├── engine.py       # render_chart：Chart+values+Release ctx -> Manifest 列表
├── yaml_lite.py    # 零依赖 YAML 序列化/解析（dump / load_all）
├── release.py      # Release / Manifest / ReleaseStatus（pending-*/deployed/superseded/...）
├── storage.py      # SecretDriver + Storage（每 revision 一个 Secret，history-max）
├── kube.py         # KubeClient + three_way_merge（三方合并 Patch，核心）
├── action.py       # Install / Upgrade / Rollback / Uninstall（= pkg/action）
└── demo.py         # GPU 推理服务 chart + run_demo()
```

## 三方合并怎么读

打开 `helm_mini/kube.py` 的 `three_way_merge(old, live, new)`，它是 Helm v3 升级的核心：

- 对每个字段同时参考 **old**（上一版 chart 渲染的）、**live**（集群现状）、**new**（本次 chart 渲染的）。
- `old == new`（chart 没改）→ 保留 `live`（人工改动）。
- `old != new`（chart 改了）→ 用 `new`。
- chart 删除的字段：若 live 未被人工改过 → 删除；被改过 → 保留。
- 人工新增的字段（old/new 都没有）→ 保留。

`tests/test_three_way_merge.py` 用 9 个用例把这套语义钉死。

## 与真实 Helm 的差异（诚实说明）

| 维度 | 真实 Helm | 本 demo |
|---|---|---|
| YAML | 完整 YAML（PyYAML/Go yaml） | 自写 `yaml_lite` 子集（块映射/序列/内联映射项/标量） |
| 模板引擎 | Go `text/template` + 全部 Sprig(200+) | 子集：取值/管道/if/with/range/include/修剪 + ~12 函数 |
| 三方合并 | K8s strategic-merge-patch（list 按 merge key 合并） | dict 递归 + **list 整体替换**（简化，足以演示“replicas 不被覆盖”） |
| Hook / post-renderer / 依赖 / OCI | 完整支持 | 仅保留语义位置/注释，未实现调度 |
| 与 apiserver 交互 | client-go 真实调用 | 内存 dict 模拟集群 |
| Release 存储 | Secret（gzip+base64 protobuf） | 内存 dict，保留 Secret 命名与“每 revision 一个”语义 |
| `with` 作用域 | 完全重绑（`.Values` 不可见） | 简化：根键仍从根解析，更不易写错 |

这些简化都**不影响**对 Helm 设计思想的理解——本 demo 的目标是“读懂机制”，
不是“替代 Helm”。要跑真实 Helm，装个 kind 集群即可。

## 运行环境

- Python ≥ 3.9（用了 dataclass、type hints、f-string）。
- 无操作系统限制（纯计算，不碰 Linux 系统调用，不像容器运行时 demo）。
