"""Diagnosis engine. It sees only the evidence of one level and never the truth.

Levels (cumulative):
  E1  failure objects on the KNX side over time
  E2  + gateway diagnostics (known gear, bus state, result of the automatic replacement)
  E3  + DALI bus trace of the gateway's polls, an active probe after the window
        (QUERY STATUS to all 64 short addresses, QUERY MISSING SHORT ADDRESS) and the idle
        bus voltage at the gateway terminals
  E4  + site facts (luminaire list, separately switched circuits and their log, emergency
        pairs and test schedule, exchanged gear, cable, supply rating, current draw)

"certain" means: the evidence contains something that, under premises P1..P5 (DOSSIER 4),
only this class of the catalogue can produce.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import constants as C
from . import electrical as E

LEVELS = ("E1", "E2", "E3", "E4")
RANK = {"certain": 0, "likely": 1, "possible": 2}
WEAK_MIN = 3   # weak answers needed before wiring resistance is called certain (noise, A5)


@dataclass
class Hypothesis:
    cls: str
    certainty: str
    reason: str
    score: float = 0.0


@dataclass
class Report:
    level: str
    hypotheses: list[Hypothesis] = field(default_factory=list)

    @property
    def first(self) -> Hypothesis | None:
        return self.hypotheses[0] if self.hypotheses else None

    def text(self) -> str:
        lines = [f"Evidence level {self.level}"]
        for i, h in enumerate(self.hypotheses, 1):
            lines.append(f"{i}. {h.cls} [{h.certainty}] {h.reason}")
        return "\n".join(lines)


class _Builder:
    def __init__(self):
        self.h: dict[str, Hypothesis] = {}

    def add(self, cls, certainty, reason, score=0.0):
        old = self.h.get(cls)
        if old is None or RANK[certainty] < RANK[old.certainty] or (
                RANK[certainty] == RANK[old.certainty] and score > old.score):
            self.h[cls] = Hypothesis(cls, certainty, reason, score)

    def ranked(self):
        return sorted(self.h.values(), key=lambda x: (RANK[x.certainty], -x.score, x.cls))


# ---------------------------------------------------------------------------------------
# features
# ---------------------------------------------------------------------------------------


def knx_features(knx):
    f = {"bus": False, "lamp": set(), "gear_sets": {}, "gear_last": {}, "gear_first": {},
         "gear_clear": {}}
    for t, obj, s, v in knx:
        if obj == "bus" and v:
            f["bus"] = True
        elif obj == "lamp" and v:
            f["lamp"].add(s)
        elif obj == "gear":
            if v:
                f["gear_sets"][s] = f["gear_sets"].get(s, 0) + 1
                f["gear_first"].setdefault(s, t)
            else:
                f["gear_clear"].setdefault(s, t)
            f["gear_last"][s] = v
    f["gear"] = set(f["gear_sets"])
    f["flapping"] = {s for s, n in f["gear_sets"].items() if n >= 2}
    f["stays"] = {s for s, v in f["gear_last"].items() if v == 1}
    return f


def correlated(times: list[float], window: float = 150.0) -> bool:
    return len(times) >= 2 and max(times) - min(times) <= window


def trace_features(trace, probe):
    per: dict[int, list] = {}
    for t, s, kind, value, mark in trace:
        per.setdefault(s, []).append((t, kind, value, mark))
    f = {"extra_low": set(), "weak": set(), "bit0": set(), "bit1": set(), "silent": {},
         "returned_with_bit7": set(), "none_times": {}, "weak_count": 0}
    for s, rows in per.items():
        none_t = [t for t, k, _, _ in rows if k == "none"]
        for t, k, v, m in rows:
            if k == "corrupt":
                if m in ("extra_low", "mixed"):
                    f["extra_low"].add(s)
                if m in ("weak", "mixed"):
                    f["weak"].add(s)
                    f["weak_count"] += 1
            elif k == "ok":
                if v & 1:
                    f["bit0"].add(s)
                if v >> 1 & 1:
                    f["bit1"].add(s)
        if none_t:
            last_none = max(none_t)
            after = [(t, v) for t, k, v, _ in rows if k == "ok" and t > last_none]
            f["silent"][s] = (min(none_t), last_none, bool(after))
            f["none_times"][s] = none_t
            if after and after[0][1] >> 7 & 1:
                f["returned_with_bit7"].add(s)
    st = probe.get("status", {})
    for s, (kind, value, mark) in st.items():
        if kind == "ok":
            if value & 1:
                f["bit0"].add(s)
            if value >> 1 & 1:
                f["bit1"].add(s)
        elif kind == "corrupt":
            if mark in ("extra_low", "mixed"):
                f["extra_low"].add(s)
            if mark in ("weak", "mixed"):
                f["weak"].add(s)
    return f


# ---------------------------------------------------------------------------------------
# engine
# ---------------------------------------------------------------------------------------


def diagnose(ev, level: str) -> Report:
    if level not in LEVELS:
        raise ValueError(level)
    li = LEVELS.index(level)
    b = _Builder()
    k = knx_features(ev.knx)

    # ---------------- E1: failure objects only ----------------------------------------
    if k["bus"]:
        b.add("BUS_SHORT", "certain",
              "bus failure object set: short circuit or supply failure on the DALI line; "
              "no gear can be queried, so other faults stay hidden while it lasts", 10)
    for s in sorted(k["lamp"]):
        b.add("LAMP_FAIL", "certain",
              f"lamp failure object for gear {s}: the gear answered with status bit 1", 9)
    gear = k["gear"]
    if gear:
        first = [k["gear_first"][s] for s in gear]
        clears = [k["gear_clear"][s] for s in gear if s in k["gear_clear"]]
        if len(k["flapping"]) == 1 and len(gear) == 1:
            b.add("DUP_ADDR", "possible", "one gear failure object toggles repeatedly", 3)
            b.add("FAR_END", "possible", "toggling failure object: unreliable answers", 2)
            b.add("MAINS_SWITCHED", "possible", "repeated mains off periods give toggling", 1)
        elif len(k["flapping"]) >= 2:
            b.add("FAR_END", "possible", "several gear toggle independently", 3)
            b.add("MAINS_SWITCHED", "possible", "several gear toggle", 2)
            b.add("SUPPLY_LOW", "possible", "unreliable answers from several gear", 1)
        if len(gear) >= 2 and correlated(first) and (not clears or correlated(clears)):
            b.add("MAINS_SWITCHED", "likely" if clears else "possible",
                  f"{len(gear)} gear fail (and recover) within one polling scan of each "
                  "other: they lost power together", 4)
        if len(gear) == 2 and not k["flapping"] and k["stays"] == gear and not correlated(first):
            b.add("REPLACE_TWO", "possible", "two gear failed at different times", 2)
            b.add("GEAR_FAIL", "possible", "two independent gear failures", 1.5)
        if len(gear) == 1 and not k["flapping"]:
            s = next(iter(gear))
            if s in k["stays"]:
                b.add("GEAR_FAIL", "likely", f"gear {s} failed and never recovered", 3)
                b.add("EMERG_TEST", "possible", "a long emergency test looks the same", 1)
                b.add("MAINS_SWITCHED", "possible", "its mains may be off", 1)
            else:
                b.add("EMERG_TEST", "likely", f"gear {s} silent for a while, then back", 3)
                b.add("MAINS_SWITCHED", "possible", "its mains may have been off", 2)
                b.add("DUP_ADDR", "possible", "intermittent collision", 1)
    if not k["bus"] and not k["lamp"] and not gear:
        b.add("HEALTHY", "likely", "no failure object changed", 2)
        for c in ("NO_ADDR", "SUPPLY_LOW", "DUP_ADDR"):
            b.add(c, "possible", "leaves no failure object", 1)

    if li < 1:
        return Report(level, b.ranked())

    # ---------------- E2: gateway diagnostics -----------------------------------------
    d = ev.diag
    if d["replace_result"] in (8, 11):
        b.add("REPLACE_TWO", "certain",
              f"automatic replacement aborted with error {d['replace_result']} "
              f"({C.REPLACE_ERRORS[d['replace_result']]})", 10)
    if not d["known"] and not k["bus"]:
        b.add("SUPPLY_LOW", "likely", "the gateway knows no gear at all", 4)

    if li < 2:
        return Report(level, b.ranked())

    # ---------------- E3: bus trace, probe, idle voltage ------------------------------
    p = ev.probe
    tf = trace_features(ev.trace, p)
    known = set(d["known"])
    v_idle = p.get("v_idle", 0.0)
    bus_up = v_idle >= C.GEAR_V_HIGH_MIN
    if bus_up and v_idle < C.SUPPLY_V_RANGE[0]:
        b.add("SUPPLY_LOW", "certain",
              f"idle bus voltage {v_idle:.1f} V at the gateway, below the 12 V a supply "
              "must deliver: the supply is loaded beyond its rating", 9)
    for s in sorted(tf["extra_low"] & known):
        b.add("DUP_ADDR", "certain",
              f"answers to short address {s} carry a low level where a valid frame is "
              "high: two transmitters answered at once", 9)
    if tf["weak"] and bus_up and v_idle >= C.SUPPLY_V_RANGE[0]:
        b.add("FAR_END", "certain" if tf["weak_count"] >= WEAK_MIN else "likely",
              f"answers from {len(tf['weak'])} gear with a low level that does not reach "
              "the receiver threshold while the idle voltage is normal: wiring resistance", 8)
    for s in sorted(tf["bit0"]):
        b.add("GEAR_FAIL", "certain", f"gear {s} answers with status bit 0 (control gear "
              "failure)", 9)
    for s in sorted(tf["bit1"]):
        b.add("LAMP_FAIL", "certain", f"gear {s} answers with status bit 1 (lamp failure)", 9)
    unknown_answering = {s for s, (kind, _, _) in p.get("status", {}).items()
                         if kind == "ok" and s not in known}
    if unknown_answering:
        b.add("NO_ADDR", "certain",
              f"short address(es) {sorted(unknown_answering)} answer but are unknown to "
              "the gateway: gear added after commissioning", 8)
    clean_yes = p.get("missing_short") == "ok"
    any_anomaly = bool(gear or k["lamp"] or tf["weak"] or tf["extra_low"] or tf["silent"])
    if p.get("missing_short") != "none" and bus_up:
        if (clean_yes and not any_anomaly and d["replace_result"] is None
                and v_idle >= C.SUPPLY_V_RANGE[0]):
            b.add("NO_ADDR", "certain", "a gear without short address answers and nothing "
                  "else is abnormal: it was added and never searched", 8)
        else:
            b.add("NO_ADDR", "possible", "gear without short address present", 1)
    silent_back = {s for s, (_, _, back) in tf["silent"].items() if back}
    silent_gone = {s for s, (_, _, back) in tf["silent"].items() if not back}
    rb = tf["returned_with_bit7"]
    if len(silent_back) >= 2:
        b.add("MAINS_SWITCHED", "likely",
              f"{len(silent_back)} gear were silent and came back ({len(rb)} of them with "
              "status bit 7, power cycle seen): they lost mains, they are not defective", 5)
    elif len(silent_back) == 1:
        b.add("EMERG_TEST", "likely", "one gear was silent for a while and came back"
              + (" with status bit 7 (power cycle seen)" if rb else ""), 4)
        b.add("MAINS_SWITCHED", "possible", "one gear lost mains for a while", 3)
    if silent_gone and not k["bus"]:
        b.add("GEAR_FAIL", "likely" if len(silent_gone) == 1 else "possible",
              f"gear {sorted(silent_gone)} stopped answering for good", 3)
    if bus_up and not any_anomaly and p.get("missing_short") == "none" and \
            not unknown_answering and v_idle >= C.SUPPLY_V_RANGE[0]:
        b.add("HEALTHY", "likely", "trace and probe clean", 3)
        b.add("DUP_ADDR", "possible", "two identical gear with one address answer as one", 1)

    if li < 3:
        return Report(level, b.ranked())

    # ---------------- E4: site facts --------------------------------------------------
    st = ev.site
    off_log = st["circuit_log"]
    members = set(st["circuit_members"])
    tests = st["tests"]
    def inside(times, intervals):
        """Every poll without answer fell inside one of the given intervals."""
        return all(any(a <= t < b for a, b in intervals) for t in times)

    explained = set()
    for s in tf["silent"]:
        if s in members and inside(tf["none_times"][s], off_log):
            explained.add(s)
    if explained and members and explained == {s for s in tf["silent"] if s in members} \
            and explained == set(tf["silent"]):
        b.add("MAINS_SWITCHED", "certain",
              f"every silent gear {sorted(explained)} sits on the separately switched "
              "circuit and was silent only while that circuit was off", 10)
    for ts, a, z in tests:
        if ts in tf["silent"]:
            if set(tf["silent"]) == {ts} and inside(tf["none_times"][ts], [(a, z)]):
                b.add("EMERG_TEST", "certain",
                      f"gear {ts} was silent only during the emergency test of its pair", 10)
    if len(st["exchanged"]) >= 2:
        b.add("REPLACE_TWO", "certain", f"{len(st['exchanged'])} gear exchanged at once", 10)
    budget_ok = st["i_total"] <= st["supply_guaranteed"]
    if not budget_ok:
        b.add("SUPPLY_LOW", "certain",
              f"bus devices draw {1e3 * st['i_total']:.0f} mA, the supply guarantees "
              f"{1e3 * st['supply_guaranteed']:.0f} mA", 10)
    drop = E.drop_at_max_current(st["cable_m"], st["mm2"], st["supply_max"])
    wiring_ok = drop <= C.V_DROP_MAX
    if not wiring_ok:
        b.add("FAR_END", "certain",
              f"{st['cable_m']:.0f} m of {st['mm2']} mm2 drops {drop:.1f} V at "
              f"{1e3 * st['supply_max']:.0f} mA, above the {C.V_DROP_MAX:.0f} V limit", 10)
    in_tests = {ts for ts, _, _ in tests}
    for s in silent_gone:
        if s not in members and s not in in_tests and wiring_ok and budget_ok \
                and not st["exchanged"] and len(silent_gone) == 1:
            b.add("GEAR_FAIL", "certain",
                  f"gear {s} stopped answering for good with permanent mains, no test, "
                  "wiring and supply within limits", 9)
    n_seen = len(known) + len(unknown_answering)
    count_gap = st["n_installed"] - n_seen
    if off_log and not explained:
        b.add("MAINS_SWITCHED", "possible", "a separately switched circuit was off during "
              "the window but no failure was caught", 2)
    if tests and not any(ts in tf["silent"] for ts, _, _ in tests):
        b.add("EMERG_TEST", "possible", "an emergency test ran but no failure was caught", 2)
    if count_gap > 0 and budget_ok and wiring_ok and p.get("missing_short") == "none":
        b.add("DUP_ADDR", "likely", f"{count_gap} installed luminaire(s) not visible to the "
              "gateway as own address: two gear may share one", 6)
    if (count_gap == 0 and not any_anomaly and not off_log and not tests and budget_ok
            and wiring_ok and p.get("missing_short") == "none" and not k["bus"]
            and not unknown_answering and v_idle >= C.SUPPLY_V_RANGE[0]
            and d["replace_result"] is None):
        b.add("HEALTHY", "certain", "count matches the site, every gear answers cleanly, "
              "no switching, test, wiring or supply issue", 10)
    return Report(level, b.ranked())
