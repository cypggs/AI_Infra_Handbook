# 7. 工程实践：一个可跑的 Helm 内核迷你实现

> 一句话理解：本章带你**亲手跑通**一个用纯 Python 写的 Helm 内核模拟器——它把前 6 章讲的 `Chart 结构 → values 深合并 → Go template 渲染 → Release 生命周期 → 三方合并 Patch` 全部串成一条可执行、可断点、可测试的链路；读着它的几百行代码，比读任何文档都更能体会 Helm "为什么这样设计"。

## 7.1 为什么要写一个迷你 Helm

读到这里你已经知道 Helm 的设计动机与架构，但有几个问题光靠文档回答不了：

1. **三方合并到底按什么规则取舍字段？** 看 `kubectl apply` 是两方（live vs new），Helm 为什么非要三方（old vs live vs new）？少了 `old` 会怎样？
2. **Release 为什么每改一次就新增一个 Secret？** 为什么不直接更新一个 ConfigMap？
3. **rollback 为什么会让 revision 号变大？** 为什么不是"原地倒退"？
4. **`helm upgrade` 换了镜像，为什么我之前手动 `kubectl scale` 的副本数没被冲掉？**

这些问题，**写一个能复现这些行为的模拟器，再跑一遍**，答案就刻在脑子里了。这正是本手册"每个主题配一个零依赖 mini-demo"理念的延续（与 [容器运行时 mini-demo](../container-runtime/07-mini-demo.md) 同源）。

本 demo 的设计目标有三：

- **忠实于 Helm 的设计思想**——三方合并、Release 多 revision、Secret 存储、`resource-policy: keep`、`if` 条件渲染，这些语义都要在。
- **零依赖、即跑即看**——不用搭 K8s，不用装 Helm，不用 PyYAML，`python3 -m helm_mini.demo` 直接出结果。
- **代码可读**——每个模块对应 Helm 一个 `pkg/*`，命名一致，读完能反推真实 Helm 的代码地图（见第 6 章）。

## 7.2 目录结构

```
docs/02-cloud-native/helm/mini-demo/
├── README.md
├── pyproject.toml          # 零依赖；pytest 为 dev 依赖；pythonpath=["."]
├── conftest.py             # 把本目录注入 sys.path
├── helm_mini/
│   ├── chart.py            # Chart / ChartMetadata      ≈ pkg/chart
│   ├── values.py           # deep_merge / merge_values  ≈ pkg/chartutil
│   ├── template.py         # 模板引擎子集               ≈ pkg/engine
│   ├── engine.py           # render_chart + Release ctx ≈ pkg/engine
│   ├── yaml_lite.py        # 零依赖 YAML dump/load_all  (替 PyYAML/Go yaml)
│   ├── release.py          # Release / Manifest / Status≈ pkg/release
│   ├── storage.py          # SecretDriver + Storage     ≈ pkg/storage
│   ├── kube.py             # KubeClient + three_way_merge≈ pkg/kube
│   ├── action.py           # Install/Upgrade/Rollback/Uninstall ≈ pkg/action
│   └── demo.py             # GPU 推理 chart + run_demo()
└── tests/                  # 55 个用例
```

每个 `helm_mini/*.py` 顶部都标注了它对应的真实 Helm 包，方便你来回对照第 6 章的源码地图。

## 7.3 跑起来

```bash
cd docs/02-cloud-native/helm/mini-demo

# 完整时序演示（7 个场景，逐行打印）
python3 -m helm_mini.demo

# 单元测试
python3 -m pytest tests/ -q
```

无需 `pip install`——`conftest.py` 已把本目录加入 `sys.path`，`pyproject.toml` 设了 `pythonpath=["."]`。环境只需 Python ≥ 3.9。

`run_demo()` 跑完会打印 7 个场景的完整 trace，最后一行是 release 历史（一串 `sh.helm.release.v1.myrelease.vN` Secret 名）。下面逐场景拆解。

## 7.4 场景拆解：7 个场景各演示了什么

### 场景 1：`helm install` —— 首次部署

```python
chart = build_chart()                              # image 0.6.3, replicas=2
r1 = Install(cfg).run("myrelease", chart, namespace="prod")
```

