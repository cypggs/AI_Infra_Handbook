# 延伸阅读

## 经典论文

**索引算法**

- [HNSW: Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs](https://arxiv.org/abs/1603.09320)（Malkov & Yashunin，TPAMI 2020）——近邻图索引的奠基之作，所有向量库的默认索引。
- [Product Quantization for Nearest Neighbor Search](https://ieeexplore.ieee.org/document/5432202)（Jégou, Douze, Schmid，TPAMI 2011）——PQ 与 IVF-PQ 的原始论文，压缩比 8~32× 的来源。
- [Billion-scale similarity search with GPUs](https://arxiv.org/abs/1702.08734)（Johnson et al.，FAISS，2017/2019）——GPU 向量检索的工程圣经。
- [DiskANN: Fast Accurate Billion-point Nearest Neighbor Search on a Single Node](https://dl.acm.org/doi/10.1145/3318464.3380575)（Subramanya et al.，SIGMOD 2020）——Vamana 图与 SSD 索引。
- [Filtered-DiskANN: Graph Algorithms for Approximate Nearest Neighbor Search with Filters](https://harsha-simhadri.org/pubs/Filtered-DiskANN23.pdf)（Gollapudi et al.，WWW 2023）——标签感知构图。
- [FreshDiskANN: A Fast and Accurate Graph-Based ANN Index for Streaming Similarity Search](https://arxiv.org/abs/2105.09613)（Singh et al.，2021）——磁盘图索引的实时插入。
- [SPFresh: Incremental In-Place Update for Billion-Scale Vector Search](https://arxiv.org/abs/2410.14452)（2023）——LIRE 局部分裂重平衡，动态更新的新范式。
- [ACORN: Performant and Predicate-Agnostic Search Over Vector Embeddings and Structured Data](https://arxiv.org/abs/2403.04871)（Patel et al.，SIGMOD 2024）——过滤检索的图增强，Qdrant 已集成。
- [RaBitQ: Quantizing High-Dimensional Vectors with a Theoretical Error Bound for Approximate Nearest Neighbor Search](https://arxiv.org/abs/2405.12497)（2024/2025）——1-bit 量化的理论突破，Milvus 2.6 生产特性。
- [Filtered ANN Search: A Unified Benchmark and Systematic Experimental Study](https://arxiv.org/abs/2509.07789)（2025）——过滤检索方法学的统一对比。

**Embedding 模型**

- [BGE M3-Embedding](https://arxiv.org/abs/2402.03216)（Chen et al.，2024）——稠密+稀疏+多向量三合一，多语言多粒度。
- [Qwen3 Embedding: Advancing Text Embedding and Reranking Through Foundation Models](https://arxiv.org/abs/2506.05176)（2025）——Qwen3-Embedding/Reranker 技术报告，MTEB 多语榜登顶。
- [Matryoshka Representation Learning](https://arxiv.org/abs/2205.13147)（2022）——MRL 截断维度的原理，text-embedding-3/Qwen3 的灵活维度来源。

## 官方文档与一手资料

- [Milvus 2.6 发布博客（Streaming Node / RaBitQ / Woodpecker）](https://milvus.io/blog/introduce-milvus-2-6-built-for-scale-designed-to-reduce-costs.md) 与 [架构文档](https://milvus.io/docs/v2.6.x/architecture_overview.md)、[Release Notes](https://milvus.io/docs/v2.6.x/release_notes.md)
- [Qdrant 2025 年度回顾](https://qdrant.tech/blog/2025-recap/) 与 [ACORN 过滤检索分析](https://qdrant.tech/blog/filtered-vector-search-acorn/)
- [NVIDIA cuVS 官方仓库](https://github.com/NVIDIA/cuvs) 与 [CAGRA 文档](https://docs.rapids.ai/api/cuvs/stable/cpp_api/neighbors_cagra/)
- [pgvector 仓库](https://github.com/pgvector/pgvector)、[pgvecto.rs](https://github.com/tensorchord/pgvecto.rs)、[Lantern](https://github.com/lanterndata/lantern)
- [Hugging Face Text Embeddings Inference (TEI)](https://github.com/huggingface/text-embeddings-inference)、[Infinity](https://github.com/michaelfeil/infinity)、[FlagEmbedding (BGE)](https://github.com/FlagOpen/FlagEmbedding)
- [MTEB 评测榜](https://huggingface.co/spaces/mteb/leaderboard)——Embedding 模型初筛的公共刻度（使用纪律见 [Benchmark + Evaluation](/07-ai-sre/benchmark-evaluation/)）

## 本手册内延伸阅读

- [RAG](/06-rag/)——向量库的最大下游：chunking、检索策略、rerank 与生成质量。
- [Benchmark + Evaluation](/07-ai-sre/benchmark-evaluation/)——召回率评测集构建、榜单解读与防污染纪律。
- [vLLM](/04-llmops/vllm/)——embedding/pooling 推理与生成共享的 GPU 服务栈。
- [LLM Gateway](/04-llmops/llm-gateway/)——Embedding 服务的网关化部署（鉴权、限流、failover）。
- [存储系统](/01-foundation/storage-systems/)——WAL、分层存储、对象存储的底层原理。
- [GPU CUDA](/01-foundation/gpu-cuda/) 与 [GPU 调度](/02-cloud-native/gpu-scheduling/)——GPU 索引与推理的资源底座。
- [分布式系统](/01-foundation/distributed-systems/)——分片、一致性、协调器的理论基础。
- [Agent Memory](/05-agent/memory/)——向量数据库作为 Agent 长期记忆的持久层。
