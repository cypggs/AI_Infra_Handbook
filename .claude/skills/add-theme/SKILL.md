---
name: add-theme
description: Add a new theme to the AI Infra Handbook with the standard 11-chapter structure, optional CPU-runnable Python Mini Demo, navigation/cross-link integration, build verification, and Vercel deployment. Use when the user asks to add a new theme, create a new topic, or continue the next theme in the handbook.
---

# AI Infra Handbook — 新增主题全流程

**One sentence:** 把一个 AI Infra 主题从选题变成线上可访问的 11 章文档 + Mini Demo + 导航集成。

## Agent Quick Start

当这个 skill 被调用时，按以下清单开始：

1. **确认选题**：让用户给出主题中文名、英文/slug 名、所属 section（如 `02-cloud-native`、`04-llmops`）。如果用户没有明确，先列出当前 section 的“计划中”主题供选择。
2. **创建任务列表**：用 `TaskCreate` 创建以下任务，便于用户跟踪：
   - 创建目录与 11 章 Markdown 骨架
   - 实现 Mini Demo（如需要）
   - 更新导航与交叉链接
   - 运行 `pnpm docs:build` 修死链/Vue mustache 错误
   - 运行 Mini Demo 测试
   - 提交、推送并验证线上部署
3. **确定边界**：不重复已有主题；硬件细节引用 `01-foundation/gpu-cuda/`，通用 K8s 机制引用 `02-cloud-native/kubernetes/`，通用 Operator 引用 `02-cloud-native/operator/`，上层引擎引用对应 `04-llmops/` 主题。

**建议的 prompt 模板：**

```text
/add-theme 我要新增一个主题为《[中文主题名]》，slug 为 [theme-slug]，放在 [section] 篇。主题是关于 [一句话描述]。需要包含 [是否需要 Mini Demo / 重点关注的技术点]。
```

**Autonomy rule:** 用户确认主题与范围后，不要再为每个小步骤请求许可。按阶段执行，在阶段边界向用户汇报。

## 新增主题标准结构

每个主题必须位于 `docs/<section>/<theme>/`，URL slug 使用小写和连字符：

```text
docs/<section>/<theme>/
├── index.md                 # 总览：一句话理解、学习目标、章节导航
├── 01-background.md         # 背景与动机
├── 02-core-ideas.md         # 核心思想/核心概念
├── 03-architecture.md       # 架构设计
├── 04-runtime-workflow.md   # Runtime/调度/执行工作流程（章节名可微调）
├── 05-core-modules.md       # 核心模块
├── 06-source-analysis.md    # 源码与生态分析
├── 07-mini-demo.md          # 工程实践：Mini Demo
├── 08-production-practice.md# 企业生产实践
├── 09-best-practices.md     # 最佳实践
├── 10-interview-questions.md# 面试题
├── 11-further-reading.md    # 延伸阅读与学习路径
└── mini-demo/               # 可选，CPU 可运行 Python 包
    ├── pyproject.toml
    ├── README.md
    ├── conftest.py
    ├── <pkg>/               # 包名统一用 snake_case，如 gpu_scheduling_mini
    │   ├── __init__.py
    │   ├── clock.py
    │   ├── apiserver.py
    │   ├── model.py
    │   ├── ...
    │   └── demo.py
    └── tests/
        └── test_*.py
```

## 工作流程

### Phase 1：规划与骨架

1. 选择或确认 section 与 theme slug。
2. 在 `docs/<section>/<theme>/` 创建上述 12 个文件（11 章 + index.md）。
3. 先写 `index.md` 与章节标题/一句话理解，建立内容地图。
4. 如需 Mini Demo，创建 `mini-demo/pyproject.toml` 与 `mini-demo/<pkg>/` 骨架。

### Phase 2：内容填充

1. 按 `references/theme-skeleton.md` 的模板填充各章节。
2. 优先写 01-04 章建立主题轮廓，再深入 05-06 源码，最后写 08-10。
3. `07-mini-demo.md` 必须在 Mini Demo 代码稳定后再定稿，确保测试数、场景输出与实际一致。
4. 全文中注意：
   - 行内代码包含 `{{ }}` 时，用 `<code v-pre>{{ ... }}</code>` 代替反引号。
   - 表格中不要出现裸 `<tag>` 占位符。
   - 不要链接 `mini-demo/README.md` 作为页面，使用反引号代码路径。
   - 多使用 Mermaid 图表解释架构与流程。

### Phase 3：Mini Demo（可选但推荐）

1. 在 `mini-demo/<pkg>/` 中用纯 Python 实现最小可运行语义：
   - `clock.py`：FakeClock / RealClock
   - `apiserver.py`：resourceVersion、乐观锁、generation、watch
   - `model.py`：核心对象
   - 主题对应模块（如 `device_plugin.py`、`scheduler.py` 等）
   - `demo.py`：4-6 个端到端场景