`build_chart()` 构造一个**生产级 GPU 推理服务** chart：vLLM 镜像、Llama-3-8B、`nvidia.com/gpu: 1`、Service、PVC（带 `helm.sh/resource-policy: keep`），以及被 <code v-pre>{{- if .Values.autoscaling.enabled }}</code> 关闭的 HPA、被 <code v-pre>{{- if .Values.ingress.enabled }}</code> 关闭的 Ingress。

`Install.run()` 的内部步骤（`helm_mini/action.py`，对应真实 Helm `pkg/action/install.go`）：

```python
manifests = self._render(chart, merged, rel)                  # 渲染
release = self._new_release(..., status=PENDING_INSTALL)
self.cfg.storage.create(release)                              # ① 先写 pending Secret
actions = self.cfg.kube.create(manifests)                     # ② 再 apply 到集群
release.status = DEPLOYED
self.cfg.storage.update(release)                              # ③ 更新为 deployed
```

**看点**：① **先写 pending-install Secret，再 apply**。这是 Helm v3 的一个关键工程决策——如果 apply 过程中崩溃，Release 历史里仍留有一条 `pending-install` 记录，下次 `helm list` 能看到，便于诊断。② HPA/Ingress 被 `if` 整段裁掉，所以首次部署只有 3 个资源（Deployment/Service/PVC），印证第 2 章的"模板按值条件渲染"。

### 场景 2：人工扩容（模拟 `kubectl scale`）

```python
cfg.kube.apply_manual_change("Deployment", "prod", "myrelease-inference",
                             ["spec", "replicas"], 10)
```

`apply_manual_change` 直接改集群里的 `spec.replicas=10`，**绕过 Helm**（这正是生产中 `kubectl scale` / 控制器自动伸缩 / 人工 hotfix 的真实路径）。这一步制造了三方合并最关键的前提：**chart 之外的手动改动**。

### 场景 3：`helm upgrade` 换镜像 —— 三方合并登场（★ 核心）

```python
chart2 = build_chart(tag="0.7.0")
r2 = Upgrade(cfg).run("myrelease", chart2, namespace="prod",
                      values=[{"image": {"tag": "0.7.0"}}])
```

`Upgrade.run()` 取出上一版的渲染清单 `old_manifests`，把本次渲染的 `new_manifests` 和集群现状 `live` 一起送进三方合并：

```python
actions = self.cfg.kube.update(old_manifests, new_manifests)
# 内部对每个资源：three_way_merge(old, live, new)
```

结果（demo 打印）：
- `image`：chart 在 old→new 之间改了（0.6.3→0.7.0），**采用 new** → `0.7.0`。
- `replicas`：chart 在 old→new 之间**没改**（两边都是 2），而 live=10 ≠ old=2 → **保留 live 的 10**。

这正是第 3.4 节讲的三方合并规则。把 `old` 去掉、退化成两方合并（live vs new），`replicas` 会被 chart 的 2 直接覆盖，人工扩容就丢了——Helm v3 相比"裸 apply"的安全优势就在这里。

`helm_mini/kube.py` 里 `three_way_merge(old, live, new)` 的核心判断（dict 递归）：

```python
if o == n:                       # chart 没改这一项
    result[k] = live             #   → 保留集群现状（人工改动）
else:                            # chart 改了
    result[k] = three_way_merge(o, live, n)   #   → 用 new，但递归保留嵌套里的人工改动
```

`tests/test_three_way_merge.py` 用 9 个用例把这套语义钉死：chart 没改保 live、chart 改了用 new、chart 删字段但 live 改过则保留、chart 新增字段、人工新增字段保留……。

### 场景 4：`helm rollback 1` —— rollback 是"新增 revision"

```python
r3 = Rollback(cfg).run("myrelease", 1, namespace="prod")
```

一个常见误解是"rollback 让 revision 号变小"。**真相相反**：rollback 取出目标 revision（v1）的清单，**当作一次 upgrade 执行**（同样走三方合并），并新建一个 revision（v4），所以 revision 号是**递增**的。

demo 结果：image 从 0.7.0 回到 0.6.3（chart 改了→用 new），replicas 仍是 10（chart 没改→保 live）。这印证第 4 章的 rollback 时序。

