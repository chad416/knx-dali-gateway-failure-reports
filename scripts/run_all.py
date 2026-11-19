"""Regenerate every result: python scripts/run_all.py [--quick]

Full run: results/summary.json, results/tables.md, figures and the support-case evidence.
--quick:  fewer runs, written to results/quick/ (used in CI, not committed).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from daligw import constants as C  # noqa: E402
from daligw import electrical as E  # noqa: E402
from daligw import frames as F  # noqa: E402
from daligw import studies as S  # noqa: E402
from daligw.diagnose import LEVELS, diagnose  # noqa: E402
from daligw.evaluate import evaluate  # noqa: E402
from daligw.scenario import FAULTS, T_OBS, make_run  # noqa: E402
from daligw.variants import VARIANTS, emergency_scope  # noqa: E402

# reference palette (categorical order fixed), light surface
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6"]
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SHORT = {"HEALTHY": "healthy", "MAINS_SWITCHED": "mains switched", "LAMP_FAIL": "lamp fail",
         "GEAR_FAIL": "gear fail", "EMERG_TEST": "emergency test", "DUP_ADDR": "dup address",
         "NO_ADDR": "no address", "REPLACE_TWO": "replace two", "SUPPLY_LOW": "supply low",
         "BUS_SHORT": "bus short", "FAR_END": "far end", "NONE": "none"}


def style():
    plt.rcParams.update({
        "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
        "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
        "ytick.color": INK2, "text.color": INK, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
        "font.size": 9.5, "lines.linewidth": 2.0, "legend.frameon": False,
    })


def r(x, nd=4):
    if isinstance(x, (float, np.floating)):
        return round(float(x), nd)
    if isinstance(x, dict):
        return {k: r(v, nd) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [r(v, nd) for v in x]
    if isinstance(x, np.integer):
        return int(x)
    return x


# ---------------------------------------------------------------------------------------


def diagnosis_part(n_runs, n_sens, out, summary):
    res, runs = evaluate(n_runs, seed0=1)
    for lv in LEVELS:
        cv = res["certain_verdicts"][lv]
        cv["wrong_cases"] = cv["wrong_cases"][:10]
    summary["diagnosis"] = res
    # how many fault classes are certain-and-right in >= 95 % of runs, per level
    summary["diagnosis"]["classes_certain_95"] = {
        lv: sorted(f for f in FAULTS if res["certain_and_right"][lv][f] >= 0.95) for lv in LEVELS}
    summary["diagnosis"]["total_runs"] = n_runs * len(FAULTS)
    summary["diagnosis"]["polls_per_run"] = int(round(T_OBS / C.POLL_CYCLE_DEFAULT))
    summary["diagnosis"]["certain_total"] = {
        "right": sum(v["right"] for v in res["certain_verdicts"].values()),
        "wrong": sum(v["wrong"] for v in res["certain_verdicts"].values())}
    # DUP_ADDR: in how many polls is the collision visible, and when
    dup = [x for x in runs if x.fault == "DUP_ADDR"]
    vis = [sum(1 for row in x.evidence.trace if row[4] == "extra_low") / max(1, len(
        [row for row in x.evidence.trace if row[1] == x.truth["short"]])) for x in dup]
    summary["diagnosis"]["dup_share_of_polls_corrupted"] = {
        "mean": float(np.mean(vis)), "min": float(np.min(vis))}

    # sensitivity 1: the added gear is a twin (same product, same group)
    sens = {"runs": n_sens, "E3_certain": 0, "E1_right_first": 0, "E4_first_dup": 0,
            "never_corrupted": 0, "corrupted_polls_median": 0}
    counts = []
    for k in range(n_sens):
        run = make_run("DUP_ADDR", 700_000 + k, dup_twin_like=True)
        marks = [row[0] for row in run.evidence.trace if row[4] == "extra_low"]
        counts.append(len(marks))
        sens["never_corrupted"] += not marks
        e3 = diagnose(run.evidence, "E3").first
        sens["E3_certain"] += e3.cls == "DUP_ADDR" and e3.certainty == "certain"
        sens["E1_right_first"] += diagnose(run.evidence, "E1").first.cls == "DUP_ADDR"
        sens["E4_first_dup"] += diagnose(run.evidence, "E4").first.cls == "DUP_ADDR"
    sens["corrupted_polls_median"] = float(np.median(counts))
    sens["corrupted_polls_max"] = int(max(counts))
    summary["diagnosis"]["sens_dup_twin_like"] = sens

    # sensitivity 2: noise sigma 1.0 V instead of 0.6 V
    n_noise = max(4, n_sens // 2)
    res_n, _ = evaluate(n_noise, seed0=900_001, sigma=1.0)
    summary["diagnosis"]["sens_noise_1v"] = {
        "runs_per_class": n_noise,
        "certain_wrong": {lv: res_n["certain_verdicts"][lv]["wrong"] for lv in LEVELS},
        "certain_right": {lv: res_n["certain_verdicts"][lv]["right"] for lv in LEVELS},
        "wrong_examples": res_n["certain_verdicts"]["E3"]["wrong_cases"][:5],
        "healthy_right_first_E3": res_n["right_first"]["E3"]["HEALTHY"]}
    return res, runs


def polling_part(samples, summary):
    """Slot scheduler with variant B's documented rule (one gear and one of two error
    types per slot, S13 section 7.2), and the pause scheduler of S10. The 0.2 s slot is
    below variant B's shortest setting (0.5 s): it shows the scheduler, not that variant."""
    lo, hi = VARIANTS["B"].poll_settings_s.value
    rows = []
    for style_ in ("slot", "pause"):
        for n in (8, 16, 32, 64):
            for tc in (0.2, 0.5, 1.0, 2.0):
                for rho in (0.0, 0.5, 0.9):
                    d = S.reporting_delays(n, style_, tc, rho, samples, seed=n * 100 + int(tc * 10))
                    row = {"style": style_, "n": n, "t_cycle": tc, "rho": rho,
                           "mean": float(d.mean()), "p99": float(np.percentile(d, 99)),
                           "max": float(d.max()),
                           "setting_of_variant_B": style_ == "slot" and lo <= tc <= hi}
                    if style_ == "slot" or rho == 0.0:
                        row["formula_scan"] = S.scan_time_formula(n, style_, tc, rho)
                    rows.append(row)
    base = [x for x in rows if x["rho"] == 0.0]
    err = max(abs(x["max"] - x["formula_scan"]) / x["formula_scan"] for x in base)
    summary["polling"] = {"rows": rows, "max_rel_error_no_traffic": err,
                          "query_ms": 1e3 * F.query_time("low"),
                          "max_queries_per_s": 1 / F.query_time("low")}
    return rows


