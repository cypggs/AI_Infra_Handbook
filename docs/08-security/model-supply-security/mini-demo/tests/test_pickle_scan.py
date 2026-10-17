"""S1 测试：pickle opcode 扫描器与 safetensors 解析。"""

import numpy as np
import pytest

from supply_security_mini.pickle_scan import (
    RATING_MALICIOUS,
    RATING_SAFE,
    RATING_SUSPICIOUS,
    build_safetensors,
    make_malicious_pickle,
    make_suspicious_pickle,
    parse_safetensors,
    pickle_dumps,
    scan_pickle,
)


class TestPureDataPickle:
    def test_rating_safe(self):
        blob = pickle_dumps([0.1, 0.2, 0.3])
        assert scan_pickle(blob).rating == RATING_SAFE


class TestNumpyPickle:
    def test_suspicious_not_malicious(self):
        blob = pickle_dumps(np.arange(6, dtype=np.float64))
        report = scan_pickle(blob)
        assert report.rating == RATING_SUSPICIOUS

    def test_imports_contain_reconstruct(self):
        blob = pickle_dumps(np.zeros((2, 2), dtype=np.float32))
        report = scan_pickle(blob)
        assert any("reconstruct" in imp for imp in report.imports)


class TestSuspiciousPickle:
    def test_unknown_class_suspicious(self):
        report = scan_pickle(make_suspicious_pickle())
        assert report.rating == RATING_SUSPICIOUS


class TestMaliciousPickle:
    def test_rating_malicious(self):
        report = scan_pickle(make_malicious_pickle("id"))
        assert report.rating == RATING_MALICIOUS

    def test_dangerous_import_detected(self):
        report = scan_pickle(make_malicious_pickle("id"))
        joined = " ".join(report.dangerous_imports)
        assert "system" in joined

    def test_score_at_least_50(self):
        report = scan_pickle(make_malicious_pickle("cat /etc/passwd"))
        assert report.score >= 50

    def test_scanner_does_not_execute(self, tmp_path):
        """扫描恶意 pickle 不得触发其负载：在被攻击目录下放哨兵文件。"""
        sentinel = tmp_path / "pwned"
        blob = make_malicious_pickle(f"touch {sentinel}")
        scan_pickle(blob)  # 若被执行，sentinel 会被创建
        assert not sentinel.exists()


class TestParseErrors:
    def test_garbage_bytes_flagged(self):
        report = scan_pickle(b"\xff\xfe not a pickle at all")
        assert report.rating == RATING_MALICIOUS
        assert report.findings[0].opcode == "PARSE_ERROR"


class TestSafeTensors:
    @pytest.fixture()
    def blob(self):
        return build_safetensors(
            {
                "a": {"dtype": "float32", "shape": [2], "data": np.ones(2, dtype=np.float32)},
                "b": {
                    "dtype": "int32",
                    "shape": [1, 2],
                    "data": np.array([[1, 2]], dtype=np.int32),
                },
            }
        )

    def test_parse_ok(self, blob):
        report = parse_safetensors(blob)
        assert report.is_safetensors
        assert report.n_tensors == 2
        assert set(report.tensor_names) == {"a", "b"}

    def test_truncated_header_rejected(self, blob):
        assert not parse_safetensors(blob[:8]).is_safetensors

    def test_corrupt_length_rejected(self, blob):
        # 破坏头长字段，让 JSON 头越界
        assert not parse_safetensors(blob[:20]).is_safetensors

    def test_random_bytes_rejected(self):
        assert not parse_safetensors(b"\x00" * 64).is_safetensors
