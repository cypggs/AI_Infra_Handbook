# 生态与实现分析：主流系统对比与源码级解读

本章做两件事：给出现阶段主流向量数据库的横向对比（截至 2026-10），以及对 HNSW、Vamana、Qdrant segment 等核心实现做源码/论文级的概念解读。

## 6.1 主流系统对比

| 系统 | 实现语言 | 索引类型 | 量化 | 过滤检索 | 部署形态 | 典型适用规模 |
|---|---|---|---|---|---|---|
| Milvus 2.6 | Go + C++ (Knowhere) | HNSW / IVF-PQ / DiskANN / GPU_CAGRA / BM25 | SQ8/PQ/BQ/RaBitQ + refine | 标量过滤 + JSON 索引 + ACORN（部分） | 分布式集群 / 云 | 亿级~十亿级 |
| Qdrant | Rust | HNSW + ACORN | scalar/PQ/1.5~2-bit/非对称 | 原生 payload 过滤 + ACORN + 全文 | 单进程 / 云（Multi-AZ） | 千万~亿级 |
| Weaviate | Go | HNSW + 倒排 | PQ/BQ | 强 schema 过滤 | 集群 / 云 | 千万~亿级 |
| pgvector | C (PG 扩展) | HNSW / IVFFlat | 外部量化（如向量半精度） | SQL 全部能力 | PG 插件 | 百万~千万级 |
| pgvecto.rs | Rust (PG 扩展) | HNSW 变体 | 部分 | SQL 全部能力 | PG 插件 | 百万级 |
| Lantern | C (PG 扩展) | 自研 HNSW 变体 | 部分 | SQL 全部能力 | PG 插件 | 百万级 |
| LanceDB | Rust | IVF-PQ / HNSW (磁盘) | PQ/SQ | 谓词下推 | 嵌入式 / 无服务器 | 千万级（湖上更大） |
| Vespa | Java + C++ | HNSW + 倒排 + tensor | 部分 | 与结构化查询统一 | 自托管集群 | 亿级 |
| Redis Vector | C | FLAT / HNSW | FP16/BF16/INT8 | Redis 查询 | 单实例 / Cluster | 百万级 |
| Elasticsearch / OpenSearch | Java | Lucene HNSW | int8_hnsq + rescoring（ES）；SQ/BQ（OS） | ES 全套过滤 | 集群 | 千万级 |

选型速查：

- **十亿级 + 高写入 + 自托管**：Milvus（流批分离 + 对象存储 + GPU 建图）。
- **亿级以内 + 运维极简 + 过滤复杂**：Qdrant（单进程、payload 过滤、ACORN）。
- **已有 PG + 百万级**：pgvector；写入敏感可评估 pgvecto.rs。
- **向量跟着数据湖走 / 边缘嵌入**：LanceDB。
- **向量是搜索系统的附加维度**：ES/OpenSearch/Redis/Vespa。
- **重混合检索（结构化 + 向量 + 稀疏一体）**：Vespa 或 Milvus 2.6 内置 BM25。

## 6.2 HNSW 源码级解读（以 hnswlib 概念模型为例）

hnswlib（C++，HNSW 作者的参考实现）的结构揭示了 HNSW 工程化的三个关键决策：

### 内存布局

```text
元素数组（连续存储）:
  [label_0][vector_0][linklist_0] [label_1][vector_1][linklist_1] ...
                          |
linklist 按层分块:  [level 2: nb_cnt, nb_ids...]
                   [level 1: nb_cnt, nb_ids...]
                   [level 0: nb_cnt, nb_ids... (最多 2M 个)]
```

- 向量与图同址存储（cache-friendly）：遍历图时读邻居 id → 邻居向量在同一缓存行附近。
- 邻居列表用 `(count, id[])` 紧凑编码，M 是编译期概念、运行期只是容量上限。

### 层级分配

```text
level(v): L = 0; while (uniform() < 1/M) L++;   # 指数衰减
```

M=16 时，约 6% 节点升 1 层，0.4% 升 2 层——上层极稀疏，保证高速公路跳数 `O(log n)`。入口点永远是当前最高层节点（最大 label 技巧）。

### 搜索热点

- `visited` 集合用**位图**（每 query 复用，query 结束清零而不是重新分配）——千万级图上频繁 new 会拖垮 QPS。
- 候选堆与结果堆分离：候选堆驱动遍历，结果堆只留 ef 个最好的；早停条件是"当前候选已差于结果堆最差"。
- 距离计算向量化（SIMD）：HNSW 的 CPU 瓶颈 80% 在距离计算，hnswlib/usearch 用 AVX2/NEON 批量算。

### 我们的 Mini Demo 与真实实现的差距

`vector_db_mini.HNSWIndex` 是有意简化的教学模型：单层图、暴力找邻居、确定性互连（无随机层级、无邻居修剪启发式）。它保留了 HNSW 的核心直觉——**贪心 + beam search 在可导航图上的访问节点数与数据规模弱相关**——但去掉了工程复杂度。差异清单：

| 方面 | Mini Demo | hnswlib/FAISS |
|---|---|---|
| 层数 | 1 层 | 多层跳表 |
| 邻居选择 | beam search 取前 M | beam search + 启发式修剪（按距离分布选边） |
| 互连 | 确定性反向链接（度上限 2M） | 双向连边 + 溢出修剪 |
| 邻居搜索 | 暴力距离计算 | 复用图遍历 + SIMD |
| 删除 | 不支持 | tombstone + 重建 |

