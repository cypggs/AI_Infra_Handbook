# 核心模块：索引算法、量化、GPU 与过滤检索

本章深入向量数据库的引擎室：五大核心模块——近邻图索引（HNSW）、倒排量化（IVF-PQ）、磁盘图索引（DiskANN/Vamana）、量化编码体系、GPU 索引（CAGRA）——以及一个工程上最容易踩坑的横切关注点：过滤检索。

## 5.1 HNSW：分层小世界图

HNSW（Hierarchical Navigable Small World，Malkov & Yashunin，TPAMI 2020）是内存 ANN 索引的事实标准。它由两部分思想组成：

- **NSW（Navigable Small World）**：单张近邻图，节点连接空间中最近的 M 个邻居。查询时从入口点**贪心遍历**——每一步走到离 query 最近的邻居，直到无法更近。图的"可导航小世界"性质（短路径 + 局部聚合）保证贪心陷入局部最优的概率很低。
- **分层（Skip-List 化）**：每个节点按指数衰减概率 `p = 1/level_mult` 获得一个层级。上层节点稀疏，作为"高速公路"；查询从最高层的入口点逐层下降，每层贪心到局部最优后进入下一层，第 0 层做精细搜索。

### 查询算法（第 0 层 beam search）

```text
SEARCH(q, ef, entry):
    C = 最小堆(候选); R = 最大堆(结果, 容量 ef)
    将 entry 放入 C 和 R
    while C 非空:
        c = C.pop最近点
        if d(c) > R中最远点距离: break      # 早停：候选不可能更好
        for n in c 的邻居:
            if n 已访问: continue
            if d(n) < R中最远点距离 或 |R| < ef:
                C.push(n); R.push(n)
                if |R| > ef: R.pop最远点
    return R 中距离最近的 k 个
```

三个核心参数：

| 参数 | 作用 | 调优方向 |
|---|---|---|
| M | 每节点最大邻居数（第 0 层 2M） | 越大图越连通、recall 越高、内存越大（建索引慢） |
| ef_construction | 建图时的 beam 宽度 | 越大图质量越好、建索引越慢 |
| ef（查询时） | 查询 beam 宽度 | recall 与延迟的主旋钮，可在查询侧按 SLO 动态调 |

### 插入算法

```text
INSERT(v):
    level = 按指数分布随机采样 v 的层级
    ep = 顶层入口点
    for L in 顶层..1:                      # 上层只做贪心定位
        ep = GREEDY(v, ep, 只走到局部最优)
    W = BEAM_SEARCH(v, ef_construction)    # 第 0 层找邻居候选
    neighbors = W 中最近的 M 个
    与 neighbors 连边；对每个邻居执行"邻居溢出修剪"
       （度数超 2M 时按启发式断开最远边）
    if v 的层级高于当前最高层: 入口点更新为 v
```

**删除的处理**：标准 HNSW 不物理删点，查询时跳过 tombstone 即可；被删点造成的断边靠定期重建修复。Mini Demo 实现了一个确定性简化版：单层图 + 确定性互连（详见[Mini Demo](07-mini-demo)）。

## 5.2 IVF-PQ：倒排 + 乘积量化

IVF-PQ 是 FAISS 时代的主力，至今仍是极致内存压缩场景的首选。

**IVF（倒排文件）**：对数据做 k-means（nlist 个质心），每个向量归属最近质心的 posting list。查询只探测与 query 最近的 nprobe 个质心的 list。

**PQ（乘积量化）**：把 d 维向量切成 m 段，每段独立做 k-means（每段 k 个质心，通常 k=256，码长 8 bit）。向量被编码为 m 个字节（每段一个质心 id）。

**ADC（非对称距离计算）**——PQ 的灵魂：

```text
查询时:
  for 每段 i:
      LUT[i][j] = || q_i - centroid_{i,j} ||^2    # 预计算查表, m×k 次
  对候选向量（码 c_1..c_m）:
      dist ≈ Σ_i LUT[i][c_i]                       # m 次查表加法
```

查询向量保持 float32，只有数据库向量被量化——"非对称"避免了二次量化误差。10 亿向量 × 768 维：原始 3 TB，PQ(m=96, 8bit) 后仅 96 GB，距离计算从 768 次乘法变成 96 次查表。

