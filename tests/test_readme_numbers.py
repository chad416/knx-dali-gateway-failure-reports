"""README numbers must come from results/summary.json."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "results" / "summary.json"
sys.path.insert(0, str(ROOT / "scripts"))

pytestmark = pytest.mark.skipif(not SUMMARY.exists(), reason="results/summary.json not generated")


def test_every_readme_number_is_in_summary():
    from check_readme_numbers import check
    assert check(ROOT / "README.md", SUMMARY) == []


def test_headline_numbers():
    d = json.loads(SUMMARY.read_text(encoding="utf-8"))
    readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").split())
    dg = d["diagnosis"]
    ct = dg["certain_total"]
    assert ct["wrong"] == 0
    assert f'{ct["right"]} "certain" verdicts and 0 of them were wrong' in readme
    assert f'{dg["total_runs"]} randomised virtual installations' in readme
    assert dg["certain_and_right"]["E1"]["LAMP_FAIL"] == 1.0
    assert dg["certain_and_right"]["E1"]["BUS_SHORT"] == 1.0
    assert dg["right_first"]["E1"]["NO_ADDR"] == 0.0
    assert dg["certain_and_right"]["E3"]["DUP_ADDR"] == 1.0
    assert f'{round(100 * dg["certain_and_right"]["E3"]["GEAR_FAIL"])} % of gear failures' in readme
    h = dg["bus_short_hidden_lamp"]
    assert h.get("hidden_lamp_reported", 0) == 0
    assert f'0 of {h["with_hidden_lamp"]} lamp failures' in readme
    p = next(x for x in d["polling"]["rows"]
             if x["style"] == "slot" and x["n"] == 64 and x["t_cycle"] == 1.0 and x["rho"] == 0.0)
    assert p["formula_scan"] == 128.0 and f'simulated {p["max"]:.1f} s' in readme
    assert f'{d["stagger"]["per_command_ms"]["dali2_middle_mean"]:.1f} ms' in readme
    assert d["stagger"]["gear_until_visible"]["dali2_middle_mean"]["100ms"] == 4
    assert f'{d["supply"]["guaranteed_needed_with_reserve_ma"]:.1f} mA' in readme


def test_variant_numbers():
    d = json.loads(SUMMARY.read_text(encoding="utf-8"))
    readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").split())
    sp = d["supply"]
    assert sp["sweep_variant"] == "B" and sp["sweep_i_g_ma"] == 128.0
    assert f'fail at {sp["linear"]["pct_over_first_frame_errors"]} % overload' in readme
    assert f'none of 64 gear at {sp["linear"]["pct_over_all_lost"]} %' in readme
    assert f'nothing happens until {sp["hard"]["pct_over_all_lost"]} %' in readme
    v = d["variants"]
    assert v["B"]["budget"]["gear_with_reserve"] == 53 and v["P"]["budget"]["gear_with_reserve"] == 64
    assert v["B"]["polling"]["worst_default_s"] == 128.0
    assert not v["P"]["polling"]["documented"] and not v["L"]["polling"]["documented"]
    sc = v["B"]["short_circuit"]
    assert f'at most {sc["worst_report_after_clear_s"]:.0f} s after it clears' in readme
    assert v["B"]["emergency_scope"] == "outside this variant"
    assert f'claims {v["B"]["fault_classes_claimed"]} classes, not 11' in readme