## 6.3 DiskANN 的 Vamana：α-RNG 的直觉

Vamana 论文（SIGMOD 2020）最重要的洞察是：**好的 ANN 图 = 高召回所需的最小连通性 + 尽量小的直径**。α-RNG 剪精准则：

```
候选 c 被接受为 v 的邻居，当且仅当:
    不存在已选邻居 u 使得  α·d(c, u) ≤ d(v, c)     (α > 1)
```

读法：如果"从 v 到 u 再到 c"的绕行距离不超过直达距离的 α 倍，那么边 v→c 就是冗余的——遍历完全可以经过 u 顺路到 c。α=1 时退化为 RNG（图太稀、直径大）；α 越大保留的"捷径"越多。DiskANN 论文取 α≈1.2，配合 R 轮全局迭代，把随机初始图的直径压到极小。

对比 HNSW 的启发式修剪（偏向"距离上分散"的邻居），Vamana 的 α-RNG 是**显式几何准则**，且作为离线算法可以全局多轮优化——这是它能搬到 SSD 场景（读放大敏感、要求极少跳数）的原因。

## 6.4 Qdrant 的 Segment 设计解读

Qdrant 的单进程架构把 LSM 的段思想搬到向量索引：

- **可变 segment**：接收新写入（内存 + WAL），不建 ANN 索引，查询走 brute-force。内存上限到阈值即 sealed。
- **不可变 segment**：sealed 后异步建 HNSW；文件级不可变，天然支持版本快照、零拷贝 mmap、并发读。
- **查询 = 所有 segment 结果归并**：可变段的 brute-force 保证"写即可见"，代价是 growing 越大查询越慢——所以 segment 尺寸阈值是核心调优参数（默认 128MB 向量数据量级）。
- **量化内联**：sealed 段的量化码与图存储在同文件（inline storage），磁盘场景读放大低；2026 版本起不可变 segment 默认单文件 mmap + io_uring 批量读。

这套设计用"不可变"换简单性：没有锁、没有原地更新、compaction 就是生成新 segment 原子切换——向量场景删除少、追加多的负载特征下非常划算。

## 6.5 Knowhere：Milvus 的索引抽象层

Milvus 的索引能力来自 C++ 库 Knowhere，它对上层屏蔽了索引差异：

```text
Knowhere Index 接口:
  Train(dataset)   # 量化类索引的训练（采样质心/旋转矩阵）
  Add(dataset)     # 编码/构图
  Query(dataset)   # 查询（CPU 版）
  Serialize/Deserialize
```

底层按索引类型委托：FAISS（IVF 系）、hnswlib（HNSW）、DiskANN 移植（Vamana）、cuVS（GPU_CAGRA/GPU_BRUTE_FORCE）、自研（SCANN-like、RaBitQ 集成）。工程启示：**索引抽象层是向量数据库可插拔性的关键**，新算法（如 RaBitQ 2024 年论文 → Milvus 2.6 生产特性）的落地周期因此从"改系统"变成"加一个 Knowhere 索引类型"。

## 6.6 Embedding 推理服务的实现分析

向量数据库的上游是 Embedding 服务。生产形态三类：

1. **云 API**：OpenAI text-embedding-3-large（3072 维，支持 MRL 截断到 256 维）、Cohere Embed v4（128K 上下文、多模态）、Voyage 4 系（32K 上下文）、Gemini Embedding（多模态）。省去运维，但数据出域、成本随量线性增长。
2. **自托管 GPU 服务**：
   - **TEI**（Hugging Face Text Embeddings Inference，Rust）：业界事实标准，支持批处理、动态 padding、OpenAI 兼容 API、FP16/INT8；适合 BGE / E5 / GTE 类模型。
   - **Infinity**（michaelfeil/infinity）：Python 生态友好，支持多种后端（ONNX/CT2），同样提供 OpenAI 兼容接口。
   - **vLLM pooling 模式**：已支持 embedding 类模型推理，与生成模型共享一套 GPU 调度（见 [vLLM 主题](/04-llmops/vllm/)）。
3. **CPU/边缘**：fastembed（ONNX 量化版小模型）、onnxruntime，QPS 要求低时的省钱选项。

服务化要点：batch 动态组批（TEI 的核心优化）、请求排队与并发上限（embedding 也是 GPU 密集）、输出归一化策略与向量库 metric 对齐、模型版本与维度固定（升级 = 全量重建索引，见第 8 章）。

## 小结

- 选型没有银弹：Milvus 吃大规模高写入，Qdrant 吃简单运维与复杂过滤，pgvector 吃 PG 生态，LanceDB 吃湖与边缘，Vespa 吃混合检索。
- HNSW 的工程本质：紧凑同址存储 + 位图 visited + SIMD 距离计算；层数服从指数分布保证 `O(log n)` 跳数。
- Vamana 的 α-RNG 给出显式的"好图"几何准则——小直径优先于局部密度，这是磁盘索引与 HNSW 的本质分歧。
- Segment 不可变化（Qdrant）与流批分离（Milvus）是同一问题的两种解法：如何让"持续写入"与"高效索引"共存。