def find(rows, **kw):
    return next(x for x in rows if all(x[k] == v for k, v in kw.items()))


def stagger_part(summary):
    per, rows = S.stagger_table()
    vis = {}
    for name, tcmd in per.items():
        vis[name] = {"20ms": S.gear_until_visible(0.020, tcmd),
                     "100ms": S.gear_until_visible(0.100, tcmd)}
    summary["stagger"] = {"per_command_ms": {k: 1e3 * v for k, v in per.items()},
                          "rows": rows, "gear_until_visible": vis,
                          "sim_check_64": S.simulated_stagger(64)}
    return per, rows


SWEEP_RATIOS = np.round(np.arange(0.80, 2.201, 0.01), 2)


def _sweep(i_g, i_max, shape):
    sw = S.overload_sweep(i_g=i_g, i_max=i_max, shape=shape, ratios=SWEEP_RATIOS)
    first_err = next((x["ratio"] for x in sw if x["p_frame_near"] > 1e-3), None)
    first_lost = next((x["ratio"] for x in sw if x["found"] < 64), None)
    all_lost = next((x["ratio"] for x in sw if x["found"] == 0), None)
    return {"rows": sw, "ratio_first_frame_errors": first_err,
            "ratio_first_gear_lost": first_lost, "ratio_all_lost": all_lost,
            "pct_over_first_frame_errors": round(100 * (first_err - 1)),
            "pct_over_all_lost": round(100 * (all_lost - 1))}


