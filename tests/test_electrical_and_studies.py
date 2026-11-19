"""Wiring, supply budget, reception error model, polling delay, mains false failures."""
import random

import numpy as np
import pytest

from daligw import constants as C
from daligw import electrical as E
from daligw import frames as F
from daligw import studies as S
from daligw.line import receive


def test_conductor_table_is_a_constant_resistance_rule():
    # every row of the table gives the same loop resistance: 6.90 ohm, 1.72 V at 250 mA
    rs = [E.loop_resistance(m, mm2) for m, mm2 in C.CONDUCTOR_TABLE]
    assert max(rs) - min(rs) < 1e-9
    assert rs[0] == pytest.approx(6.897, abs=0.01)
    for m, mm2 in C.CONDUCTOR_TABLE:
        assert E.drop_at_max_current(m, mm2) <= C.V_DROP_MAX


def test_required_cross_section():
    assert E.required_cross_section(80) == 0.5
    assert E.required_cross_section(120) == 0.75
    assert E.required_cross_section(300) == 1.5
    assert E.required_cross_section(301) is None


def test_node_voltages_daisy_chain():
    # two loads of 0.1 A at 100 m and 200 m on 1.5 mm2: first segment carries 0.2 A
    v = E.node_voltages(16.0, [200.0, 100.0], [0.1, 0.1], 1.5)
    r100 = E.loop_resistance(100, 1.5)
    assert v[1] == pytest.approx(16.0 - 0.2 * r100)
    assert v[0] == pytest.approx(16.0 - 0.2 * r100 - 0.1 * r100)


def test_supply_budget():
    s = E.Supply(i_guaranteed=0.220)
    assert s.budget_gear() == 64                              # 110 by current, capped at 64
    assert E.Supply(0.100).budget_gear() == 50
    assert E.Supply(0.100).budget_gear(reserve=1.2) == 41
    assert E.Supply(0.128).budget_gear() == 64                # 64 x 2 mA = 128 mA
    assert E.Supply(0.128).budget_gear(reserve=1.2) == 53
    assert E.Supply(0.150).budget_gear(reserve=1.2, i_other=0.020) == 52


def test_supply_curves():
    lin = E.Supply(0.150, shape="linear")
    hard = E.Supply(0.150, shape="hard")
    assert lin.voltage(0.150) == C.V_SUPPLY_NOMINAL
    assert lin.voltage(0.200) == pytest.approx(16.0 * 50 / 100)
    assert lin.voltage(0.250) == 0.0
    assert hard.voltage(0.249) == C.V_SUPPLY_NOMINAL and hard.voltage(0.250) == 0.0


def test_p_frame_error_limits():
    assert E.p_frame_error(0.0, 16.0) < 1e-12
    assert E.p_frame_error(1.72, 16.0) < 1e-4       # table limit at 0.6 V noise
    assert E.p_frame_error(4.5, 16.0) > 0.99        # low exactly at the threshold
    assert E.p_frame_error(1.0, 10.0) > 0.99        # idle high exactly at the threshold
    assert E.p_frame_error(1.0, 16.0, sigma=0) == 0.0
    assert E.p_frame_error(5.0, 16.0, sigma=0) == 1.0


def test_weak_far_end_gives_weak_marks_only():
    rng = random.Random(3)
    kinds = [receive([(0x04, 0, 4.5)], 16.0, rng) for _ in range(200)]
    corrupt = [k for k in kinds if k.kind == "corrupt"]
    assert len(corrupt) > 150
    assert all(k.mark == "weak" for k in corrupt)


def test_receive_collision_in_noise_is_extra_low():
    rng = random.Random(4)
    rec = receive([(0x04, 0, 0.5), (0x84, 0, 0.5)], 16.0, rng)
    assert rec.kind == "corrupt" and rec.mark == "extra_low"


def test_polling_delay_no_traffic_matches_formula():
    # S9: 64 gear, 1 s per gear and error type -> 128 s for a full scan
    assert S.scan_time_formula(64, "slot", 1.0) == 128.0
    d = S.reporting_delays(64, "slot", 1.0, 0.0, 2000, seed=1)
    assert d.max() == pytest.approx(128.0, rel=0.01)
    assert d.mean() == pytest.approx(64.0, rel=0.05)
    d = S.reporting_delays(16, "pause", 0.2, 0.0, 2000, seed=2)
    assert d.max() == pytest.approx(S.scan_time_formula(16, "pause", 0.2), rel=0.01)


def test_heavy_traffic_stretches_a_short_cycle():
    quiet = S.reporting_delays(64, "slot", 0.2, 0.0, 1000, seed=5)
    busy = S.reporting_delays(64, "slot", 0.2, 0.9, 1000, seed=5)
    assert np.percentile(busy, 99) > 2 * np.percentile(quiet, 99)
    assert S.scan_time_formula(64, "slot", 0.2, 0.9) > S.scan_time_formula(64, "slot", 0.2)


def test_gear_until_visible():
    per = F.command_time("middle")       # 33.6 ms
    assert S.gear_until_visible(0.020, per) == 2
    assert S.gear_until_visible(0.100, per) == 4
    assert F.stagger(4, per) > 0.100 >= F.stagger(3, per)


def test_false_failure_probability_matches_formula():
    p = S.false_failure_probability(64, 1.0, 64.0, 1, 4000, seed=1)
    assert p == pytest.approx(0.5, abs=0.03)
    assert S.false_failure_formula(64, 1.0, 64.0) == 0.5
    assert S.false_failure_probability(16, 1.0, 40.0, 1, 500, seed=1) == 1.0
    more = S.false_failure_probability(64, 1.0, 30.0, 4, 2000, seed=2)
    one = S.false_failure_probability(64, 1.0, 30.0, 1, 2000, seed=2)
    assert more > one


def test_budget_table_and_overload_sweep():
    rows = {r["guaranteed_ma"]: r for r in S.budget_table()}
    assert rows[183]["gear_with_reserve"] == 64
    sw = S.overload_sweep(ratios=[0.9, 1.0, 1.5])
    assert sw[0]["found"] == 64 and sw[1]["found"] == 64
    assert sw[2]["found"] == 0


def test_wiring_table_margin():
    rows = S.wiring_table(sigmas=(0.6,), residuals=(0.0,))
    for row in rows:
        assert row["len_p0.001_s0.6_r0"] > row["table_max_m"]
