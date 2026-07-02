# 6. 源码分析

## 仓库结构

Triton Inference Server 的源码分散在多个仓库中：

| 仓库 | 内容 |
|---|---|
| [server](https://github.com/triton-inference-server/server) | Triton core：HTTP/gRPC server、scheduler、model manager、metrics |
| [backend](https://github.com/triton-inference-server/backend) | Backend API 的头文件与公共库 |
| [core](https://github.com/triton-inference-server/core) | Triton server 的核心 C++ 库（被 server 依赖） |
| [common](https://github.com/triton-inference-server/common) | 公共工具与协议定义 |
| [client](https://github.com/triton-inference-server/client) | Python / C++ / Java 客户端 |
| [tensorrtllm_backend](https://github.com/triton-inference-server/tensorrtllm_backend) | TensorRT-LLM backend |
| [vllm_backend](https://github.com/triton-inference-server/vllm_backend) | vLLM backend |
| [model_analyzer](https://github.com/triton-inference-server/model_analyzer) | 配置调优工具 |

## `server` 仓库核心目录

```text
server/
├── src/
│   ├── servers/           # HTTP / gRPC / 主入口
│   │   ├── main.cc
│   │   ├── http_server.cc
│   │   ├── grpc_server.cc
│   │   └── tritonserver.cc
│   ├── core/              # 核心逻辑（若使用 core 子模块）
│   └── test/              # 单元测试与集成测试
├── qa/                    # 大量 L0/L1/L2 集成测试
├── build/                 # CMake 构建脚本
└── docker/                # NGC 镜像构建文件
```

## 关键入口与调用链

### 启动流程

```text
main()
  └─ TritonServer::Create()
       └─ TritonServer::Start()
            ├─ ModelRepositoryManager::Create()
            │    └─ 扫描 model repository，加载 config.pbtxt
            ├─ 初始化 HTTP / gRPC server
            └─ 启动 backend 加载
```

核心文件：

- `src/servers/main.cc`：命令行解析与 `TritonServer` 创建。
- `src/servers/tritonserver.cc`：`TritonServer` 类的实现。
- `src/core/model_repository_manager.cc`：模型发现、加载、热更新。

### 请求处理流程

```text
HTTP Server / gRPC Server
  └─ Parse request → InferenceRequest
       └─ ModelRepositoryManager::GetModel()
            └─ model->ScheduleRunnable()
                 └─ Scheduler::Enqueue()
                      └─ DynamicBatchScheduler::BatcherThread()
                           └─ Backend::Run()
                                └─ TRITONBACKEND_ModelExecute()
```

核心文件：

- `src/core/dynamic_batch_scheduler.cc`：Dynamic Batcher 实现。
- `src/core/sequence_batch_scheduler.cc`：Sequence Batcher 实现。
- `src/core/ensemble_scheduler.cc`：Ensemble 执行引擎。
- `src/core/backend.cc`：Backend 加载与执行封装。

### Backend 加载流程

```text
ModelRepositoryManager::LoadModel()
  └─ TritonBackend::Create()
       └─ dlopen(backend so)
            └─ TRITONBACKEND_Initialize()
                 └─ TRITONBACKEND_ModelInitialize()
                      └─ TRITONBACKEND_ModelInstanceInitialize()
```

Backend 以共享库形式被动态加载，通过 C API 与 core 通信。

## Dynamic Batcher 源码要点

`src/core/dynamic_batch_scheduler.cc` 的核心逻辑大致如下：

1. 每个启用 dynamic batching 的模型有一个 `DynamicBatchScheduler` 实例。
2. `Enqueue()` 把请求加入 pending queue，并触发 batcher thread。
3. Batcher thread 循环检查：
   - 是否有足够请求达到 preferred batch size；
   - 最早请求是否已等待超过 `max_queue_delay_microseconds`；
   - 是否收到关闭信号。
4. 满足条件后，从 queue 中取出一批请求，调用 backend 执行。

关键设计：

- 队列与调度线程是**每个模型独立**的，避免不同模型互相阻塞。
- 调度器通过 `std::promise` / `std::future` 或回调机制把结果返回到 HTTP/gRPC server。

## Ensemble Scheduler 源码要点

`src/core/ensemble_scheduler.cc` 维护一个张量池（tensor pool）和步骤依赖图：

1. 初始张量池填充 ensemble 的输入。
2. 对每个 step：
   - 检查 input_map 中的张量是否都已就绪。
   - 构建子模型的 `InferenceRequest`。
   - 调用子模型的 scheduler/backend。
   - 将 output_map 指定的输出写回张量池。
3. 当所有 output tensor 就绪后，构造响应。

Ensemble 本身没有 GPU kernel，所有耗时都在子模型调用上。

## Backend API 源码要点

`backend` 仓库定义了 backend 必须实现的 C API：

```c
// backend/include/triton/backend/backend_common.h
TRITONSERVER_Error* TRITONBACKEND_Initialize(TRITONBACKEND_Backend* backend);
TRITONSERVER_Error* TRITONBACKEND_ModelInitialize(TRITONBACKEND_Model* model);
TRITONSERVER_Error* TRITONBACKEND_ModelInstanceInitialize(
    TRITONBACKEND_ModelInstance* instance);
TRITONSERVER_Error* TRITONBACKEND_ModelExecute(
    TRITONBACKEND_ModelInstance* instance,
    TRITONBACKEND_Request** requests,
    const uint32_t request_count);
```

通过这些接口，Triton core 把 input buffers、output buffers、配置参数传给 backend，backend 完成推理后返回。

## Python Backend 的特殊性

Python backend 不是直接执行 Python 函数，而是：

1. 启动一个独立的 Python 子进程（或每个实例一个）。
2. 通过 IPC（shared memory + socket）把请求传给 Python 进程。
3. Python 进程调用用户编写的 `model.py` 中的 `execute()`。
4. 结果通过 IPC 传回 core。

这种设计的好处是：

- Python GIL 不会影响 C++ core 的并发。
- 一个 Python backend 崩溃不会拖垮整个 server。
- 可以方便地加载不同的 Python 环境与依赖。

## 如何阅读源码

建议按以下顺序阅读：

1. 先读 `backend/include/triton/backend/backend_common.h`，理解 backend 接口。
2. 再读 `src/core/model_repository_manager.cc`，理解模型加载生命周期。
3. 读 `src/core/dynamic_batch_scheduler.cc`，理解动态 batching。
4. 读 `src/core/ensemble_scheduler.cc`，理解 ensemble 执行。
5. 挑一个具体 backend（如 `vllm_backend` 或 `tensorrtllm_backend`）看 `model.py` 与 C API 封装。

## 本章小结

Triton 的源码虽然分散在多个仓库，但其主线清晰：**server 负责网络与生命周期，core 负责调度与内存，backend 负责具体推理**。阅读源码时抓住 `main.cc → model_repository_manager → scheduler → backend → TRITONBACKEND_ModelExecute` 这条调用链，就能快速定位关键逻辑。

**参考来源**

- [triton-inference-server/server GitHub](https://github.com/triton-inference-server/server)
- [triton-inference-server/core GitHub](https://github.com/triton-inference-server/core)
- [triton-inference-server/backend GitHub](https://github.com/triton-inference-server/backend)
- [Triton Python Backend](https://github.com/triton-inference-server/python_backend)
- [Triton vLLM Backend](https://github.com/triton-inference-server/vllm_backend)
- [Triton TensorRT-LLM Backend](https://github.com/triton-inference-server/tensorrtllm_backend)
