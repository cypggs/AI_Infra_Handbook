"""S2：模型工件签名-验证链（merkle 清单 + HMAC 签名 + 篡改定位）。

对应生产中的 Sigstore/cosign 思路的玩具版：
- manifest：列出每个工件的 sha256 + 聚合 merkle root（任何单文件改动都会改变 root）；
- sign/verify：用 HMAC-SHA256 代替真实世界的密钥签名（保证确定性、无外部依赖）；
- verify_bundle 逐文件校验，能精确定位"哪个文件被改了"——这是供应链事件响应的第一步。
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _merkle_root(leaves: list[str]) -> str:
    """对十六进制摘要列表求 merkle root；空清单为全零串。"""
    if not leaves:
        return hashlib.sha256(b"").hexdigest()
    level = [bytes.fromhex(d) for d in leaves]
    while len(level) > 1:
        if len(level) % 2 == 1:  # 奇数节点复制最后一个
            level.append(level[-1])
        level = [
            hashlib.sha256(level[i] + level[i + 1]).digest()
            for i in range(0, len(level), 2)
        ]
    return level[0].hex()


@dataclass
class ManifestEntry:
    path: str
    sha256: str
    size: int


@dataclass
class Manifest:
    """工件清单：path -> 摘要，外加 merkle root 作为整体指纹。"""

    entries: dict[str, ManifestEntry] = field(default_factory=dict)
    merkle_root: str = ""

    def to_dict(self) -> dict:
        return {
            "files": [
                {"path": e.path, "sha256": e.sha256, "size": e.size}
                for e in self.entries.values()
            ],
            "merkle_root": self.merkle_root,
        }


def build_manifest(files: dict[str, bytes]) -> Manifest:
    """files: 相对路径 -> 字节内容。返回带 merkle root 的清单。"""
    entries = {
        path: ManifestEntry(path=path, sha256=sha256_hex(blob), size=len(blob))
        for path, blob in sorted(files.items())
    }
    root = _merkle_root([e.sha256 for e in entries.values()])
    return Manifest(entries=entries, merkle_root=root)


def sign_manifest(manifest: Manifest, key: bytes) -> str:
    """对 merkle root 做 HMAC-SHA256 签名（玩具版：确定性、无随机数）。"""
    return hmac.new(key, manifest.merkle_root.encode("ascii"), hashlib.sha256).hexdigest()


@dataclass
class VerifyResult:
    ok: bool
    bad_files: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    extra_files: list[str] = field(default_factory=list)
    signature_ok: bool = False


def verify_bundle(
    files: dict[str, bytes], manifest: Manifest, signature: str, key: bytes
) -> VerifyResult:
    """完整验证链：签名 -> merkle root -> 逐文件 digest。

    返回结构化的 VerifyResult，bad_files 精确列出被篡改的工件路径。
    """
    result = VerifyResult(ok=False)
    expect_sig = sign_manifest(manifest, key)
    result.signature_ok = hmac.compare_digest(expect_sig, signature)
    if not result.signature_ok:
        return result  # 签名不成立时不再信任清单本身

    actual = build_manifest(files)
    if actual.merkle_root != manifest.merkle_root:
        for path, entry in manifest.entries.items():
            if path not in files:
                result.missing_files.append(path)
            elif sha256_hex(files[path]) != entry.sha256:
                result.bad_files.append(path)
        for path in files:
            if path not in manifest.entries:
                result.extra_files.append(path)
        return result

    result.ok = True
    return result


def tamper(files: dict[str, bytes], path: str, mutation: bytes) -> dict[str, bytes]:
    """复制 files 并把 path 指向的内容替换为 mutation（演示篡改）。"""
    out = dict(files)
    out[path] = mutation
    return out