def supply_part(summary):
    """Budget table over guaranteed currents, and the overload sweep with the documented
    currents of variant B (128 mA guaranteed, 250 mA maximum). Above the guaranteed
    current the supply curve is assumption A6 (two shapes)."""
    budget = S.budget_table()
    b = VARIANTS["B"]
    i_g, i_max = b.i_guaranteed_a.value, b.i_max_a.value
    sweeps = {shape: _sweep(i_g, i_max, shape) for shape in ("linear", "hard")}
    summary["supply"] = {"budget": budget, "sweep_variant": "B",
                         "sweep_i_g_ma": 1e3 * i_g, "sweep_i_max_ma": 1e3 * i_max,
                         "sweep_n_gear": 64, "sweep_length_m": 200, "sweep_mm2": 1.5,
                         "linear": {k: v for k, v in sweeps["linear"].items() if k != "rows"},
                         "hard": {k: v for k, v in sweeps["hard"].items() if k != "rows"},
                         "gear_64_draw_ma": 64 * C.I_GEAR_MAX * 1e3,
                         "guaranteed_needed_with_reserve_ma":
                             64 * C.I_GEAR_MAX * C.SUPPLY_RESERVE * 1e3}
    return sweeps


def variants_part(samples, summary):
    """Per documented variant: the facts with their sources, the polling rule where it is
    stated, the supply budget, the overload sweep, the short-circuit timing and whether the
    emergency-test fault class belongs to it."""
    out = {}
    e4_95 = summary["diagnosis"]["classes_certain_95"]["E4"]
    for key, v in VARIANTS.items():
        facts = {name: {"value": f.value, "source": f.source, "note": f.note}
                 for name, f in v.facts().items()}
        budget = S.variant_budget(v)
        i_b = budget["i_guaranteed_ma"] or budget["i_max_ma"]
        sweep = {}
        if key != "B":           # variant B's sweep is summary["supply"]
            for shape in ("linear", "hard"):
                sw = _sweep(1e-3 * i_b, 1e-3 * budget["i_max_ma"], shape)
                sweep[shape] = {k: x for k, x in sw.items() if k != "rows"}
        scope = emergency_scope(v)
        classes = [f for f in FAULTS if not (f == "EMERG_TEST" and scope != "in scope")]
        out[key] = {"name": v.name, "facts": facts,
                    "polling": S.variant_polling(v, 64, samples, seed=640),
                    "budget": budget, "overload_sweep": sweep,
                    "short_circuit": S.short_circuit_timing(v),
                    "emergency_scope": scope,
                    "fault_classes_claimed": len(classes),
                    "e4_certain_95_claimed": sorted(f for f in e4_95 if f in classes)}
    summary["variants"] = out
    return out