**参数**：nlist（质心数，经验值约 `sqrt(n)` 到 n/100）、nprobe（探测簇数）、m（段数）、k（每段质心数）。nprobe 增大单调提升 recall 与延迟（Mini Demo S2 实测 nprobe 1→8 时 recall 0.985→1.000）。

## 5.3 DiskANN 与 Vamana：SSD 上的图索引

DiskANN（Microsoft，SIGMOD 2020）解决的是"内存装不下"的问题：把近邻图放到 SSD 上，每次查询只做少量顺序/随机读。

**Vamana 图构建**：与 HNSW 不同，Vamana 是**离线图算法**，核心是 α-RNG（α-relative neighborhood graph）剪枝：

```text
VAMANA(vectors, α > 1, L):
    从随机图开始
    repeat R 轮:
        for 每个节点 v:
            从入口贪心 + beam search 找 v 的 L 个最近候选
            按距离升序遍历候选 c:
                if 存在已选邻居 u 使 α·d(c, u) ≤ d(v, c):
                    skip c          # α-RNG: c 可由已有邻居"绕过"
                else:
                    选择 c 为邻居   # 长边优先保留 → 图直径小
    控制每节点出度 ≤ R
```

α 剪枝的效果：**短边被长边替代**（若 α·d(c,u) ≤ d(v,c)，即经由 u 到 c 只比直达远一点），从而图直径大幅缩小，贪心遍历更少跳数。代价是离线构建更贵。

**查询**：第 0 层 beam search 的磁盘版——维护容量为 beam width（如 8~32）的内存优先队列，每步把队首节点的邻居列表从 SSD 整页读入。10 亿向量、单节点：内存仅需放量化向量与缓存，延迟 5~15ms。

**Filtered-DiskANN（WWW 2023）**：把标签（如租户、类目）纳入构图——FilteredVamana 只在同标签邻居间连边，StitchedVamana 为标签组合分别建图再缝合。解决"带过滤条件的 ANN"在图遍历上的失效问题（见 5.6）。

**动态更新演进**：FreshDiskANN（2021）用内存 buffer 吸收插入 + 周期性 merge；SPFresh（2023）改用"分区分裂 + 局部重平衡"，把全局重建开销变成局部操作，单机 10GB 内存支撑 4K QPS 查询 + 2K QPS 更新。Milvus 的 DiskANN 索引类型即源自这一系工作。

## 5.4 量化编码体系

量化模块的输入是原始向量，输出是"码 + 元数据"，查询侧提供 ADC 距离。生产系统的完整工具箱：

| 技术 | 机制 | 备注 |
|---|---|---|
| SQ8 | 每维 float → uint8（min/max 线性映射） | 召回损失最小，Milvus/ES 默认压缩档 |
| SQ4 / int8 原生向量 | 更激进的标量量化 | Milvus 2.6 支持 INT8 向量类型（端到端 int8） |
| PQ | 分段质心码 | 压缩比高，召回靠 ADC + refine |
| BQ | 每维 1 bit（符号） | 32× 压缩，召回需要 refine 救 |
| RaBitQ | 随机正交旋转 → 1-bit 量化 → 残差 refine | 理论界更优；Milvus 2.6 集成，官方称内存降 72%、recall 94.9%（refine 后） |
| 非对称量化 | 查询侧也量化但用更高精度码本 | Qdrant 2025 新增 |

设计要点：

1. **旋转/变换在前**：RaBitQ 先随机旋转再符号量化，利用了高维向量各向异性的特点——旋转后各维方差趋同，1-bit 的信息损失最小化。
2. **Refine 是标配**：粗码召回 top-αk，再用原始向量或 SQ8 残差精排。内存账 = 粗码（极省） + refine 层（按需加载或只存候选）。
3. **训练数据要代表性**：PQ/SQ 的 min/max 与质心来自采样，分布漂移后量化误差增大；生产上定期用新数据重训练并重建索引。

## 5.5 GPU 向量索引：cuVS 与 CAGRA

NVIDIA **cuVS**（CUDA Vector Search，前身 RAFT）是 GPU 向量检索的标准库，核心算法 **CAGRA**（CUDA ANN GRAph-based algorithm）：

- **GPU 原生构图与查询**：HNSW 的并行化受限于"插点必须串行连边"，CAGRA 改为**先 brute-force 建 knn-graph 再迭代精化**（与 Vamana 类似但全在 GPU 上），构建吞吐比 CPU HNSW 高 12~30 倍（千万级向量分钟级建完）。
- **图格式互操作**：CAGRA 构图的结果可以直接被 CPU 当 HNSW 图搜索（GPU-build / CPU-serve），这是"用 GPU 加速索引构建、用 CPU 做查询服务"混合架构的基础。
- **支持数据类型**：fp32 / fp16 / int8 / uint8，天然配合量化。

