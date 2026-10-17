# 案例研究篇

本章节通过分析顶尖公司与产品的 AI 基础设施实践，提炼可复用的工程经验。

## 已上线主题

- [OpenAI](/09-case-study/openai/) — 从 GPT 训练集群到 ChatGPT 推理服务的完整基础设施演化
- [Anthropic](/09-case-study/anthropic/) — 宪法对齐、机制可解释性、Trainium/Colossus 异构算力与 prompt caching 推理工程
- [Meta](/09-case-study/meta/) — 开放权重、OCP 硬件协同设计、RoCE/InfiniBand 双网络织物、SDC 治理与 >95% 有效训练时间、MTIA 自研硅
- [Google](/09-case-study/google/) — TPU 自研硅（MXU/SparseCore/3D-torus/OCS）、NSDI'24 双路径恢复（99.98% 可用率）、GSPMD/Pathways 自动并行、开放软件栈 + 闭源硬件
- [DeepSeek](/09-case-study/deepseek/) — 算法-系统协同设计：DualPipe、细粒度 EP、FP8 混合精度、MLA、3FS/DeepEP 开源栈，278.8 万 H800 GPU 小时训练 V3 的方法论
- [xAI](/09-case-study/xai/) — Memphis Colossus：122 天 10 万卡单训练域、供电/液冷/网络 fabric 工程、"速度即战略"的集群建设组织学
- [Perplexity](/09-case-study/perplexity/) — 答案引擎的推理经济学：不训基础模型、靠模型路由/缓存/流式延迟取胜，Sonar 系列与 r1-1776 开源

## 计划中主题

- Cursor

## 一句话理解

> 最好的老师不是论文，而是那些在真实生产环境中 scale 到亿级用户的系统。

每个案例都会从**设计动机 → 架构设计 → 源码实现 → 工程实践 → 生产落地**五个维度进行拆解，并结合本手册其他主题（LLMOps、Agent、RAG、AI SRE、安全）的交叉视角，帮助读者把散落的知识点连成网络。
