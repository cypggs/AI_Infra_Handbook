"""端到端 demo 测试：五个场景全部出现且输出确定。"""

import io
from contextlib import redirect_stdout

from supply_security_mini.demo import run_demo


def _capture() -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        run_demo()
    return buf.getvalue()


class TestDemoOutput:
    def test_all_scenarios_present(self):
        out = _capture()
        for tag in ("[S1]", "[S2]", "[S3]", "[S4]", "[S5]"):
            assert tag in out

    def test_malicious_pickle_flagged(self):
        assert "RCE pickle (os.system)" in _capture()
        assert "rating=malicious" in _capture()

    def test_poison_alarm_fires(self):
        out = _capture()
        assert "alarm=True" in out
        assert "alarm=False" in out

    def test_deterministic(self):
        assert _capture() == _capture()

    def test_watermark_detection_summary(self):
        out = _capture()
        assert "detected=True" in out
        assert "detected=False" in out
