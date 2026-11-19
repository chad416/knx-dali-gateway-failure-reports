"""Write results/tables.md from the summary file (called by run_all.py)."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def pct(x):
    return f"{100 * x:.0f}"


def _fact(f) -> str:
    v = f["value"]
    if v is None:
        return "not stated"
    if isinstance(v, bool):
        v = "yes" if v else "no"
    elif isinstance(v, list):
        v = " / ".join(f"{x:g}" if isinstance(x, (int, float)) else str(x) for x in v)
    elif isinstance(v, float):
        v = f"{v:g}"
    return f"{v} ({f['source']})"


def _variant_tables(d: dict, L: list) -> None:
    vs = d["variants"]
    keys = list(vs)
    L.append("## T12 Gateway variants: documented facts\n")
    L.append("Values with their source (docs/SOURCES.md). \"not stated\": the documents read do "
             "not state it. Currents in A, times in s, lengths in m.\n")
    L.append("| fact | " + " | ".join(vs[k]["name"] for k in keys) + " |\n|---|" + "---|" * len(keys))
    for name in vs[keys[0]]["facts"]:
        L.append(f"| {name} | " + " | ".join(_fact(vs[k]["facts"][name]) for k in keys) + " |")
    L.append("")
    L.append("## T13 Gateway variants: polling, budget, overload, short circuit, emergency class\n")
    L.append("| item | " + " | ".join(keys) + " |\n|---|" + "---|" * len(keys))

    def row(label, fn):
        L.append(f"| {label} | " + " | ".join(fn(vs[k], k) for k in keys) + " |")

    def poll(v, key, field, fmt="{:.0f} s"):
        p = v["polling"]
        return fmt.format(p[field]) if p["documented"] else "not documented"

    row("worst reporting delay, 64 gear, default setting (quoted)", lambda v, k: poll(v, k, "worst_default_s"))
    row("simulated worst / mean, default setting",
        lambda v, k: f"{v['polling']['sim_max_default_s']:.1f} / {v['polling']['sim_mean_default_s']:.1f} s"
        if v["polling"]["documented"] else "not documented")
    row("worst delay at shortest / longest setting (arithmetic)",
        lambda v, k: f"{v['polling']['worst_shortest_setting_s']:.0f} / {v['polling']['worst_longest_setting_s']:.0f} s"
        if v["polling"]["documented"] else "not documented")
    row("budget basis", lambda v, k: v["budget"]["basis"])
    row("gear at 2 mA, no reserve / with / 1.2 reserve (capped at 64)",
        lambda v, k: f"{v['budget']['gear_no_reserve']} / {v['budget']['gear_with_reserve']}")
    row("same, uncapped", lambda v, k: f"{v['budget']['uncapped_no_reserve']} / {v['budget']['uncapped_with_reserve']}")
    row("maximum above budget current", lambda v, k: f"{v['budget']['headroom_above_guaranteed_pct']:.0f} %")
    row("wiring drop at the table limit (6.90 ohm) at the maximum current",
        lambda v, k: f"{v['budget']['drop_at_table_limit_v']:.2f} V")

    def over(v, k):
        if k == "B":
            s = d["supply"]
            return (f"all gear lost at {s['linear']['pct_over_all_lost']} % (linear) / "
                    f"{s['hard']['pct_over_all_lost']} % (hard) over {s['sweep_i_g_ma']:.0f} mA")
        o = v["overload_sweep"]
        return (f"all gear lost at {o['linear']['pct_over_all_lost']} % (linear) / "
                f"{o['hard']['pct_over_all_lost']} % (hard)")
    row("overload sweep, 64 gear, 200 m of 1.5 mm2 (A6)", over)

    def sc(v, k, field):
        s = v["short_circuit"]
        return f"{s[field]:g} s" if s["documented"] and s[field] is not None else "not documented"
    row("short: shutdown after", lambda v, k: sc(v, k, "shutdown_s"))
    row("short: bus back at most this long after it clears (A18)", lambda v, k: sc(v, k, "worst_wait_after_clear_s"))
    row("short: fault during it reported at most this long after it clears",
        lambda v, k: sc(v, k, "worst_report_after_clear_s"))
    row("emergency-test fault class", lambda v, k: v["emergency_scope"])
    row("fault classes claimed (of 11)", lambda v, k: str(v["fault_classes_claimed"]))
    row("classes certain in >= 95 % at E4, claimed", lambda v, k: str(len(v["e4_certain_95_claimed"])))
    L.append("")
    b = vs["B"]["short_circuit"]
    if b["documented"]:
        L.append("Variant B, bus back and worst report after a short of a given length (A18):\n")
        L.append("| short (s) | bus back after onset (s) | wait after clear (s) | worst report after clear (s) |\n|---|---|---|---|")
        for r in b["rows"]:
            L.append(f"| {r['short_s']:g} | {r['bus_back_s']:.1f} | {r['wait_after_clear_s']:.1f} | "
                     f"{r['worst_report_after_clear_s']:.1f} |")
        L.append("")
    es = d["energy_saving"]
    L.append("## T14 Open question A19: gear mains switched off by the energy-saving function\n")
    L.append(f"Variant B rule, {es['n_gear']} gear, {es['t_cycle']:g} s polling, {es['members']} gear on one "
             "energy-saving object; lights off for "
             + ", ".join(f"{b - a:g} s" for a, b in es["lights_off"]) + ".\n")
    L.append("| off delay | hypothesis | gear failure telegrams | gear reported failed | max failures in total | polls skipped |\n|---|---|---|---|---|---|")
    for name, c in es["cases"].items():
        delay, hyp = name.split("_", 2)[1], name.split("_", 2)[2].replace("_", " ")
        L.append(f"| {delay} | {hyp} | {c['gear_failure_telegrams']} | {len(c['gear_reported_failed'])} | "
                 f"{c['max_failures_in_total']} | {c['polls_skipped']} |")
    L.append("")
    L.append("| off delay (s) | gear on the object | lights off (s) | periods with a false failure, not suppressed | suppressed |\n|---|---|---|---|---|")
    for r in es["rows"]:
        L.append(f"| {r['delay_off_s']:g} | {r['members']} | {r['lights_off_s']} | {pct(r['p_not_suppressed'])} % | "
                 f"{pct(r['p_suppressed'])} % |")
    L.append("")


def write_tables(d: dict, path: Path) -> None:
    L = []
    dg = d["diagnosis"]
    levels, faults = dg["levels"], dg["faults"]
    L.append(f"# Result tables\n\nGenerated by `scripts/run_all.py`{' --quick' if d['quick'] else ''}. "
             "Simulated study, no hardware.\n")

    L.append("## T1 DALI frame timing (model)\n")
    L.append("| Quantity | Model | Stated in source |\n|---|---|---|")
    x = d["dali"]
    L.append(f"| bit time | {x['bit_time_ms']:.3f} ms | 0.833 ms |")
    L.append(f"| 16-bit forward frame (start + 16 bits + 2.45 ms stop) | {x['t_forward_ms']:.2f} ms | {x['t_forward_stated_ms']:.1f} ms |")
    L.append(f"| backward frame (start + 8 bits + stop) | {x['t_backward_ms']:.2f} ms | {x['t_backward_stated_ms']:.2f} ms |")
    L.append(f"| one command, middle priority, mean settling | {x['command_ms_middle_mean']:.1f} ms | |")
    L.append(f"| one query with answer, low priority, mean | {x['query_ms_low_mean']:.1f} ms | |")
    L.append(f"| one query without answer | {x['query_no_answer_ms']:.1f} ms | |\n")

    for key, title in (("certain_and_right", "T2 Right class and certain (% of runs)"),
                       ("right_first", "T3 Right class ranked first (% of runs)")):
        L.append(f"## {title}\n")
        L.append("| Fault | " + " | ".join(levels) + " |\n|---|" + "---|" * len(levels))
        for f in faults:
            L.append(f"| {f} | " + " | ".join(pct(dg[key][lv][f]) for lv in levels) + " |")
        L.append("")
    L.append("## T4 Certain verdicts\n")
    L.append("| Level | right | wrong | classes certain in >= 95 % of runs |\n|---|---|---|---|")
    for lv in levels:
        cv = dg["certain_verdicts"][lv]
        L.append(f"| {lv} | {cv['right']} | {cv['wrong']} | {', '.join(dg['classes_certain_95'][lv]) or '-'} |")
    L.append("")
    L.append("## T5 Outcome by variant (first rank right / missed)\n")
    L.append("| Fault | " + " | ".join(levels) + " |\n|---|" + "---|" * len(levels))
    for f in faults:
        cells = []
        for lv in levels:
            v = dg["by_variant"][lv].get(f, {})
            cells.append("; ".join(f"{k} {n}" for k, n in sorted(v.items())))
        L.append(f"| {f} | " + " | ".join(cells) + " |")
    L.append("")
    s = dg["sens_dup_twin_like"]
    L.append("## T6 Sensitivity runs of the diagnosis\n")
    L.append(f"- Duplicate address, added gear of the same product in the same group: {s['runs']} runs; "
             f"never a corrupted answer in {s['never_corrupted']}; median {s['corrupted_polls_median']:.0f} "
             f"corrupted polls (max {s['corrupted_polls_max']}); certain at E3 in {s['E3_certain']}; "
             f"ranked first at E4 in {s['E4_first_dup']}.")
    n = dg["sens_noise_1v"]
    L.append(f"- Noise 1.0 V instead of 0.6 V, {n['runs_per_class']} runs per class: wrong certain verdicts "
             + ", ".join(f"{lv} {n['certain_wrong'][lv]}" for lv in levels) + ".")
    h = dg["bus_short_hidden_lamp"]
    L.append(f"- Bus short with a lamp failure during the short: {h.get('hidden_lamp_reported', 0)} of "
             f"{h.get('with_hidden_lamp', 0)} lamp failures reported at any level.\n")

    L.append("## T7 Reporting delay of a failure (s)\n")
    L.append("| scheduler | gear | slot / pause (s) | traffic | mean | p99 | max | formula | setting of variant B |\n|---|---|---|---|---|---|---|---|---|")
    for row in d["polling"]["rows"]:
        if row["n"] in (16, 64):
            fs = f"{row['formula_scan']:.1f}" if "formula_scan" in row else "-"
            vb = "-" if row["style"] != "slot" else ("yes" if row.get("setting_of_variant_B") else "no")
            L.append(f"| {row['style']} | {row['n']} | {row['t_cycle']:g} | {pct(row['rho'])} % | "
                     f"{row['mean']:.1f} | {row['p99']:.1f} | {row['max']:.1f} | {fs} | {vb} |")
    L.append("")
    st = d["stagger"]
    L.append("## T8 First-to-last time with individual commands (s)\n")
    keys = list(st["per_command_ms"])
    L.append("| gear | " + " | ".join(keys) + " | group or broadcast |\n|---|" + "---|" * (len(keys) + 1))
    for row in st["rows"]:
        L.append(f"| {row['n']} | " + " | ".join(f"{row[k]:.2f}" for k in keys) + " | 0 |")
    L.append("| per command (ms) | " + " | ".join(f"{st['per_command_ms'][k]:.1f}" for k in keys) + " | |")
    L.append("| gear until > 20 ms | " + " | ".join(str(st["gear_until_visible"][k]["20ms"]) for k in keys) + " | |")
    L.append("| gear until > 100 ms | " + " | ".join(str(st["gear_until_visible"][k]["100ms"]) for k in keys) + " | |\n")

    sp = d["supply"]
    L.append("## T9 Supply budget at 2 mA per gear\n")
    L.append("| guaranteed current (mA) | gear, no reserve | gear, with / 1.2 reserve | uncapped with reserve |\n|---|---|---|---|")
    for row in sp["budget"]:
        L.append(f"| {row['guaranteed_ma']} | {row['gear_no_reserve']} | {row['gear_with_reserve']} | {row['uncapped_with_reserve']} |")
    L.append("")
    for shape in ("linear", "hard"):
        q = sp[shape]
        L.append(f"- Overload sweep, variant B ({sp['sweep_i_g_ma']:.0f} mA guaranteed, "
                 f"{sp['sweep_i_max_ma']:.0f} mA maximum), supply model {shape} (assumption A6): "
                 f"first frame errors at {q['ratio_first_frame_errors']} x "
                 f"guaranteed current, first gear lost at {q['ratio_first_gear_lost']}, all lost at {q['ratio_all_lost']}.")
    L.append("")
    L.append("## T10 Wiring: far-end reliability\n")
    L.append("| mm2 | table limit (m) | loop resistance at limit (ohm) | drop at 250 mA (V) | length for 2 V (m) | length for frame error < 0.1 % (noise 0.6 V, residual 0 / 1 / 2 V) |\n|---|---|---|---|---|---|")
    for row in d["wiring"]["rows"]:
        L.append(f"| {row['mm2']} | {row['table_max_m']:.0f} | {row['r_loop_at_table_max']:.2f} | "
                 f"{row['drop_250ma_at_table_max']:.2f} | {row['len_for_2v']:.0f} | "
                 f"{row['len_p0.001_s0.6_r0']:.0f} / {row['len_p0.001_s0.6_r1']:.0f} / {row['len_p0.001_s0.6_r2']:.0f} |")
    L.append("")
    L.append("## T11 Separately switched mains: off periods that raise a false gear failure\n")
    L.append("| gear | on circuit | off (s) | simulated | formula min(1, off / scan) |\n|---|---|---|---|---|")
    for row in d["mains"]["rows"]:
        L.append(f"| {row['n']} | {row['members']} | {row['off_s']} | {pct(row['p_sim'])} % | {pct(row['p_formula_one'])} % |")
    L.append("")
    if "variants" in d:
        _variant_tables(d, L)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    src = Path(sys.argv[1])
    write_tables(json.loads(src.read_text(encoding="utf-8")), src.with_name("tables.md"))