集成现状：FAISS（faiss-gpu）、Milvus（GPU_CAGRA / GPU_BRUTE_FORCE，经 Knowhere）、OpenSearch（faiss GPU 引擎）、Redis、KDB.AI 都已接入 cuVS。

**什么时候该上 GPU**：

| 场景 | 建议 |
|---|---|
| 索引构建太慢（亿级向量全量构建数小时） | GPU 建图，收益最直接 |
| 热集小（千万级）+ 极高 QPS（数万） | GPU brute-force / CAGRA 服务，延迟可到亚毫秒 |
| 十亿级 + 中等 QPS | 通常 DiskANN（SSD）更划算；GPU 留作构建加速 |
| 数据频繁更新 | GPU 索引重建成本高，慎用于高频更新段 |

## 5.6 过滤检索：最容易踩的坑

RAG 的真实查询几乎都带过滤条件："只在产品文档里搜"、"只搜该租户的 chunk"。朴素做法是"先 ANN 出 top-k 再过滤"，这在过滤选择率（selectivity）低时会**灾难性漏召回**——top-k 里的合格向量可能远少于 k。

```mermaid
flowchart TB
    subgraph 错误：post-filter
        A1[ANN top-100] --> B1[过滤 tenant=A] --> C1[只剩 6 条<br/>召回崩了]
    end
    subgraph 正确：pre-filter / 图感知
        A2[过滤感知遍历<br/>只访问 tenant=A 的节点] --> B2[top-10 全部合格]
    end
```

三种工程解法（也是学术热点）：

1. **ACORN**（SIGMOD 2024，Qdrant 已集成）：谓词无关的图遍历增强。ACORN-1 在搜索时把每个节点的**邻居的邻居**也纳入候选，避免"当前节点全被过滤掉时遍历断链"；ACORN-γ 在建索引时预先把邻居集扩大 γ 倍。低选择率（<1%）下比传统 filterable HNSW 吞吐高 2~1000 倍。
2. **Filtered-DiskANN**（WWW 2023）：构图时把标签纳入连边决策，同标签节点天然连通；适合标签集合稳定的场景。
3. **按谓词分区**：把高频过滤维度（租户）做成 partition key，物理隔离；查询直接路由到子集。代价是跨分区查询与数据倾斜。

**实践判据**：选择率 >20% 时 post-filter 也基本可用；选择率 <5% 必须用 pre-filter 或图感知方案。Mini Demo S6 用 10% 选择率实测：post-filter 召回 0.60，pre-filter 召回 1.00。

## 5.7 混合检索模块

生产 RAG 普遍是"稠密向量 + 稀疏信号"双路：

- **稠密路**：Embedding → ANN。抓语义相似。
- **稀疏路**：BM25 / learned sparse（BGE-M3 的 sparse 输出、SPLADE 系）。抓精确词面匹配（型号、错误码、人名）。
- **归并**：RRF（Reciprocal Rank Fusion）或加权打分，再接 reranker。

向量数据库的演进方向就是**把三路都装进一个系统**：Milvus 2.6 内置 BM25 全文索引与 JSON 过滤；Qdrant 2025 加入原生全文过滤；Vespa 一直支持 tensor + 传统检索混合。对基础设施团队，这减少了"一个 RAG 三个系统"的运维面。

## 小结

- HNSW = 分层跳表 + NSW 贪心遍历，ef/M/ef_construction 三参数统治召回-延迟-内存三角。
- IVF-PQ = 倒排剪枝 + 乘积量化 + ADC 查表，是极致压缩场景的标准答案。
- DiskANN/Vamana 用 α-RNG 剪枝把图搬到 SSD，FreshDiskANN/SPFresh 系列解决了磁盘图的实时更新。
- RaBitQ（旋转 + 1-bit + refine）代表了量化技术的最新水位；旋转在前、refine 标配是两个工程要点。
- GPU 索引（cuVS/CAGRA）的最大红利在**建图**，查询侧适合热集小、QPS 极高的场景。
- 过滤检索必须按选择率选策略：低选择率下 post-filter 是静默的正确性事故，ACORN / Filtered-DiskANN / 分区是三条正路。
