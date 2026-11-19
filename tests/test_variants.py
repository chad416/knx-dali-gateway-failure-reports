"""The three documented gateway variants and the studies that use their facts."""
import pytest

from daligw import constants as C
from daligw import studies as S
from daligw.variants import VARIANTS, emergency_scope

B, P, L = VARIANTS["B"], VARIANTS["P"], VARIANTS["L"]


def test_every_fact_has_a_source_or_says_why_not():
    for v in VARIANTS.values():
        for name, f in v.facts().items():
            if f.documented:
                assert f.source.startswith("S1"), (v.key, name)
            else:
                assert f.source == "-" and f.note, (v.key, name)


def test_documented_limits():
    for v in VARIANTS.values():
        assert v.gear_per_channel.value == 64
        assert v.groups_per_channel.value == 16
    assert B.channels.value == (1, 2) and P.channels.value == 1 and L.channels.value == 1
    assert B.scenes_per_channel.value == 16 and P.scenes_per_channel.value == 16
    assert not L.scenes_per_channel.documented            # claim refuted in verification
    assert B.external_supply_allowed.value is False and L.external_supply_allowed.value is False
    assert not P.external_supply_allowed.documented
    assert B.cable_max_m.value == 300.0 and not P.cable_max_m.documented


def test_documented_supply_currents_differ_by_variant():
    assert (B.i_guaranteed_a.value, B.i_max_a.value) == (0.128, 0.250)
    assert (P.i_guaranteed_a.value, P.i_max_a.value) == (0.160, 0.160)
    assert L.i_guaranteed_a.value is None and L.i_max_a.value == 0.128


def test_simulated_gateway_polls_like_variant_b():
    assert C.POLL_CYCLE_DEFAULT == B.poll_default_s.value == 1.0
    assert C.POLL_ERROR_TYPES == B.poll_error_types.value == 2
    assert C.BUS_FAIL_DETECT_S == B.short_shutdown_s.value == 0.6


def test_polling_rule_only_where_documented():
    p = S.variant_polling(B, 64, 2000, seed=1)
    assert p["documented"] and p["worst_default_s"] == 128.0      # quoted figure
    assert p["sim_max_default_s"] == pytest.approx(128.0, rel=0.01)
    assert p["worst_shortest_setting_s"] == 64.0 and p["worst_longest_setting_s"] == 1280.0
    for v in (P, L):
        q = S.variant_polling(v, 64, 10, seed=1)
        assert q == {"documented": False, "note": v.poll_default_s.note}


def test_budget_per_variant():
    b, p, l_ = (S.variant_budget(v) for v in (B, P, L))
    assert (b["gear_no_reserve"], b["gear_with_reserve"]) == (64, 53)
    assert (p["gear_no_reserve"], p["gear_with_reserve"]) == (64, 64)
    assert (p["uncapped_no_reserve"], p["uncapped_with_reserve"]) == (80, 66)
    assert (l_["gear_no_reserve"], l_["gear_with_reserve"]) == (64, 53)
    assert l_["basis"].startswith("maximum only")
    assert b["headroom_above_guaranteed_pct"] == pytest.approx(95.3125)
    assert p["headroom_above_guaranteed_pct"] == 0.0
    assert b["drop_at_table_limit_v"] == pytest.approx(1.72, abs=0.01)


def test_overload_without_headroom_collapses_at_once():
    # variant P: guaranteed = maximum, so any overload removes the bus under both shapes
    for shape in ("linear", "hard"):
        sw = S.overload_sweep(i_g=0.160, i_max=0.160, shape=shape, ratios=[0.99, 1.02])
        assert sw[0]["found"] == 64 and sw[1]["found"] == 0
    # variant B with the hard shape holds until the 250 mA maximum
    sw = S.overload_sweep(i_g=0.128, i_max=0.250, shape="hard", ratios=[1.9, 1.96])
    assert sw[0]["found"] == 64 and sw[1]["found"] == 0


def test_short_circuit_timing_variant_b():
    sc = S.short_circuit_timing(B)
    assert sc["documented"] and sc["shutdown_s"] == 0.6 and sc["restart_s"] == 5.0
    assert sc["worst_wait_after_clear_s"] == 5.0
    assert sc["worst_report_after_clear_s"] == 133.0               # 5 s + 128 s scan
    for row in sc["rows"]:
        assert 0.0 <= row["wait_after_clear_s"] < 5.0
        assert row["bus_back_s"] == pytest.approx(S.bus_back_simulated(B, row["short_s"]), abs=0.011)
    assert not S.short_circuit_timing(P)["documented"]
    assert not S.short_circuit_timing(L)["documented"]


def test_energy_saving_both_hypotheses():
    off = [(100.0, 400.0)]                    # lights off for 300 s
    args = dict(n_gear=8, members=[1, 5], t_cycle=1.0, lights_off=off, delay_off=10.0)
    shown = S.energy_saving_run(suppressed=False, **args)
    hidden = S.energy_saving_run(suppressed=True, **args)
    # not suppressed: both gear fail within one scan (16 s) after the mains go off, and clear
    assert shown["gear_reported_failed"] == [1, 5]
    assert shown["max_failures_in_total"] == 2
    assert shown["first_failure_after_lights_off_s"] <= 10.0 + 16.0
    assert [e[3] for e in shown["knx"] if e[1] == "gear"].count(0) == 2
    # suppressed: only the energy-saving object itself appears on KNX
    assert hidden["gear_failure_telegrams"] == 0 and hidden["polls_skipped"] > 0
    assert {e[1] for e in hidden["knx"]} == {"energy_saving"}
    # lights off for less than the off delay: the mains never go off
    short = S.energy_saving_run(suppressed=False, **{**args, "lights_off": [(100.0, 105.0)]})
    assert short["knx"] == []
    assert S.energy_saving_false_failure(64, 1.0, 300, 600, 8, 200, seed=1) == 0.0
    assert S.energy_saving_false_failure(64, 1.0, 900, 600, 1, 200, seed=1) == 1.0


def test_emergency_class_only_where_tests_are_supported():
    assert emergency_scope(B) == "outside this variant"           # test commands not supported
    assert emergency_scope(P) == "not stated"
    assert emergency_scope(L) == "in scope"


def test_open_question_a19_is_not_answered_by_any_variant():
    for v in VARIANTS.values():
        assert not v.failures_suppressed_while_mains_off.documented