def energy_saving_part(trials, summary):
    """Open question A19 on variant B's energy-saving function: both hypotheses."""
    b = VARIANTS["B"]
    n, tc = 64, b.poll_default_s.value
    members = list(range(0, 64, 8))                  # 8 gear spread over the scan
    lights_off = [(600.0, 660.0), (1200.0, 1500.0), (2400.0, 6000.0)]   # 1 min, 5 min, 1 h
    cases = {}
    for delay in (10.0, 600.0):                      # shortest and longest documented
        for sup in (False, True):
            run = S.energy_saving_run(n, members, tc, lights_off, delay, sup)
            name = f"delay_{delay:g}s_{'suppressed' if sup else 'not_suppressed'}"
            cases[name] = {k: v for k, v in run.items() if k != "knx"}
            cases[name]["energy_saving_telegrams"] = sum(
                1 for e in run["knx"] if e[1] == "energy_saving")
            cases[name]["knx_excerpt"] = [list(e) for e in run["knx"][:6]]
    rows = []
    for delay in (10.0, 600.0):
        for members_n in (1, 8):
            for off in (30, 60, 120, 300, 900, 3600):
                p = S.energy_saving_false_failure(n, tc, off, delay, members_n, trials,
                                                  seed=off + int(delay))
                rows.append({"delay_off_s": delay, "members": members_n, "lights_off_s": off,
                             "p_not_suppressed": p, "p_suppressed": 0.0})
    summary["energy_saving"] = {"n_gear": n, "t_cycle": tc, "members": len(members),
                                "lights_off": lights_off, "cases": cases, "rows": rows}
    return rows


def wiring_part(summary):
    rows = S.wiring_table()
    summary["wiring"] = {"rows": rows,
                         "margin_to_receiver_v": C.DEV_V_LOW_MAX - rows[0]["drop_250ma_at_table_max"]}
    return rows


def mains_part(trials, summary):
    rows = []
    for n in (16, 64):
        for members in (1, 4):
            for off in (10, 30, 60, 120, 300, 600):
                p = S.false_failure_probability(n, 1.0, off, members, trials, seed=n + off)
                rows.append({"n": n, "members": members, "off_s": off, "p_sim": p,
                             "p_formula_one": S.false_failure_formula(n, 1.0, off)})
    one = [x for x in rows if x["members"] == 1]
    err = max(abs(x["p_sim"] - x["p_formula_one"]) for x in one)
    summary["mains"] = {"rows": rows, "max_abs_error_one_member": err}
    return rows


