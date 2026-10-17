# Mini Demo：纯 Python 实现向量检索最小栈

本章配套的 Mini Demo 位于 `docs/06-rag/vector-db/mini-demo/`，用纯 Python（仅依赖 numpy）实现了一个**向量检索与 Embedding 基础设施**的最小闭环：

- 三种索引：暴力 Flat、IVF-Flat、简化 HNSW（单层图、确定性构建）
- 两种量化：标量量化 SQ、乘积量化 PQ（含 ADC 查表距离）
- 一个玩具 Embedding 服务：md5 特征哈希模拟推理服务的语义（batch、归一化、截断、请求计数）
- 六个端到端场景：召回率 / 延迟 / 压缩比的实测对比

所有代码 CPU 可运行，随机性全部固定种子，测试无需网络。

## 目录结构

```text
docs/06-rag/vector-db/mini-demo/
├── README.md
├── pyproject.toml
├── conftest.py
├── vector_db_mini/
│   ├── __init__.py
│   ├── metric.py      # L2 / 内积 / 余弦距离（统一"越小越近"约定）
│   ├── quantize.py    # ScalarQuantizer + ProductQuantizer（种子化 k-means）
│   ├── index.py       # FlatIndex / IVFFlatIndex / HNSWIndex（简化图）
│   ├── embed.py       # ToyEmbeddingServer：哈希 bag-of-words + 批处理语义
│   └── demo.py        # run_demo()：六个场景
└── tests/
    ├── test_metric.py      # 9 个测试
    ├── test_quantize.py    # 18 个测试
    ├── test_embed.py       # 12 个测试
    ├── test_index.py       # 23 个测试
    └── test_demo.py        # 7 个测试
```

## 安装与运行

```bash
cd docs/06-rag/vector-db/mini-demo
pip install -e ".[dev]"
pytest tests/ -v
python -m vector_db_mini.demo
```

## 场景与实测输出

测试数据集：2000 条 32 维合成聚类向量（16 个簇 + 高斯噪声，`RandomState(42)`），查询取前 20 条向量。延迟为本机 CPU 实测量级，随机器波动；**召回率与误差为固定种子下的确定值**。

### S1：暴力基线

```text
[S1] FlatIndex exact search
     n=2000 dim=32 avg latency 0.291 ms/query
```

暴力扫描是正确性基准，也是本 Demo 所有召回率的 ground truth。

### S2：IVF-Flat vs 暴力（nprobe 权衡）

```text
[S2] IVFFlatIndex vs FlatIndex (nlist=16)
     nprobe=1  recall@10=0.985  0.035 ms/query
     nprobe=2  recall@10=1.000  0.052 ms/query
     nprobe=4  recall@10=1.000  0.135 ms/query
     nprobe=8  recall@10=1.000  0.206 ms/query
```

聚类数据上 IVF 表现极好：nprobe=2 即满分召回，且比暴力快 5 倍以上。注意这是"簇内分布友好"的合成数据；真实数据簇边界更模糊，nprobe 需要更大（对应第 5 章的 nprobe 调优）。

### S3：简化 HNSW 的 ef 扫描

```text
[S3] HNSWIndex ef sweep (M=8, ef_construction=32)
     ef=4   recall@10=0.760  0.653 ms/query
     ef=8   recall@10=0.760  0.647 ms/query
     ef=16  recall@10=0.880  0.663 ms/query
     ef=32  recall@10=0.955  0.731 ms/query
     ef=64  recall@10=0.970  0.798 ms/query
```

ef 是查询侧 recall/延迟的主旋钮：ef 从 4 到 64，召回提升 21 个百分点，延迟仅增约 20%。Demo 的图是**单层简化版**（真实 HNSW 有多层跳表与邻居修剪），所以绝对延迟比生产实现高，但 ef-recall 权衡的形态与真实系统一致。

### S4：量化对比

```text
[S4] Quantization (vs float64 baseline)
     SQ: ratio=0.1250 rel_err=0.0059 recall@10=0.970
     PQ: ratio=0.0273 rel_err=0.1965 recall@10=0.535
```

SQ8 用 1/8 的内存几乎不掉召回（0.970）；PQ 压缩到 1/36，但小码本（m=8 段 × k=128 质心）的量化误差把召回打到 0.535——这正是生产系统要配 **refine**（粗码召回 + 原始向量精排）的原因。PQ 的 `adc_distances()` 实现了教科书式的不对称距离计算：查询保持 float，对质心查表累加平方距离。

### S5：玩具 Embedding 服务端到端

