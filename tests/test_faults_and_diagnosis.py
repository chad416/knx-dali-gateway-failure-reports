"""Every injected fault leaves its signature, and the engine reads it."""
import pytest

from daligw.diagnose import LEVELS, diagnose, knx_features, trace_features
from daligw.scenario import FAULTS, make_run

SEEDS = range(3)


def runs(fault):
    return [make_run(fault, 50_000 + 97 * s) for s in SEEDS]


def first(run, level):
    return diagnose(run.evidence, level).first


@pytest.mark.parametrize("fault", FAULTS)
def test_every_fault_is_certain_at_e4_without_wrong_certain(fault):
    for run in runs(fault):
        rep = diagnose(run.evidence, "E4")
        certain = [h.cls for h in rep.hypotheses if h.certainty == "certain"]
        assert all(c == fault for c in certain), (fault, certain)
        assert rep.first.cls == fault


def test_healthy_leaves_no_failure_object_and_clean_trace():
    for run in runs("HEALTHY"):
        assert run.evidence.knx == []
        assert all(row[2] == "ok" for row in run.evidence.trace)
        assert run.evidence.probe["missing_short"] == "none"


def test_lamp_failure_signature():
    for run in runs("LAMP_FAIL"):
        k = knx_features(run.evidence.knx)
        assert k["lamp"] == {run.truth["short"]} and not k["gear"]
        assert first(run, "E1").certainty == "certain"


def test_gear_failure_signature_silent_or_bit0():
    for run in [make_run("GEAR_FAIL", s) for s in range(12)]:
        tf = trace_features(run.evidence.trace, run.evidence.probe)
        s = run.truth["short"]
        if run.variant == "silent":
            assert s in tf["silent"] and not tf["silent"][s][2]     # never came back
            assert first(run, "E3").certainty != "certain"
        else:
            assert s in tf["bit0"]
            assert first(run, "E3").certainty == "certain"


def test_mains_switched_gear_come_back_and_e4_explains_them():
    for run in runs("MAINS_SWITCHED"):
        tf = trace_features(run.evidence.trace, run.evidence.probe)
        assert set(tf["silent"]) <= set(run.evidence.site["circuit_members"])
        if tf["silent"]:
            assert first(run, "E4").cls == "MAINS_SWITCHED"


def test_emergency_test_silences_the_paired_gear_only():
    for run in runs("EMERG_TEST"):
        tf = trace_features(run.evidence.trace, run.evidence.probe)
        assert set(tf["silent"]) <= {run.truth["short"]}


def test_duplicate_address_corrupts_with_extra_low():
    for run in runs("DUP_ADDR"):
        marks = {row[4] for row in run.evidence.trace if row[1] == run.truth["short"]}
        assert "extra_low" in marks and "weak" not in marks
        assert first(run, "E3").cls == "DUP_ADDR"


def test_twin_like_duplicate_is_visible_only_briefly():
    counts = []
    for s in range(10):
        run = make_run("DUP_ADDR", 7000 + s, dup_twin_like=True)
        counts.append(sum(1 for row in run.evidence.trace if row[4] == "extra_low"))
    assert max(counts) < 40          # out of 1800 polls
    assert min(counts) == 0          # sometimes never visible at all


def test_no_short_address_leaves_nothing_on_knx():
    for run in runs("NO_ADDR"):
        assert run.evidence.knx == []
        rep1 = first(run, "E1")
        assert rep1.cls == "HEALTHY" and rep1.certainty != "certain"
        assert first(run, "E3").cls == "NO_ADDR"


def test_replace_two_aborts_with_error_8():
    for run in runs("REPLACE_TWO"):
        assert run.evidence.diag["replace_result"] == 8
        assert first(run, "E2").cls == "REPLACE_TWO"


def test_supply_low_lowers_idle_voltage_and_hides_gear():
    for run in runs("SUPPLY_LOW"):
        assert run.evidence.probe["v_idle"] < 12.5
        assert run.truth["n_unfound"] >= 1
        assert run.evidence.site["i_total"] > run.evidence.site["supply_guaranteed"]


def test_bus_short_masks_everything():
    hidden = 0
    for s in range(10):
        run = make_run("BUS_SHORT", 300 + s)
        objs = {o for _, o, _, _ in run.evidence.knx}
        assert objs == {"bus"}
        if run.truth["hidden_lamp"] is not None:
            hidden += 1
            assert all(h.cls != "LAMP_FAIL" for h in diagnose(run.evidence, "E4").hypotheses)
    assert hidden >= 1


def test_far_end_gives_weak_marks_only():
    for run in runs("FAR_END"):
        marks = {row[4] for row in run.evidence.trace} - {""}
        assert marks == {"weak"}
        assert first(run, "E3").cls == "FAR_END"


def test_levels_are_cumulative_in_certainty():
    for fault in FAULTS:
        for run in runs(fault):
            prev = set()
            for lv in LEVELS:
                cur = {h.cls for h in diagnose(run.evidence, lv).hypotheses
                       if h.certainty == "certain"}
                assert prev <= cur, (fault, lv)
                prev = cur
