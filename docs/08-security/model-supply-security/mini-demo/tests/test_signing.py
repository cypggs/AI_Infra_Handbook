"""S2 测试：merkle 清单 + HMAC 签名 + 篡改定位。"""

import numpy as np

from supply_security_mini.signing import (
    build_manifest,
    sign_manifest,
    tamper,
    verify_bundle,
)

KEY = b"test-signing-key"


def _files() -> dict[str, bytes]:
    return {
        "config.json": b'{"layers": 2}',
        "model.safetensors": np.arange(32, dtype=np.float32).tobytes(),
        "tokenizer.txt": b"hello world",
    }


class TestManifest:
    def test_all_files_listed(self):
        manifest = build_manifest(_files())
        assert sorted(manifest.entries) == [
            "config.json",
            "model.safetensors",
            "tokenizer.txt",
        ]

    def test_merkle_root_deterministic(self):
        assert build_manifest(_files()).merkle_root == build_manifest(_files()).merkle_root

    def test_merkle_root_changes_with_content(self):
        files = _files()
        root_a = build_manifest(files).merkle_root
        files["config.json"] = b'{"layers": 3}'
        assert build_manifest(files).merkle_root != root_a

    def test_odd_leaf_count_works(self):
        files = _files()
        files["extra1.bin"] = b"x"
        files["extra2.bin"] = b"y"
        manifest = build_manifest(files)
        assert len(files) == 5 and manifest.merkle_root  # 奇数叶子，复制末叶配对


class TestSignature:
    def test_sign_depends_on_key(self):
        manifest = build_manifest(_files())
        assert sign_manifest(manifest, KEY) != sign_manifest(manifest, b"other-key")


class TestVerify:
    def test_intact_bundle_ok(self):
        files = _files()
        manifest = build_manifest(files)
        result = verify_bundle(files, manifest, sign_manifest(manifest, KEY), KEY)
        assert result.ok and result.signature_ok and result.bad_files == []

    def test_tampered_file_located(self):
        files = _files()
        manifest = build_manifest(files)
        mutated = tamper(files, "model.safetensors", b"\xff" * 128)
        result = verify_bundle(mutated, manifest, sign_manifest(manifest, KEY), KEY)
        assert not result.ok
        assert result.bad_files == ["model.safetensors"]

    def test_missing_file_reported(self):
        files = _files()
        manifest = build_manifest(files)
        del files["tokenizer.txt"]
        result = verify_bundle(files, manifest, sign_manifest(manifest, KEY), KEY)
        assert not result.ok
        assert result.missing_files == ["tokenizer.txt"]

    def test_extra_file_reported(self):
        files = _files()
        manifest = build_manifest(files)
        files["attacker.safetensors"] = b"evil"
        result = verify_bundle(files, manifest, sign_manifest(manifest, KEY), KEY)
        assert not result.ok
        assert result.extra_files == ["attacker.safetensors"]

    def test_wrong_key_fails_signature(self):
        files = _files()
        manifest = build_manifest(files)
        result = verify_bundle(files, manifest, sign_manifest(manifest, KEY), b"wrong")
        assert not result.ok and not result.signature_ok
