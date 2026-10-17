"""代码库索引管道：chunk -> embed -> Merkle 增量更新 -> 向量检索。

模拟 Cursor 官方文档与公开访谈中可确证的机制（不含任何未公开数字）：
- 文件在本地被切分为语义块（教学实现：空行边界 + 最大行数，近似 AST 感知切块）
- Merkle 树对全部文件做指纹，任何文件变化都会改变根哈希（官方文档口径）
- 只有哈希不匹配的文件被重新切块/嵌入（增量同步，官方文档口径约 10 分钟周期）
- 嵌入向量与混淆后的相对路径 + 行号区间一起存入远程索引（官方安全文档口径：
  不存明文代码，查询只回传路径/行号，文件内容本地读取）
- 教学嵌入：哈希词袋 -> 定长向量 + L2 归一化（真实系统使用神经嵌入模型）

本模块的输出完全确定：不依赖随机数。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np

EMBED_DIM = 64
MAX_CHUNK_LINES = 40  # 教学切块上限


def _stable_hash(text: str) -> int:
    """对字符串做稳定哈希（跨进程确定性）。"""
    return int.from_bytes(hashlib.blake2b(text.encode("utf-8"), digest_size=8).digest(), "big")


def chunk_code(text: str, max_lines: int = MAX_CHUNK_LINES) -> list[tuple[int, int, str]]:
    """把源文件切成 (start_line, end_line, content) 三元组。

    切块规则（教学近似）：先按空行把源文件分成逻辑块（近似 AST 感知的
    函数/类边界），超过 max_lines 行的块再硬切。行号从 0 开始。
    """
    lines = text.split("\n")
    blocks: list[tuple[int, list[str]]] = []
    cur_start: int | None = None
    cur: list[str] = []
    for i, ln in enumerate(lines):
        if ln.strip() == "":
            if cur:
                blocks.append((cur_start if cur_start is not None else i, cur))
                cur = []
                cur_start = None
        else:
            if cur_start is None:
                cur_start = i
            cur.append(ln)
    if cur:
        blocks.append((cur_start if cur_start is not None else 0, cur))

    chunks: list[tuple[int, int, str]] = []
    for start, blk in blocks:
        for off in range(0, len(blk), max_lines):
            part = blk[off : off + max_lines]
            chunks.append((start + off, start + off + len(part) - 1, "\n".join(part)))
    return chunks


def embed_text(text: str, dim: int = EMBED_DIM) -> np.ndarray:
    """教学嵌入：哈希词袋 + 符号化，L2 归一化。

    每个词通过稳定哈希映射到 (维度, 符号)，累加后归一化。
    相似文本的余弦相似度较高，完全无关文本接近 0——足够演示检索语义。
    """
    vec = np.zeros(dim, dtype=np.float64)
    for token in _tokens(text):
        h = _stable_hash(token)
        idx = h % dim
        sign = 1.0 if (h >> 63) & 1 else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


def _tokens(text: str) -> list[str]:
    out: list[str] = []
    cur = []
    for ch in text.lower():
        if ch.isalnum() or ch == "_":
            cur.append(ch)
        elif cur:
            out.append("".join(cur))
            cur = []
    if cur:
        out.append("".join(cur))
    return out


def merkle_root(file_hashes: dict[str, str]) -> str:
    """对 {path: content_hash} 构造确定性 Merkle 根。

    叶子 = "path|hash"；逐层 hash(left + right)，奇数个节点时复制末节点。
    空索引的根为空串的哈希。
    """
    leaves = sorted(f"{p}|{h}" for p, h in file_hashes.items())
    if not leaves:
        return hashlib.sha256(b"").hexdigest()
    level = [hashlib.sha256(x.encode("utf-8")).hexdigest() for x in leaves]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(hashlib.sha256((left + right).encode("utf-8")).hexdigest())
        level = nxt
    return level[0]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def obfuscate_path(path: str, key: str) -> str:
    """教学路径混淆：用 key 派生的一次一密对每段做异或后 hex（官方口径为
    客户端密钥加密路径段，使远程索引不暴露明文路径结构）。"""
    out = []
    for seg in path.split("/"):
        k = hashlib.blake2b(key.encode("utf-8") + seg.encode("utf-8"), digest_size=4).digest()
        data = seg.encode("utf-8")
        mask = (k * (len(data) // len(k) + 1))[: len(data)]
        out.append(bytes(a ^ b for a, b in zip(data, mask)).hex())
    return "/".join(out)


@dataclass
class ChunkRecord:
    obfuscated_path: str
    start_line: int
    end_line: int
    embedding: np.ndarray
    chunk_hash: str


@dataclass
class CodebaseIndex:
    """内存版代码库索引：Merkle 增量同步 + 向量检索。"""

    obfuscation_key: str = "demo-key"
    records: list[ChunkRecord] = field(default_factory=list)
    _file_hashes: dict[str, str] = field(default_factory=dict)

    @property
    def root_hash(self) -> str:
        return merkle_root(self._file_hashes)

    def sync(self, files: dict[str, str]) -> dict[str, int]:
        """与给定文件集做增量同步。

        返回 {"added": a, "updated": u, "removed": r, "unchanged": n,
        "chunks_reembedded": c}——只有内容哈希变化/新增的文件会被重新切块嵌入。
        """
        added = updated = removed = unchanged = 0
        old_paths = set(self._file_hashes)
        for path, text in files.items():
            h = content_hash(text)
            if path not in self._file_hashes:
                added += 1
            elif self._file_hashes[path] == h:
                unchanged += 1
                continue
            else:
                updated += 1
            self._file_hashes[path] = h
            self._drop_path(path)
            self._embed_file(path, text)
        for path in old_paths - set(files):
            removed += 1
            self._drop_path(path)
            del self._file_hashes[path]
        return {
            "added": added,
            "updated": updated,
            "removed": removed,
            "unchanged": unchanged,
            "chunks_reembedded": added + updated,
        }

    def _drop_path(self, path: str) -> None:
        obf = obfuscate_path(path, self.obfuscation_key)
        self.records = [r for r in self.records if r.obfuscated_path != obf]

    def _embed_file(self, path: str, text: str) -> None:
        obf = obfuscate_path(path, self.obfuscation_key)
        for start, end, content in chunk_code(text):
            self.records.append(
                ChunkRecord(
                    obfuscated_path=obf,
                    start_line=start,
                    end_line=end,
                    embedding=embed_text(content),
                    chunk_hash=content_hash(content),
                )
            )

    def search(self, query: str, k: int = 3) -> list[ChunkRecord]:
        """按余弦相似度返回 top-k 块（真实系统回传路径+行号，本地再读文件）。"""
        if not self.records:
            return []
        q = embed_text(query)
        mat = np.stack([r.embedding for r in self.records])
        sims = mat @ q
        order = np.argsort(-sims, kind="stable")[:k]
        return [self.records[int(i)] for i in order]

    def stats(self) -> dict[str, int]:
        return {"files": len(self._file_hashes), "chunks": len(self.records)}
