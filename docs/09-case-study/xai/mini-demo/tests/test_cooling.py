"""散热密度模型测试。"""

import pytest

from xai_case_mini import cooling


def test_gpus_per_rack_air_h100():
    # 35kW / 700W = 50，但物理槽位 32 先到上限
    assert cooling.gpus_per_rack("H100-SXM", "air") == 32


def test_gpus_per_rack_dlc_h100():
    # 130kW / 700W = 185，物理槽位 72 先到上限
    assert cooling.gpus_per_rack("H100-SXM", "dlc") == 72


def test_gpus_per_rack_air_gb200_power_capped():
    # 35kW / 1200W = 29 < 32 物理槽位 —— 功率成为瓶颈
    assert cooling.gpus_per_rack("GB200", "air") == 29


def test_gpus_per_rack_unknown():
    with pytest.raises(ValueError):
        cooling.gpus_per_rack("H100-SXM", "immersion")
    with pytest.raises(ValueError):
        cooling.gpus_per_rack("TPU-v4", "air")


def test_racks_needed_ceil():
    # 100k H100 air: 100000/32 = 3125 整除
    assert cooling.racks_needed(100_000, "H100-SXM", "air") == 3125
    # 100k H100 dlc: ceil(100000/72) = 1389
    assert cooling.racks_needed(100_000, "H100-SXM", "dlc") == 1389


def test_racks_needed_zero_raises():
    with pytest.raises(ValueError):
        cooling.racks_needed(0, "H100-SXM", "air")


def test_dlc_fewer_racks_than_air():
    assert cooling.racks_needed(100_000, "H100-SXM", "dlc") < \
        cooling.racks_needed(100_000, "H100-SXM", "air")


def test_pue_values():
    assert cooling.pue("air") == pytest.approx(1.40)
    assert cooling.pue("dlc") == pytest.approx(1.20)
    with pytest.raises(ValueError):
        cooling.pue("oil")


def test_annual_energy_h100_dlc():
    # IT 84 MW * 1.2 PUE * 8760 h = 883,008 MWh
    assert cooling.annual_energy_mwh(100_000, "H100-SXM", "dlc") == \
        pytest.approx(84.0 * 1.2 * 8760)


def test_dlc_saves_energy_vs_air():
    air = cooling.annual_energy_mwh(100_000, "H100-SXM", "air")
    dlc = cooling.annual_energy_mwh(100_000, "H100-SXM", "dlc")
    assert dlc < air
    assert air / dlc == pytest.approx(1.40 / 1.20)


def test_annual_co2():
    mwh = cooling.annual_energy_mwh(100_000, "H100-SXM", "dlc")
    assert cooling.annual_co2_tons(100_000, "H100-SXM", "dlc") == \
        pytest.approx(mwh * cooling.GRID_CO2_KG_PER_KWH)


def test_cooling_comparison_shape():
    rows = cooling.cooling_comparison(100_000, "H100-SXM")
    assert [r.cooling for r in rows] == ["air", "dlc"]
    assert rows[1].racks < rows[0].racks
    assert rows[1].annual_co2_tons < rows[0].annual_co2_tons