def support_case(out, summary):
    """Pick a separately switched circuit with at least three gear that went off and came
    back during the window, and write what each evidence level says."""
    for seed in range(4000, 4400):
        run = make_run("MAINS_SWITCHED", seed)
        ev = run.evidence
        silent = {row[1] for row in ev.trace if row[2] == "none"}
        if len(ev.site["circuit_members"]) >= 3 and run.variant == "1_off" and \
                len(silent) >= 3 and ev.site["circuit_log"][0][1] - ev.site["circuit_log"][0][0] > 300:
            break
    lines = [f"Support case evidence (simulated), MAINS_SWITCHED seed {run.truth['seed']}",
             f"luminaires installed: {ev.site['n_installed']}, known to the gateway: "
             f"{len(ev.diag['known'])}, polling 1 s per gear and error type", "",
             "E1 KNX failure objects:"]
    for t, obj, s, v in ev.knx:
        lines.append(f"  t={t:7.1f} s  {obj:4s} failure  gear {s}  -> {v}")
    for lv in LEVELS:
        lines += ["", diagnose(ev, lv).text()]
    lines += ["", "E3 trace excerpt (first poll without answer and first answer after it, per silent gear):"]
    seen_none, seen_back = set(), set()
    for t, s, kind, val, mark in ev.trace:
        if s not in silent:
            continue
        if kind == "none" and s not in seen_none:
            seen_none.add(s)
        elif kind == "ok" and s in seen_none and s not in seen_back:
            seen_back.add(s)
        else:
            continue
        st = "" if val is None else f" status=0x{val:02X} power_cycle_seen={val >> 7 & 1}"
        lines.append(f"  t={t:7.1f} s  QUERY STATUS gear {s:2d}: {kind}{st}")
    lines += ["", f"E4 site: circuit members {ev.site['circuit_members']}, "
              f"circuit log {[(round(a, 1), round(b, 1)) for a, b in ev.site['circuit_log']]}"]
    fixed = make_run("MAINS_SWITCHED", run.truth["seed"], bridge_circuit=True)
    fe = fixed.evidence
    rep_fixed = diagnose(fe, "E4")
    answered = sum(1 for row in fe.trace if row[1] in silent and row[2] == "ok")
    polled = sum(1 for row in fe.trace if row[1] in silent)
    lines += ["", "After the fix (circuit bridged, same installation and traffic):",
              f"  KNX failure objects: {len(fe.knx)}",
              f"  polls of the six gear answered: {answered} of {polled}",
              rep_fixed.text()]
    (out / "support_case.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    first_t = min(t for t, o, s, v in ev.knx if v == 1)
    summary["support_case"] = {
        "seed": run.truth["seed"], "members": ev.site["circuit_members"],
        "off": ev.site["circuit_log"][0], "first_object_s": first_t,
        "objects": len(ev.knx),
        "fixed": {"objects": len(fe.knx), "answered": answered, "polled": polled,
                  "e4": [rep_fixed.first.cls, rep_fixed.first.certainty]},
        "levels": {lv: [diagnose(ev, lv).first.cls, diagnose(ev, lv).first.certainty]
                   for lv in LEVELS}}


# ---------------------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------------------


def fig_diagnosis(res, out):
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.2), sharey=True)
    for ax, key, title in zip(axes, ("certain_and_right", "right_first"),
                              ("Right class, reported as certain", "Right class ranked first")):
        m = np.array([[res[key][lv][f] for lv in LEVELS] for f in FAULTS])
        ax.imshow(m, cmap="Blues", vmin=0, vmax=1, aspect="auto")
        ax.grid(False)
        for i in range(m.shape[0]):
            for j in range(m.shape[1]):
                ax.text(j, i, f"{100 * m[i, j]:.0f}", ha="center", va="center", fontsize=8.5,
                        color="white" if m[i, j] > 0.6 else INK)
        ax.set_xticks(range(len(LEVELS)), ["E1 KNX", "E2 +gateway", "E3 +trace", "E4 +site"])
        ax.set_yticks(range(len(FAULTS)), [SHORT[f] for f in FAULTS])
        ax.set_title(title + " (% of runs)", loc="left", fontsize=10.5)
    fig.suptitle(f"Diagnosis by evidence level, {res['runs_per_class']} runs per class",
                 x=0.01, ha="left", fontsize=11.5)
    fig.tight_layout()
    fig.savefig(out / "diagnosis_by_evidence.png", dpi=150)
    plt.close(fig)


def fig_confusion(res, out):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6), sharey=True)
    labels = list(FAULTS) + ["NONE"]
    for ax, lv in zip(axes, ("E1", "E3")):
        m = np.array([[res["confusion"][lv][f].get(g, 0) for g in labels] for f in FAULTS])
        ax.imshow(m, cmap="Blues", vmin=0, vmax=res["runs_per_class"], aspect="auto")
        ax.grid(False)
        for i in range(m.shape[0]):
            for j in range(m.shape[1]):
                if m[i, j]:
                    ax.text(j, i, str(m[i, j]), ha="center", va="center", fontsize=7.5,
                            color="white" if m[i, j] > 0.6 * res["runs_per_class"] else INK)
        ax.set_xticks(range(len(labels)), [SHORT[g] for g in labels], rotation=60, ha="right")
        ax.set_yticks(range(len(FAULTS)), [SHORT[f] for f in FAULTS])
        ax.set_title(f"{lv}: injected fault (rows) against first-ranked diagnosis",
                     loc="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(out / "confusion_matrices.png", dpi=150)
    plt.close(fig)


def fig_polling(rows, out):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    ax = axes[0]
    for c, tc in zip(SERIES, (0.2, 0.5, 1.0, 2.0)):
        pts = [find(rows, style="slot", n=n, t_cycle=tc, rho=0.0) for n in (8, 16, 32, 64)]
        ax.plot([p["n"] for p in pts], [p["max"] for p in pts], "-o", color=c, ms=5,
                label=f"{tc:g} s per slot")
    ax.set_xlabel("control gear on the line")
    ax.set_ylabel("worst reporting delay (s)")
    ax.set_xticks((8, 16, 32, 64))
    ax.set_title("No traffic: worst delay = 2 x gear x slot time", loc="left", fontsize=10)
    ax.legend()
    ax = axes[1]
    k = 0
    for style_ in ("slot", "pause"):
        for tc in (0.2, 1.0):
            pts = [find(rows, style=style_, n=64, t_cycle=tc, rho=rho) for rho in (0.0, 0.5, 0.9)]
            ax.plot([100 * p["rho"] for p in pts], [p["p99"] for p in pts], "-o",
                    color=SERIES[k], ms=5, label=f"{style_} {tc:g} s")
            k += 1
    ax.set_xlabel("bus time used by switching / dimming commands (%)")
    ax.set_ylabel("99th percentile reporting delay (s)")
    ax.set_title("64 gear: effect of command traffic", loc="left", fontsize=10)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "reporting_delay.png", dpi=150)
    plt.close(fig)


