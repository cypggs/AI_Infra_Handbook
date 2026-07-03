"""test_demo — 端到端：run_demo 不报错且输出包含关键概念痕迹。"""
import io
from contextlib import redirect_stdout

from crt_mini.demo import run_demo


def test_run_demo_runs_without_error_and_prints_scenarios(capsys):
    run_demo()
    out = capsys.readouterr().out
    # 6 个场景标题都在
    for marker in [
        "场景 1：镜像分层与内容寻址去重",
        "场景 2：overlayfs 联合挂载与 copy-on-write",
        "场景 3：namespace 隔离",
        "场景 4：cgroup 限制",
        "场景 5：OCI 生命周期",
        "场景 6：多架构 manifest list",
    ]:
        assert marker in out, f"missing scenario marker: {marker}"


def test_run_demo_shows_cow_and_oom_and_throttle(capsys):
    run_demo()
    out = capsys.readouterr().out
    # COW 代价（改 1 字节复制整文件）
    assert "整个" in out and "copy-up" in out
    # OOM
    assert "oom" in out.lower()
    # CPU throttle
    assert "throttled" in out.lower()
    # 多架构
    assert "linux/amd64" in out and "linux/arm64" in out


def test_run_demo_is_deterministic(capsys):
    run_demo()
    first = capsys.readouterr().out
    buf = io.StringIO()
    with redirect_stdout(buf):
        run_demo()
    second = buf.getvalue()
    assert first == second  # 无随机数，反复运行输出完全一致
