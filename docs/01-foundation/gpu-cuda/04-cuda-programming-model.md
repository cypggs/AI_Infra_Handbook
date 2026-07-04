# 4. CUDA 编程模型：Grid、Block、Thread 与内存

CUDA（Compute Unified Device Architecture）是 NVIDIA 的并行计算平台和编程模型。它让开发者可以用 C/C++ 风格的代码编写在 GPU 上运行的程序。

作为 AI Infra 工程师，你未必天天写 CUDA，但你一定会遇到这些问题：

- 为什么 PyTorch 的某个 op 在 GPU 上特别慢？
- 为什么同样的 kernel，block size 从 128 改成 256 速度翻倍？
- 为什么模型推理时显存占用和理论值差很多？

理解 CUDA 编程模型，是回答这些问题的基础。

## 4.1 主机（Host）与设备（Device）

CUDA 程序运行在两个“世界”里：

- **Host**：CPU + 内存，负责串行控制、数据准备、kernel 启动；
- **Device**：GPU + 显存，负责并行计算。

```c
cudaMalloc(&d_A, size);      // 在 GPU 上分配内存
cudaMemcpy(d_A, h_A, size, cudaMemcpyHostToDevice); // CPU -> GPU
myKernel<<<grid, block>>>(d_A); // 启动 GPU kernel
cudaMemcpy(h_A, d_A, size, cudaMemcpyDeviceToHost); // GPU -> CPU
```

CPU 和 GPU 之间的数据传输通过 PCIe 或 NVLink，速度差异巨大。AI 训练中的大量工程优化，本质上都是在**减少 Host-Device 数据传输**。

## 4.2 Grid / Block / Thread 层级

CUDA kernel 启动时，需要指定两个参数：

```c
myKernel<<<gridDim, blockDim>>>(args);
```

- **gridDim**：Grid 中有多少个 Block；
- **blockDim**：每个 Block 中有多少个 Thread。

每个线程通过内置变量知道自己的位置：

| 变量 | 含义 |
|---|---|
| `blockIdx.x` | Block 在 Grid 中的索引 |
| `threadIdx.x` | Thread 在 Block 中的索引 |
| `blockDim.x` | 每个 Block 的线程数 |
| `gridDim.x` | Block 总数 |

全局线程 ID 可以计算为：

```c
int idx = blockIdx.x * blockDim.x + threadIdx.x;
```

### 三维索引

CUDA 也支持二维和三维的 Block/Grid，方便处理图像、体素等数据：

```c
dim3 grid(16, 16);   // 16x16 个 Block
dim3 block(16, 16);  // 每个 Block 16x16 线程
myKernel<<<grid, block>>>(args);
```

在 kernel 内部可以用 `blockIdx.x/y/z` 和 `threadIdx.x/y/z`。

## 4.3 Warp：硬件真正的执行单位

虽然 CUDA 代码以 Thread 为单位写，但硬件以 **Warp（32 线程）** 为单位执行。

一个 Block 里的线程会按顺序分成多个 warp：

```
Block 有 256 个线程 → 256 / 32 = 8 个 warp
```

同一个 warp 里的 32 个线程执行 SIMT：同一时钟周期执行同一条指令。如果线程走不同分支，就会触发 **warp divergence**，导致分支串行执行。

```c
if (threadIdx.x % 2 == 0) {
    // 偶数线程执行
} else {
    // 奇数线程执行
}
// warp 会先执行偶数分支，掩码掉奇数线程；再执行奇数分支，掩码掉偶数线程
```

## 4.4 CUDA 内存类型

CUDA 中有多种内存，每种有不同的作用域和速度：

| 内存类型 | 声明方式 | 作用域 | 生命周期 | 速度 |
|---|---|---|---|---|
| Register | 局部变量 | Thread | Kernel | 最快 |
| Local Memory | 寄存器溢出或动态数组 | Thread | Kernel | 慢（在 global memory） |
| Shared Memory | `__shared__` | Block | Kernel | 很快 |
| Global Memory | 指针/`__device__` | Grid | 程序 | 慢 |
| Constant Memory | `__constant__` | Grid | 程序 | 有缓存，只读 |
| Texture Memory | 纹理对象 | Grid | 程序 | 有缓存，特定访问模式 |

### Shared Memory 的关键作用

Shared memory 是一块片上高速存储，同一个 Block 内的线程可以共享数据。典型用法是 **Tiling**：

```c
__shared__ float tile[BLOCK_SIZE][BLOCK_SIZE];
// 把 global memory 的一小块数据读到 shared memory
// Block 内线程一起计算
// 结果写回 global memory
```

