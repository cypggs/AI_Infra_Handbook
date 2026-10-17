"""建设排程模块测试。"""

import pytest

from xai_case_mini import build


def test_schedule_simple_chain():
    tasks = [build.Task("a", 5), build.Task("b", 3, ("a",))]
    result = build.schedule(tasks)
    assert result["a"] == (0, 5)
    assert result["b"] == (5, 8)
    assert build.makespan_days(tasks) == 8


def test_schedule_parallel_branches():
    tasks = [
        build.Task("root", 10),
        build.Task("slow", 20, ("root",)),
        build.Task("fast", 5, ("root",)),
        build.Task("join", 1, ("slow", "fast")),
    ]
    result = build.schedule(tasks)
    assert result["join"] == (30, 31)
    assert build.critical_path(tasks) == ["root", "slow", "join"]


def test_schedule_duplicate_names():
    with pytest.raises(ValueError):
        build.schedule([build.Task("a", 1), build.Task("a", 2)])


def test_schedule_cycle():
    with pytest.raises(ValueError):
        build.schedule([build.Task("a", 1, ("b",)), build.Task("b", 1, ("a",))])


def test_critical_path_single_task():
    assert build.critical_path([build.Task("only", 7)]) == ["only"]


def test_critical_path_goal():
    tasks = [
        build.Task("root", 10),
        build.Task("bg", 100, ("root",)),   # 后台长尾
        build.Task("work", 20, ("root",)),
    ]
    # 默认（makespan 目标）走后台长尾；显式 goal 走真正的交付链
    assert build.critical_path(tasks) == ["root", "bg"]
    assert build.critical_path(tasks, goal="work") == ["root", "work"]
    with pytest.raises(ValueError):
        build.critical_path(tasks, goal="nope")


def test_conventional_plan_sanity():
    tasks = build.conventional_plan()
    span = build.makespan_days(tasks)
    # 教科书流程：12-24 个月数量级
    assert 365 <= span <= 730
    names = {t.name for t in tasks}
    assert "first_training" in names


def test_aggressive_plan_faster_than_conventional():
    assert build.compression_report()["cluster_ready_days"] < \
        build.makespan_days(build.conventional_plan())


def test_aggressive_cluster_ready_about_122_days():
    report = build.compression_report()
    # 模拟调参目标：复现 Colossus "122 天" 数量级
    assert report["cluster_ready_days"] <= 130
    assert report["first_training_day"] < report["cluster_ready_days"]


def test_aggressive_grid_off_critical_path():
    report = build.compression_report()
    path = report["aggressive_critical_path"]
    assert "grid_upgrade" not in path  # 电网扩容退出关键路径
    assert "temp_turbines" in path
    # 电网扩容作为后台任务仍在跑，且在集群就绪之后才完工
    assert report["grid_upgrade_done_day"] > report["cluster_ready_days"]


def test_compression_ratio_range():
    report = build.compression_report()
    assert 2.5 <= report["compression_ratio"] <= 6.0


def test_all_deps_resolve():
    for plan_fn in (build.conventional_plan, build.aggressive_plan):
        tasks = plan_fn()
        names = {t.name for t in tasks}
        for t in tasks:
            for d in t.deps:
                assert d in names
