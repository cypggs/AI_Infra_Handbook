# supply-security-mini：AI 供应链与模型安全最小闭环

纯 Python（仅依赖 numpy）实现《AI 供应链与模型安全》主题的五个核心机制，CPU 可运行、全程确定性种子、测试无需网络。

## 五个模块（对应第 5 章的五条防线）

| 模块 | 机制 | 对应生产工具/概念 |
|---|---|---|
| `pickle_scan.py` | pickle 字节流 opcode 风险评分 vs safetensors 结构校验 | picklescan、ModelScan、Fickling、HF pickle scanning |
| `signing.py` | merkle 工件清单 + HMAC 签名 + 篡改定位 | Sigstore/cosign、SLSA provenance |
| `mcp_integrity.py` | MCP 工具清单完整性：hash 不符拒绝加载、描述 diff 告警 | Invariant Labs tool poisoning 防线、版本锁定 |
| `poisoning.py` | canary 样本触发率检测训练数据后门 | BadGPT / Sleeper Agents 检测思路 |
| `watermark.py` | 确定性伪随机权重水印：嵌入/抽取/鲁棒性 | Kirchenbauer et al. 2023 权重水印思路 |

## 安装与运行

```bash
cd docs/08-security/model-supply-security/mini-demo
pip install -e ".[dev]"
pytest tests/ -v        # 57 个测试
python -m supply_security_mini.demo
```

## 目录结构

```text
mini-demo/
├── README.md
├── pyproject.toml
├── conftest.py
├── supply_security_mini/
│   ├── __init__.py
│   ├── pickle_scan.py      # S1 pickle 扫描器 + safetensors 解析
│   ├── signing.py          # S2 merkle 清单 + HMAC 签名验证链
│   ├── mcp_integrity.py    # S3 MCP 工具清单完整性校验
│   ├── poisoning.py        # S4 数据投毒 + canary 触发率
│   ├── watermark.py        # S5 权重水印嵌入/抽取
│   └── demo.py             # run_demo()：五个端到端场景
└── tests/
    ├── test_pickle_scan.py   # 13 个测试
    ├── test_signing.py       # 10 个测试
    ├── test_mcp_integrity.py # 9 个测试
    ├── test_poisoning.py     # 10 个测试
    ├── test_watermark.py     # 10 个测试
    └── test_demo.py          # 5 个测试
```

## 设计说明

- **绝不执行被扫描对象**：pickle 扫描只使用 `pickletools.genops` 读取指令；测试中有哨兵文件验证恶意负载不会被触发。
- **确定性**：所有随机源均为固定种子的 `numpy.random.default_rng`；demo 输出可逐字节复现。
- **玩具边界**：HMAC 代替真实非对称签名；线性模型代替真实 LLM；目的是演示机制与权衡，不是生产工具。