### Bank Conflict

Shared memory 被分成 32 个 bank（对应一个 warp 的 32 个线程）。理想情况下，warp 里的 32 个线程同时访问 32 个不同 bank，一次完成。

如果多个线程访问同一个 bank，就会 **bank conflict**，访问被串行化，性能下降。

```c
// 容易引发 bank conflict 的写法
__shared__ float s[32][32];
float x = s[threadIdx.x][0]; // 同一列，可能落在同一 bank
```

解决方式通常是用 padding：

```c
__shared__ float s[32][33]; // 加一列，让 bank 分布均匀
```

## 4.5 内存合并访问（Coalesced Memory Access）

Global memory 的访问以 **transaction** 为单位（通常是 32/64/128 bytes）。如果一个 warp 的 32 个线程访问的地址是连续的，GPU 可以把多次访问合并成一次 transaction，极大减少总线压力。

### 好模式 vs 坏模式

```c
// 好：合并访问，线程 i 访问地址 base + i
int idx = blockIdx.x * blockDim.x + threadIdx.x;
float x = A[idx];

// 坏：跨步访问，线程 i 访问地址 base + i * stride
int idx = blockIdx.x * blockDim.x + threadIdx.x;
float x = A[idx * N]; // stride 很大，分散在不同 cache line
```

矩阵乘法中，**行优先读取 A 是合并访问，列优先读取 B 是非合并访问**。Tiling 的核心目的之一就是把非合并访问转化为 shared memory 上的快速访问。

## 4.6 Occupancy：SM 的“入住率”

Occupancy = 当前驻留 warp 数 / SM 支持的最大 warp 数。

例如 H100 每个 SM 最多 32 个 warp（1024 线程）。如果一个 Block 用了 1024 个线程、64 KB shared memory、大量寄存器，那可能一个 SM 同时只能放 1 个 Block，occupancy 就不高。

### 影响 occupancy 的因素

- **Block 大小**：太大可能限制并发 Block 数；
- **每个线程的寄存器数**：寄存器文件总量有限；
- **Shared memory 用量**：shared memory 总量有限；
- **Warp 调度能力**：SM 有最大 warp 数限制。

但注意：**高 occupancy 不等于高性能**。有时候降低 occupancy，但让每个 warp 做更多有用计算，反而更快。Occupancy 只是工具，不是目标。

## 4.7 同步

CUDA 中有两种常见同步：

- **`__syncthreads()`**：Block 内所有线程同步，常用于 shared memory tiling 后确保数据已读完；
- **`cudaDeviceSynchronize()`**：Host 等待 Device 所有 kernel 完成，常用于计时或错误检查。

## 4.8 一个完整的 Vector Add Kernel

```c
__global__ void vectorAdd(const float *A, const float *B, float *C, int N) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < N) {
        C[i] = A[i] + B[i];
    }
}

// 启动
int blockSize = 256;
int numBlocks = (N + blockSize - 1) / blockSize;
vectorAdd<<<numBlocks, blockSize>>>(d_A, d_B, d_C, N);
```

这是 CUDA 的“Hello World”。每个线程处理一个元素，线程 ID 由 blockIdx 和 threadIdx 计算得到。

## 4.9 一个矩阵乘 kernel 的雏形

```c
__global__ void matmul(const float *A, const float *B, float *C, int N) {
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;

    float sum = 0.0f;
    for (int k = 0; k < N; k++) {
        sum += A[row * N + k] * B[k * N + col];
    }
    C[row * N + col] = sum;
}
```

这个 kernel 有两个明显问题：

1. **B 的访问是列优先，非合并访问**；
2. **每个元素从 global memory 读取 N 次 A 和 N 次 B，没有复用**。

优化版本会引入 shared memory tiling，把 A 和 B 的小块读到 shared memory，复用多次计算。Mini Demo 会详细演示这一过程。

## 4.10 本节小结

CUDA 编程模型的核心可以概括为：

1. **Host 控制，Device 并行执行**；
2. **Grid → Block → Thread 的层级结构**；
3. **硬件以 Warp（32 线程）为单位执行**，避免 warp divergence；
4. **内存分层**，Register/Shared/Global 速度和作用域不同；
5. **合并访问**和**避免 bank conflict** 是内存优化的关键；
6. **Occupancy** 是 hiding 延迟的手段，不是唯一目标。

下一节，我们看 NVIDIA 的软件栈：CUDA Runtime、cuBLAS、NCCL、DCGM 等。
