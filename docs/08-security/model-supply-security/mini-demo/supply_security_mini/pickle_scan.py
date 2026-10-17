"""S1：pickle 字节流 opcode 风险扫描 vs safetensors 安全加载对照。

核心思想：pickle 是"指令流"，GLOBAL/STACK_GLOBAL 引用模块属性、REDUCE 调用可调用对象，
因此反序列化未知 pickle 等价于执行远程代码。扫描器不执行任何指令，只用
pickletools.genops 逐条读出 opcode，根据"引用了什么、reduce 了什么"打分。
safetensors 则是"纯数据"：8 字节小端头长 + JSON 头（张量元数据）+ 原始字节缓冲区，
不含任何指令，因此可以安全地只做边界校验。
"""

from __future__ import annotations

import hashlib
import io
import json
import pickletools
import struct
from dataclasses import dataclass, field
from typing import Any

# --- 风险打分表 -------------------------------------------------------------

#: 允许出现的"良性" import 前缀（白名单）：只引用了这些数据/数值库，
#: 且不 reduce 危险目标时最多算 suspicious。
BENIGN_IMPORT_PREFIXES = (
    "numpy",
    "numpy.core.multiarray",
    "numpy._core.multiarray",
    "collections",
    "torch",
)

#: 高危模块：能直接执行命令 / 访问网络 / 读写文件系统
DANGEROUS_MODULES = {
    "os",
    "nt",
    "posix",
    "subprocess",
    "sys",
    "socket",
    "builtins",
    "codecs",
    "marshal",
    "ctypes",
    "importlib",
    "pathlib",
    "shutil",
    "pty",
    "requests",
    "urllib",
}

#: 高危属性：出现在任意模块名下的这些属性名一律视为恶意
DANGEROUS_ATTRS = {
    "system",
    "popen",
    "exec",
    "eval",
    "compile",
    "__import__",
    "getattr",
    "subprocess",
    "call",
    "check_output",
    "run",
    "remove",
    "rmtree",
    "unlink",
    "read",
    "write",
    "open",
}

#: 每个 finding 的基础分
SCORE_MALICIOUS = 50
SCORE_SUSPICIOUS = 10
SCORE_REDUCE = 5

RATING_SAFE = "safe"
RATING_SUSPICIOUS = "suspicious"
RATING_MALICIOUS = "malicious"


@dataclass
class Finding:
    """一条扫描发现：哪个 opcode、引用了什么、判定为何。"""

    opcode: str
    name: str
    rating: str
    detail: str


@dataclass
class ScanReport:
    """pickle 扫描结果。"""

    findings: list[Finding] = field(default_factory=list)
    score: int = 0
    n_opcodes: int = 0
    imports: list[str] = field(default_factory=list)

    @property
    def rating(self) -> str:
        if any(f.rating == RATING_MALICIOUS for f in self.findings):
            return RATING_MALICIOUS
        if self.score > 0:
            return RATING_SUSPICIOUS
        return RATING_SAFE

    @property
    def dangerous_imports(self) -> list[str]:
        return [f.name for f in self.findings if f.rating == RATING_MALICIOUS]


def _resolve_import(module: str, attr: str) -> str:
    """STACK_GLOBAL/GLOBAL 总是以 module + attr 成对出现。"""
    return f"{module}.{attr}" if module else attr


def _classify(module: str, attr: str) -> tuple[str, str]:
    """返回 (rating, detail)。"""
    full = _resolve_import(module, attr)
    if attr in DANGEROUS_ATTRS or module.split(".")[0] in DANGEROUS_MODULES:
        return RATING_MALICIOUS, "引用危险模块/属性"
    if any(full.startswith(p) or module.startswith(p) for p in BENIGN_IMPORT_PREFIXES):
        return RATING_SAFE, "良性数据/数值库引用"
    return RATING_SUSPICIOUS, "未知模块引用"


def scan_pickle(data: bytes) -> ScanReport:
    """静态扫描 pickle 字节流，绝不执行其中的指令。

    解析逻辑（模拟生产扫描器 picklescan/ModelScan 的最小内核）：
    1. 用 pickletools.genops 读出全部 (opcode, arg, pos)；
    2. GLOBAL / STACK_GLOBAL 之后跟随的模块名、属性名记入 imports；
    3. REDUCE 意味着"以栈顶可调用对象执行调用"——这是 RCE 的落脚点；
    4. 按打分表累加，输出 rating ∈ {safe, suspicious, malicious}。
    """
    report = ScanReport()
    try:
        ops = list(pickletools.genops(io.BytesIO(data)))
    except Exception as exc:  # 不是合法 pickle / 被截断
        report.findings.append(
            Finding("PARSE_ERROR", "", RATING_MALICIOUS, f"无法解析 pickle 流: {exc}")
        )
        report.score += SCORE_MALICIOUS
        return report

    pending_module = ""
    last_attr = ""
    for opcode, arg, _pos in ops:
        report.n_opcodes += 1
        name = opcode.name
        if name == "GLOBAL":
            # 形如 "os system\n"
            module, _, attr = str(arg).partition(" ")
            report.imports.append(_resolve_import(module, attr))
            rating, detail = _classify(module, attr)
            if rating != RATING_SAFE:
                report.findings.append(
                    Finding(name, _resolve_import(module, attr), rating, detail)
                )
                report.score += (
                    SCORE_MALICIOUS if rating == RATING_MALICIOUS else SCORE_SUSPICIOUS
                )
        elif name == "SHORT_BINUNICODE" and isinstance(arg, str):
            # STACK_GLOBAL 消费栈上最后两个字符串：module、attr
            pending_module, last_attr = last_attr, arg
        elif name == "STACK_GLOBAL":
            report.imports.append(_resolve_import(pending_module, last_attr))
            rating, detail = _classify(pending_module, last_attr)
            if rating != RATING_SAFE:
                report.findings.append(
                    Finding(
                        name,
                        _resolve_import(pending_module, last_attr),
                        rating,
                        detail,
                    )
                )
                report.score += (
                    SCORE_MALICIOUS if rating == RATING_MALICIOUS else SCORE_SUSPICIOUS
                )
            pending_module, last_attr = "", ""
        elif name == "REDUCE":
            # 有 REDUCE 说明 pickle 不只是纯数据；是否恶意取决于引用是否危险
            report.findings.append(
                Finding(name, "", RATING_SUSPICIOUS, "包含 REDUCE 调用（非纯数据 pickle）")
            )
            report.score += SCORE_REDUCE

    return report