```python
# helm_mini/action.py：rollback 复用 upgrade 的 update 路径
old_manifests = current.manifests            # 当前版（v3）清单
target_manifests = target.manifests          # 目标版（v1）清单
actions = self.cfg.kube.update(old_manifests, target_manifests)
release.status = DEPLOYED                    # 新 revision（v4）= deployed
```

### 场景 5：chart 主动改 replicas —— chart-driven 覆盖

```python
r4 = Upgrade(cfg).run("myrelease", chart3, namespace=ns, values=[{"replicaCount": 4}])
```

这次 **chart 自己改了 replicas（2→4）**，三方合并采用 chart 的新值 → replicas=4。对比场景 3：同样是 `replicas` 字段，**chart 改没改**决定了用 live 还是 new。这条规则简单到一句话，却是 Helm 升级语义的全部精髓。

### 场景 6：条件渲染 —— 开 HPA + Ingress

```python
r5 = Upgrade(cfg).run("myrelease", chart4, namespace=ns, values=[{
    "autoscaling": {"enabled": True, "minReplicas": 2, "maxReplicas": 8},
    "ingress": {"enabled": True, "host": "inference.prod.example.com"},
}])
```

values 覆盖把两个 `enabled: false` 翻成 `true`，模板引擎把原本被 `if` 裁掉的 HPA、Ingress 渲染出来。集群从 3 个资源变 5 个。注意 `update()` 路径对**新增资源**走的是 `create` 分支（chart 新增的资源→创建），对**保留资源**走三方合并。

### 场景 7：`helm uninstall` —— `resource-policy: keep`

```python
Uninstall(cfg).run("myrelease")
```

`KubeClient.delete()` 逆序删资源（workload 先于依赖），但 PVC 因为带 `helm.sh/resource-policy: keep` 被**跳过保留**：

```python
# helm_mini/kube.py
def delete(self, manifests):
    for m in reversed(manifests):
        if self._keep(self.cluster[m.key]):     # resource-policy == "keep"
            actions.append(f"kept (resource-policy=keep) {m.kind}/{m.name}")
            continue
        del self.cluster[m.key]
```

这是 Helm 处理"不可重建状态"（PVC 里的数据、已签发的 TLS 证书、CRD）的标准手法（见第 9 章）。

## 7.5 模板引擎子集：能渲染真实 Deployment 的最小集

`helm_mini/template.py` 是一个 Go `text/template` + Sprig 的极简子集。它支持的真实 chart 模板要素（demo 的 `DEPLOYMENT` 模板全用到了）：

| 能力 | 示例 | 真实用途 |
|---|---|---|
| 取值 | <code v-pre>{{ .Values.image.tag }}</code> | 注入参数 |
| `.Release` / `.Chart` | <code v-pre>{{ .Release.Name }}</code> | 命名、标签 |
| 管道 | <code v-pre>{{ .Values.model.name \| quote }}</code> | YAML 字符串加引号 |
| `default` | <code v-pre>{{ .Values.nameOverride \| default .Chart.Name }}</code> | 缺省值 |
| `trunc` / `trimSuffix` | <code v-pre>{{ ... \| trunc 63 \| trimSuffix "-" }}</code> | 合规命名（K8s 63 字符限制） |
| `toYaml` + `nindent` | <code v-pre>{{- toYaml .Values.resources \| nindent 12 }}</code> | 把整块 dict 缩进塞进去 |
| `define` + `include` | <code v-pre>{{ include "app.labels" . }}</code> | 命名模板复用 |
| `if` / `with` / `range` | <code v-pre>{{- if .Values.autoscaling.enabled }}</code> | 条件、作用域、迭代 |
| 空白修剪 | <code v-pre>{{- ... -}}</code> | 去掉模板标记留下的空行 |

实现上最值得读的两个细节：

1. **<code v-pre>{{- -}}</code> 空白修剪**：`_tokenize` 标记每个动作左右是否带 `-`，`_apply_trim` 把相邻文本片段 `rstrip`/`lstrip`。这就是为什么真实 chart 模板里到处是 <code v-pre>{{-</code> 和 <code v-pre>-}}</code>——不修剪会渲染出大量空行。
2. **作用域模型**：路径首段若是根键（`Values`/`Release`/`Chart`…）就从根解析，否则从当前 `.`（`with`/`range` 绑定的值）解析。这让 <code v-pre>{{ include "x" . }}</code> 在 `with` 块内仍能取到 `.Values`。真实 Go template 在 `with` 内 `.Values` 不可见（更严格），本 demo 做了简化，见 7.6 差异表。