def fig_stagger(per, rows, out):
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    ns = [x["n"] for x in rows]
    names = [("dali2_low_max", "DALI-2 settling, low priority max"),
             ("dali2_middle_mean", "DALI-2 settling, middle priority mean"),
             ("dali2_high_min", "DALI-2 settling, high priority min"),
             ("v1_22te_unverified", "version 1, 22 Te (not verified)")]
    for c, (key, lab) in zip(SERIES, names):
        ax.plot(ns, [x[key] for x in rows], marker="o", color=c, ms=5, label=lab,
                ls="--" if key.startswith("v1") else "-")
    ax.plot(ns, [0] * len(ns), "-o", color=SERIES[4], ms=5, label="one group or broadcast frame")
    ax.axhline(0.1, color=INK2, lw=1, ls=":")
    ax.text(8, 0.13, "100 ms (assumed clearly visible)", color=INK2, fontsize=8)
    ax.set_xticks(ns)
    ax.set_xlabel("luminaires switched by individual commands")
    ax.set_ylabel("first to last luminaire (s)")
    ax.set_title("Individual addressing: visible ripple", loc="left", fontsize=10.5)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "stagger.png", dpi=150)
    plt.close(fig)


def fig_supply(sweeps, out):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    p = VARIANTS["P"]
    curves = [(f"variant B, supply model {shape}", sweeps[shape]["rows"], "-")
              for shape in ("linear", "hard")]
    curves.append(("variant P, 160 mA guaranteed = maximum",
                   _sweep(p.i_guaranteed_a.value, p.i_max_a.value, "linear")["rows"], "--"))
    for c, (label, rows, ls) in zip(SERIES, curves):
        x = [100 * (q["ratio"] - 1) for q in rows]
        axes[0].plot(x, [q["v_gateway"] for q in rows], color=c, ls=ls, label=label)
        axes[1].plot(x, [q["found"] for q in rows], color=c, ls=ls, label=label)
    axes[0].axhline(C.DEV_V_HIGH_MIN, color=INK2, lw=1, ls=":")
    axes[0].text(-18, C.DEV_V_HIGH_MIN + 0.3, "gateway reads high above 10 V", fontsize=8, color=INK2)
    axes[0].axhline(C.GEAR_V_HIGH_MIN, color=INK2, lw=1, ls="--")
    axes[0].text(-18, C.GEAR_V_HIGH_MIN - 1.0, "gear read high above 9.5 V", fontsize=8, color=INK2)
    axes[0].set_ylabel("idle bus voltage at the gateway (V)")
    axes[1].set_ylabel("gear found at commissioning (of 64)")
    for ax in axes:
        ax.set_xlabel("total draw above the guaranteed current (%)")
    axes[0].legend(fontsize=8, loc="lower left", bbox_to_anchor=(0.0, 0.06))
    axes[1].legend(fontsize=8, loc="center right")
    axes[0].set_title("Variant B: 128 mA guaranteed, 250 mA max; 200 m of 1.5 mm2",
                      loc="left", fontsize=10)
    axes[1].set_title("The gateway loses every gear at once", loc="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(out / "supply_overload.png", dpi=150)
    plt.close(fig)


def fig_wiring(out):
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    for c, (max_len, mm2) in zip(SERIES, C.CONDUCTOR_TABLE):
        L = np.linspace(10, 3 * max_len, 300)
        p = [E.p_frame_error(E.low_level_at_gateway(E.loop_resistance(x, mm2)),
                             C.V_SUPPLY_NOMINAL) for x in L]
        ax.semilogy(L, np.clip(p, 1e-9, 1), color=c, label=f"{mm2} mm2 (table limit {max_len:.0f} m)")
        ax.axvline(max_len, color=c, lw=1, ls=":")
    ax.set_ylim(1e-9, 1.5)
    ax.set_xlabel("distance gateway to farthest gear (m)")
    ax.set_ylabel("backward frame error probability")
    ax.set_title("Far end: frame errors against cable length (noise 0.6 V)", loc="left",
                 fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "wiring_far_end.png", dpi=150)
    plt.close(fig)


def fig_mains(rows, out):
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    k = 0
    for n in (16, 64):
        for members in (1, 4):
            pts = [x for x in rows if x["n"] == n and x["members"] == members]
            ax.plot([x["off_s"] for x in pts], [100 * x["p_sim"] for x in pts], "-o",
                    color=SERIES[k], ms=5, label=f"{n} gear, {members} on the circuit")
            k += 1
    ax.set_xscale("log")
    ax.set_xlabel("mains off period (s)")
    ax.set_ylabel("off periods that raise a false gear failure (%)")
    ax.set_title("Separately switched mains, 1 s polling slot", loc="left", fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "mains_false_failure.png", dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    out = ROOT / "results" / ("quick" if a.quick else "")
    out.mkdir(parents=True, exist_ok=True)
    n_runs, n_sens, samples, trials = (8, 8, 400, 400) if a.quick else (60, 60, 4000, 4000)
    style()
    summary: dict = {"quick": a.quick}
    summary["dali"] = {
        "bit_time_ms": 1e3 * C.T_BIT, "t_forward_ms": 1e3 * F.T_FORWARD,
        "t_forward_stated_ms": 1e3 * C.T_FORWARD_STATED, "t_backward_ms": 1e3 * F.T_BACKWARD,
        "t_backward_stated_ms": 1e3 * C.T_BACKWARD_STATED,
        "command_ms_middle_mean": 1e3 * F.command_time("middle"),
        "query_ms_low_mean": 1e3 * F.query_time("low"),
        "query_no_answer_ms": 1e3 * F.query_time_no_answer("low"),
    }
    res, _ = diagnosis_part(n_runs, n_sens, out, summary)
    prow = polling_part(samples, summary)
    per, srows = stagger_part(summary)
    sweeps = supply_part(summary)
    wiring_part(summary)
    mrows = mains_part(trials, summary)
    variants_part(samples, summary)
    energy_saving_part(trials, summary)
    support_case(out, summary)
    fig_diagnosis(res, out)
    fig_confusion(res, out)
    fig_polling(prow, out)
    fig_stagger(per, srows, out)
    fig_supply(sweeps, out)
    fig_wiring(out)
    fig_mains(mrows, out)
    name = "summary_quick.json" if a.quick else "summary.json"
    (out / name).write_text(json.dumps(r(summary), indent=1, sort_keys=False) + "\n",
                            encoding="utf-8")
    from make_tables import write_tables  # noqa: E402
    write_tables(json.loads((out / name).read_text(encoding="utf-8")), out / "tables.md")
    print(f"wrote {out / name}; certain verdicts {summary['diagnosis']['certain_total']}")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
