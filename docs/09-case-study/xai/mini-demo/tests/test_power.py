"""供电容量规划模块测试。"""

import pytest

from xai_case_mini import power


def test_it_load_100k_h100():
    # 100k * 700W * 1.2 = 84 MW
    assert power.it_load_mw(100_000, "H100-SXM") == pytest.approx(84.0)


def test_it_load_zero():
    assert power.it_load_mw(0, "H100-SXM") == 0.0


def test_it_load_unknown_gpu():
    with pytest.raises(KeyError):
        power.it_load_mw(1000, "V100")


def test_it_load_negative_raises():
    with pytest.raises(ValueError):
        power.it_load_mw(-1, "H100-SXM")


def test_facility_load_pue():
    # 84 MW IT * 1.25 PUE = 105 MW
    assert power.facility_load_mw(84.0, 1.25) == pytest.approx(105.0)


def test_facility_load_rejects_pue_below_one():
    with pytest.raises(ValueError):
        power.facility_load_mw(84.0, 0.9)


def test_training_demand_end_to_end():
    # 100k H100 @ DLC PUE 1.2: 84 * 1.2 = 100.8 MW
    assert power.training_demand_mw(100_000, "H100-SXM") == pytest.approx(100.8)


def test_capacity_timeline_constant_grid():
    plan = power.PowerPlan(grid_mw=150.0, horizon_days=30)
    tl = plan.capacity_timeline()
    assert tl.shape == (30,)
    assert (tl == 150.0).all()


def test_capacity_timeline_turbine_ramp():
    plan = power.PowerPlan(grid_mw=150.0, turbines=[(10, 5)], horizon_days=30)
    tl = plan.capacity_timeline()
    assert (tl[:10] == 150.0).all()
    assert (tl[10:] == 150.0 + 5 * power.TURBINE_MW).all()


def test_capacity_timeline_two_ramps():
    plan = power.PowerPlan(grid_mw=100.0, turbines=[(5, 2), (15, 3)],
                           horizon_days=30)
    tl = plan.capacity_timeline()
    assert tl[4] == 100.0
    assert tl[5] == 100.0 + 2 * power.TURBINE_MW
    assert tl[14] == 100.0 + 2 * power.TURBINE_MW
    assert tl[15] == 100.0 + 5 * power.TURBINE_MW


def test_shortfall_timeline_shape_and_values():
    plan = power.PowerPlan(grid_mw=100.0, horizon_days=10)
    rows = plan.shortfall_timeline(120.0)
    assert len(rows) == 10
    day, cap, demand, gap = rows[0]
    assert (day, cap, demand, gap) == (0, 100.0, 120.0, -20.0)


def test_max_shortfall_and_first_ok_day():
    plan = power.PowerPlan(grid_mw=100.0, turbines=[(10, 10)], horizon_days=30)
    assert plan.max_shortfall_mw(180.0) == pytest.approx(80.0)   # day0: 100-180
    assert plan.days_of_shortfall(180.0) == 10
    assert plan.first_day_meeting(180.0) == 10                    # 100+100=200>=180


def test_first_day_meeting_never():
    plan = power.PowerPlan(grid_mw=50.0, horizon_days=10)
    assert plan.first_day_meeting(1000.0) is None


def test_no_shortfall_when_capacity_suffices():
    plan = power.PowerPlan(grid_mw=150.0, horizon_days=30)
    assert plan.days_of_shortfall(100.0) == 0
    assert plan.max_shortfall_mw(100.0) == 0.0


def test_invalid_plan_args():
    with pytest.raises(ValueError):
        power.PowerPlan(grid_mw=-1)
    with pytest.raises(ValueError):
        power.PowerPlan(grid_mw=100, turbines=[(-1, 5)])
    with pytest.raises(ValueError):
        power.PowerPlan(grid_mw=100, horizon_days=0)