`tests/test_template.py` 的 16 个用例覆盖了取值、管道、`if`/`with`/`range`、修剪、`include`+`nindent` 等。

## 7.6 测试与运行结果

```text
$ python3 -m pytest tests/ -q
.......................................................                  [100%]
55 passed in 0.04s
```

55 个用例分布：

| 测试文件 | 数量 | 覆盖 |
|---|---|---|
| `test_yaml_lite.py` | 8 | dump/load_all 往返、嵌套、序列、标量 |
| `test_values.py` | 6 | 深合并（map 递归、list 整体替换、优先级） |
| `test_template.py` | 16 | 取值/管道/控制结构/修剪/include |
| `test_three_way_merge.py` | 9 | 三方合并全套语义 |
| `test_release_lifecycle.py` | 13 | install/upgrade/rollback/uninstall 状态机 |
| `test_demo.py` | 2 | 端到端断言 + trace 完整性 |

其中 `test_demo.py::test_demo_end_to_end_assertions` 把第 7.4 节每个场景的关键断言写成了代码，是整条链路的回归测试。

## 7.7 与真实 Helm 的差异（诚实说明）

本 demo 是**教学模拟器**，不是 Helm 替代品。差异如下，都不影响对设计思想的理解：

| 维度 | 真实 Helm | 本 demo |
|---|---|---|
| YAML | 完整 YAML（Go yaml / PyYAML） | 自写 `yaml_lite` 子集（块映射/序列/内联项/标量） |
| 模板引擎 | Go `text/template` + 全部 Sprig（200+ 函数） | 子集：取值/管道/if/with/range/include/修剪 + ~12 函数 |
| 三方合并 | K8s **strategic-merge-patch**（list 按 merge key 合并） | dict 递归 + **list 整体替换**（简化，足以演示"replicas 不被覆盖"） |
| Hook / post-renderer / 依赖 / OCI | 完整支持 | 仅保留语义位置/注释，未实现调度 |
| 与 apiserver 交互 | client-go 真实调用 | 内存 dict 模拟集群 |
| Release 存储 | Secret（gzip + base64 + protobuf） | 内存 dict，保留 Secret 命名与"每 revision 一个"语义 |
| `with` 作用域 | 完全重绑（`.Values` 不可见） | 简化：根键仍从根解析（更不易写错） |
| `--reuse-values` | 完整 CLI 支持 | 已实现（见 `action.py` Upgrade 分支） |
| `--atomic` 自动回滚 | 完整支持 | 已实现（失败时把 old 重新 apply + 新建 rollback revision） |

想跑真实 Helm，装一个 kind 集群 + `helm install` 即可；本 demo 的价值在于**让你在 5 分钟内读懂机制**，而不是在生产里替代 Helm。

## 本章小结

- 这个 mini-demo 用纯 Python 把 Helm 五大核心机制（Chart/values/模板/Release/三方合并）串成一条可执行链路，是前 6 章理论的"可触摸版本"。
- **场景 3/4/5** 是全文的高潮：同一个 `replicas` 字段，在"chart 没改→保 live（人工扩容）"和"chart 改了→用 new"之间切换，三方合并的全部精髓都在这几行 `three_way_merge` 里。
- 代码命名刻意与真实 Helm 的 `pkg/*` 对齐（`action`/`engine`/`kube`/`storage`/`release`），读完 demo 再翻第 6 章源码地图会非常顺。
- 诚实的差异表提醒你：真实 Helm 用 strategic-merge-patch 处理 list、用 protobuf 存 Secret、有完整的 Hook/依赖/OCI——这些是生产级能力，本 demo 用简化版保留了**语义**而非**全部实现**。

**参考来源**

- 本仓库：`docs/02-cloud-native/helm/mini-demo/`（全部源码 + 55 个测试）
- 第 3 章 3.4 节：三方合并的设计动机
- 第 4 章：Release 状态机与 install/upgrade/rollback/uninstall 时序
- 第 6 章：helm/helm 源码地图（demo 各模块对应的真实包）