2. 在 `tests/` 中写 25-50 个确定性测试。
3. 本地验证：
   ```bash
   cd docs/<section>/<theme>/mini-demo
   pip install -e ".[dev]"
   pytest tests/ -v
   python -m <pkg>.demo
   ```
4. 更新 `07-mini-demo.md` 与 `mini-demo/README.md` 中的测试数、场景输出。

### Phase 4：导航与交叉链接

必须修改以下文件：

1. `docs/.vitepress/sidebar.ts` — 新增该主题的完整子树。
2. `docs/.vitepress/config.ts` — 顶部 `nav` dropdown 新增总览入口（如适合放在 header）。
3. `docs/<section>/index.md` — 把主题从“计划中”移到“已上线”。
4. `docs/index.md` — 添加 hero action 与当前进度勾选。
5. `docs/guide.md` — 添加“按主题查阅”条目。
6. `docs/10-roadmap/learning-path.md` — 替换/添加为已上线链接。
7. `README.md` — 添加到“已上线主题”列表。
8. 相邻主题 `11-further-reading.md` — 添加回链，至少包含同 section 的上下主题和相关 AI 平台/LLMOps 主题。

### Phase 5：构建验证

运行：

```bash
pnpm docs:build
```

- 必须无死链错误。
- 必须无 Vue mustache 编译错误。
- 修复所有 `(!) Some chunks are larger than 500 kB` 之外的报错。

### Phase 6：提交、推送与线上验证

1. 检查 git status，确保新文件全部 add。
2. 提交：
   ```bash
   git add .
   git commit -m "新增 [中文主题名] 主题：11 章文档 + Mini Demo + 导航集成

   - 新增 docs/<section>/<theme>/ 11 章主题文档
   - 新增 <pkg> 纯 Python Mini Demo（N 测试，M 个端到端场景）
   - 更新 sidebar.ts、config.ts、首页、阅读指南、学习路线、README
   - 在相邻主题延伸阅读中增加回链
   - 通过 pnpm docs:build（无死链）与 pytest（N passed）验证

   Co-Authored-By: Claude <noreply@anthropic.com>"
   ```
3. 推送到 `main`：
   ```bash
   git push origin main
   ```
4. 等待 Vercel 部署完成后验证：
   ```bash
   curl -sL https://ai-infra.cypggs.com/<section>/<theme>/ | grep -o "[主题标题关键字]" | head -1
   ```

## 关键约束

- **Vue mustache**：行内 `{{ }}` 用 `<code v-pre>` 包裹。
- **Dead links**：不要链接 `mini-demo/README.md` 作为页面。
- **Tables**：表格中不要出现裸 `<tag>` 占位符。
- **Mermaid**：支持 `vitepress-plugin-mermaid`，可放心使用 fenced `mermaid`。
- **Commit**：中文 commit message，结尾必须带 `Co-Authored-By: Claude <noreply@anthropic.com>`。
- **Branch**：`main`。
- **Mini Demo 测试数**：确保 `07-mini-demo.md`、`README.md`、`docs/<section>/index.md` 中测试数一致。

## 常见错误与处理

| 现象 | 原因 | 处理 |
|---|---|---|
| `docs:build` 报死链 | 链接到未创建的页面或 `mini-demo/README.md` | 修正为正确路径或反引号 |
| `docs:build` 报 Vue mustache | 行内代码有 `{{ }}` | 改为 `<code v-pre>` |
| Mini Demo 导入错误 | 当前工作目录不在 `mini-demo/` | 用绝对路径或 `cd` 后再执行 |
| 调度/分配测试失败 | Node 命名空间或资源类型键不一致 | 检查 `api.list(kind="Node")` 与 `resource_type` 键 |
| Vercel 线上 404 | 部署尚未完成 | `curl -sL` 轮询，或稍后手动验证 |

## 完成标准

宣布主题完成前必须全部勾选：

- [ ] 11 章 Markdown + index.md 已创建并填充
- [ ] Mini Demo 已创建并通过 `pytest tests/ -v`
- [ ] `python -m <pkg>.demo` 端到端场景通过
- [ ] `pnpm docs:build` 无死链、无 mustache 错误
- [ ] sidebar.ts / config.ts / 首页 / guide.md / learning-path.md / README.md 已更新
- [ ] 相邻主题 `11-further-reading.md` 已添加回链
- [ ] 已提交并推送到 `main`
- [ ] 线上 `https://ai-infra.cypggs.com/<section>/<theme>/` 可访问且内容正确

## 参考文件

- `references/theme-skeleton.md` — 11 章通用骨架模板
- `CLAUDE.md` — 项目全局约定
- `docs/.vitepress/sidebar.ts` — 侧边栏结构样例
- `docs/.vitepress/config.ts` — 顶部导航样例
- 已上线主题（如 `docs/02-cloud-native/gpu-scheduling/`）——最佳实践参照