# --- safetensors 对照 -------------------------------------------------------


@dataclass
class SafeTensorsReport:
    """safetensors 结构校验结果。"""

    is_safetensors: bool
    n_tensors: int = 0
    total_bytes: int = 0
    tensor_names: list[str] = field(default_factory=list)
    sha256: str = ""


def parse_safetensors(data: bytes) -> SafeTensorsReport:
    """只解析结构、不执行任何东西，天然免疫反序列化 RCE。

    布局: [8 字节小端 header_len][header_len 字节 JSON][连续张量原始字节]
    校验项：头长边界、JSON 可解析、每个张量的 begin/end 落在缓冲区内。
    """
    if len(data) < 8:
        return SafeTensorsReport(is_safetensors=False)
    (header_len,) = struct.unpack("<Q", data[:8])
    if header_len <= 0 or 8 + header_len > len(data):
        return SafeTensorsReport(is_safetensors=False)
    try:
        header = json.loads(data[8 : 8 + header_len].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return SafeTensorsReport(is_safetensors=False)
    if not isinstance(header, dict) or "__metadata__" not in header and not all(
        isinstance(v, dict) and "data_offsets" in v for v in header.values()
    ):
        return SafeTensorsReport(is_safetensors=False)

    base = 8 + header_len
    total = len(data) - base
    names: list[str] = []
    for name, meta in header.items():
        if name == "__metadata__":
            continue
        begin, end = meta["data_offsets"]
        if begin < 0 or end < begin or end > total:
            return SafeTensorsReport(is_safetensors=False)
        names.append(name)
    return SafeTensorsReport(
        is_safetensors=True,
        n_tensors=len(names),
        total_bytes=total,
        tensor_names=names,
        sha256=hashlib.sha256(data).hexdigest(),
    )


def build_safetensors(tensors: dict[str, dict[str, Any]]) -> bytes:
    """构造一个最小合法 safetensors 文件（仅 int32/float32 dtype）。"""
    header: dict[str, Any] = {}
    blobs: list[bytes] = []
    offset = 0
    dtype_map = {"float32": ("F32", 4), "int32": ("I32", 4), "float64": ("F64", 8)}
    for name, spec in tensors.items():
        arr = spec["data"]
        dtype, _size = dtype_map[spec["dtype"]]
        raw = arr.tobytes() if hasattr(arr, "tobytes") else bytes(arr)
        end = offset + len(raw)
        header[name] = {
            "dtype": dtype,
            "shape": list(spec["shape"]),
            "data_offsets": [offset, end],
        }
        blobs.append(raw)
        offset = end
    header_bytes = json.dumps(header).encode("utf-8")
    return struct.pack("<Q", len(header_bytes)) + header_bytes + b"".join(blobs)


# --- 样本负载（供 demo/tests 使用） -------------------------------------------


def make_benign_pickle(rng: Any) -> bytes:
    """纯数据 pickle：一个 numpy 数组，REDUCE 只落在 numpy._core 的重建函数上。"""
    import numpy as np

    arr = np.arange(12, dtype=np.float64).reshape(3, 4)
    return pickle_dumps(arr)


class DemoWeights:
    """供 demo/tests 使用的良性自定义对象（模块级定义，可 pickle）。"""

    def __init__(self, w: list[float]) -> None:
        self.w = w


def make_suspicious_pickle() -> bytes:
    """引用未知模块的 pickle（自定义类对象）。"""
    import pickle

    return pickle.dumps(DemoWeights([0.1, 0.2]), protocol=4)


def make_malicious_pickle(cmd: str = "id") -> bytes:
    """教科书式 RCE pickle：os.system(cmd)，与 fickling 文档示例同型。

    使用 __reduce__ 会产出 GLOBAL('os system') + REDUCE 的指令序列。
    """
    import pickle

    class Exploit:  # noqa: D106
        def __reduce__(self) -> Any:
            import os

            return (os.system, (cmd,))

    return pickle.dumps(Exploit(), protocol=4)


def pickle_dumps(obj: Any) -> bytes:
    import pickle

    return pickle.dumps(obj, protocol=4)