```text
[S5] ToyEmbeddingServer -> cosine retrieval
     server batches served: 5 (batch_size=4)
     EN query top3 (flat): [0, 1, 8]
     EN query top3 (hnsw): [0, 1, 8]
     ZH query top2 (flat): [5, 4]
```

10 篇文档（中英混合）经哈希 embedding → 余弦最近邻检索。查询 "how does hnsw vector search work" 命中 doc 0（vector database stores embeddings...）、doc 1（hnsw is a graph index...）、doc 8（reranker cross encoder...）；中文查询 "向量 量化 压缩 内存" 命中 doc 5（量化技术压缩向量...）与 doc 4（向量数据库存储 embedding...）。`batches_served=5` 演示了推理服务的组批语义（10 条 / batch_size 4 = 3 批文档 + 2 批查询）。

### S6：过滤检索的 post-filter 陷阱

```text
[S6] Filter trap (blue selectivity ~10%)
     post-filter(top-50 then keep blue): 6 hits, recall@10=0.600
     pre-filter(scan with predicate):    recall@10=1.000
```

先 top-50 再过滤只剩 6 条合格结果，召回 0.60；谓词下推的 pre-filter 召回 1.00。10% 选择率尚且如此，生产上 1% 的租户过滤会更惨（对应第 5 章 ACORN / Filtered-DiskANN 的必要性）。

## 关键代码片段

### 1. 三种索引统一 API

```python
from vector_db_mini import FlatIndex, IVFFlatIndex, HNSWIndex

flat = FlatIndex(dim=32, metric="l2")
flat.add(vectors)                       # 暴力
ivf = IVFFlatIndex(dim=32, nlist=16, nprobe=2)
ivf.add(vectors); ivf.build()           # 倒排
hnsw = HNSWIndex(dim=32, M=8, ef=32)
hnsw.add(vectors)                       # 图（在线构建）
hits = hnsw.search(query, k=10, ef=64)
```

### 2. PQ 的不对称距离计算

```python
from vector_db_mini import ProductQuantizer

pq = ProductQuantizer(m=8, k=128, seed=0).fit(vectors)
codes = pq.encode(vectors)              # (n, 8) 质心 id
dists = pq.adc_distances(query, codes)  # 查表累加, 与"解码后算距离"完全等价
```

### 3. 玩具 Embedding 服务

```python
from vector_db_mini import ToyEmbeddingServer

server = ToyEmbeddingServer(dim=256, batch_size=4)
vecs = server.encode(["向量检索", "vector search"])  # (2, 256), 已归一化
```

## 测试结果

```text
69 passed in 2.55s
```

覆盖：距离度量与归一化等价性、SQ/PQ 编解码与 ADC 正确性、PQ 段数-误差单调性、k-means 确定性、IVF 召回与 nprobe 单调性、HNSW 召回与 ef 单调性与构建确定性、embedding 服务的批处理/截断/确定性、六个端到端场景的断言（9 + 18 + 12 + 23 + 7 = 69）。

## 与生产系统的差异

| 方面 | Mini Demo | 生产系统 |
|---|---|---|
| 距离计算 | numpy 循环 | SIMD/GPU 批量 |
| HNSW | 单层简化图 | 多层跳表 + 修剪（hnswlib/FAISS） |
| IVF | 暴力探测 | PQ 码 + ADC 表 |
| Embedding | md5 特征哈希 | 神经网络（BGE-M3/Qwen3-Embedding 等） |
| 持久化 | 内存 | WAL + 对象存储 + 分层 |
| 分布式/多租户/一致性 | 无 | Milvus/Qdrant 全套能力 |

## 扩展练习

1. 给 `HNSWIndex` 加多层跳表（按指数分布分配层级），对比单层版的构建时间与召回。
2. 实现 `IVFPQIndex`：IVF 倒排 + 段内 PQ 码 + ADC，对比 IVF-Flat 的内存与召回。
3. 给量化加 SQ8 refine 层：PQ 粗排 → 候选取原始向量精排，观察 recall@10 回到什么水平。
4. 用真实 sentence-transformers 模型替换 `ToyEmbeddingServer`，对比哈希 embedding 的检索质量。
5. 实现一个简单的 ACORN-1（搜索时扩展邻居的邻居），在低选择率过滤下对比 post-filter 与 pre-filter。
6. 给 demo 增加删除操作与 tombstone，观察 growing 段暴力扫描的延迟随写入量的变化曲线。

## 小结

Mini Demo 用约 1500 行 Python 复刻了向量检索基础设施的核心链路：**度量 → 量化 → 索引 → 服务 → 检索**，并用 69 个确定性测试把"ef 换召回""nprobe 权衡""量化掉召回""post-filter 陷阱"这些本章的理论结论变成了可复现的数字。
