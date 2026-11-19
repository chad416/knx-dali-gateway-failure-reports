"""Random virtual installation, fault injection, commissioning and the observed window.

One installation = one DALI line (8 to 64 luminaires on one cable run), one KNX/DALI
gateway with integrated supply, the KNX side. One fault (or none) is injected. The run
returns the evidence an engineer could collect at four levels (E1..E4) and the truth.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from . import constants as C
from . import electrical as E
from .line import Gear, receive, reply_offsets

FAULTS = (
    "HEALTHY",
    "MAINS_SWITCHED",   # gear mains switched separately from the DALI bus (false gear failure)
    "LAMP_FAIL",        # real lamp failure
    "GEAR_FAIL",        # real control gear failure
    "EMERG_TEST",       # emergency test disconnects the normal gear of an undeclared pair
    "DUP_ADDR",         # reused / pre-addressed gear added with an address already in use
    "NO_ADDR",          # gear added after commissioning, never searched
    "REPLACE_TWO",      # two gear exchanged at once, automatic replacement aborts
    "SUPPLY_LOW",       # gear not found at commissioning: supply cannot deliver the current
    "BUS_SHORT",        # bus short circuit or supply failure (hides other faults)
    "FAR_END",          # wiring too long / too thin: far end answers unreliably
)

T_OBS = 1800.0          # s, observed window (A13)


@dataclass
class Evidence:
    knx: list            # E1: (t, object, short address or None, value)
    diag: dict           # E2: gateway diagnostics
    trace: list          # E3: (t, short, reception kind, value, mark) of every gateway poll
    probe: dict          # E3: active probe after the window, idle voltage at the gateway
    site: dict           # E4: site facts


@dataclass
class Run:
    fault: str
    variant: str
    evidence: Evidence
    truth: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------------------
# installation
# ---------------------------------------------------------------------------------------


def _base(rng: random.Random, n: int):
    length = rng.uniform(30.0, 300.0)
    mm2 = E.required_cross_section(length)
    if rng.random() < 0.3 and mm2 < 1.5:           # some installers use a larger size
        mm2 = 1.5
    n_types = rng.randint(1, 3)
    offsets = reply_offsets(list(range(n_types)), rng)
    n_groups = rng.randint(1, min(C.N_GROUPS, max(1, n // 2)))
    gear = []
    for k in range(n):
        g = Gear(uid=k, pos_m=rng.uniform(0.05, 1.0) * length,
                 i_draw=rng.uniform(1.0e-3, C.I_GEAR_MAX), product=rng.randrange(n_types),
                 groups={rng.randrange(n_groups)}, lamp_on=rng.random() < 0.5)
        gear.append(g)
    return length, mm2, offsets, n_groups, gear


def _apply_electrics(gear, supply: E.Supply, mm2: float, i_other: float, other_pos: float):
    """Idle voltage and loop resistance at every gear; other bus devices sit at other_pos."""
    pos = [g.pos_m for g in gear] + [other_pos]
    cur = [g.i_draw for g in gear] + [i_other]
    i_total = sum(cur)
    v_src = supply.voltage(i_total)
    v = E.node_voltages(v_src, pos, cur, mm2)
    for g, vk in zip(gear, v):
        g.v_bus = vk
        g.r_loop = E.loop_resistance(g.pos_m, mm2)
    return v_src, i_total


def _found(g: Gear, v_high: float, sigma: float) -> bool:
    """Commissioning outcome of one gear (A9): found if powered, hears the bus, alive and
    its answers are read with a frame error probability below 0.5. The command sequence of
    the search is not modelled (not verified from an open source)."""
    if not g.can_answer(-1.0):
        return False
    p = E.p_frame_error(E.low_level_at_gateway(g.r_loop), v_high, sigma)
    return p < 0.5


# ---------------------------------------------------------------------------------------
# one run
# ---------------------------------------------------------------------------------------


def make_run(fault: str, seed: int, **kw) -> Run:
    """Build and observe one installation. If the fault cannot be injected into the drawn
    installation (for example SUPPLY_LOW on a short cable, where all gear would drop out
    together with the gateway), the next seed is drawn."""
    for attempt in range(50):
        run = _make_run(fault, seed + 100_003 * attempt, **kw)
        if run is not None:
            run.truth["seed"] = seed + 100_003 * attempt
            return run
    raise RuntimeError(f"could not inject {fault} from seed {seed}")


def _make_run(fault: str, seed: int, t_cycle: float = C.POLL_CYCLE_DEFAULT,
              sigma: float = C.NOISE_SIGMA, same_product_dup: float = 0.5,
              t_obs: float = T_OBS, supply_shape: str = "linear",
              dup_twin_like: bool = False) -> Run | None:
    rng = random.Random(seed)
    adds_gear = fault in ("DUP_ADDR", "NO_ADDR")
    n = rng.randint(8, 63 if adds_gear else 64)
    length, mm2, offsets, n_groups, gear = _base(rng, n)
    variant = ""
    truth: dict = {}

    # bus supply: guaranteed current sized with the planning reserve for a healthy line
    i_other = rng.choice([0.0, 0.0, rng.uniform(2e-3, 12e-3)])     # other bus devices (A14)
    need = sum(g.i_draw for g in gear) + i_other
    i_g = max(need * C.SUPPLY_RESERVE, rng.uniform(0.12, 0.22))
    i_g = min(i_g, 0.24)
    other_pos = rng.uniform(0.0, 1.0) * length

    # optional separately switched circuit and emergency pairs, present in any class
    circuit_members: list[int] = []
    if fault == "MAINS_SWITCHED" or rng.random() < 0.3:
        k = rng.randint(1, min(8, n - 1))
        circuit_members = rng.sample(range(n), k)
        for i in circuit_members:
            gear[i].circuit = 1
    pairs: list[tuple[int, int]] = []    # (normal uid, converter uid)
    if fault == "EMERG_TEST" or rng.random() < 0.3:
        free = [i for i in range(n) if i not in circuit_members]
        for _ in range(rng.randint(1, 2)):
            if len(free) < 2:
                break
            a, b = rng.sample(free, 2)
            free.remove(a)
            free.remove(b)
            gear[b].emergency_converter = True
            pairs.append((a, b))

    supply = E.Supply(i_guaranteed=i_g, shape=supply_shape)

    if fault == "FAR_END":
        # cable too long for its cross-section: far gear low level 3.4 .. 5.6 V at the gateway
        mm2 = rng.choice([0.5, 0.75])
        v_target = rng.uniform(3.4, 5.6)
        r_far = (v_target - C.TX_RESIDUAL_V) / C.I_SUPPLY_MAX
        new_len = r_far * mm2 / (2 * C.RHO_CU)
        scale = new_len / max(g.pos_m for g in gear)
        for g in gear:
            g.pos_m *= scale
        other_pos *= scale
        length = new_len
        truth["far_low_level_v"] = v_target
        variant = f"{mm2}mm2"

    if fault == "SUPPLY_LOW":
        # total draw above the guaranteed current: some gear do not see a valid idle level
        # the extra consumption sits beyond the far end (added devices, A14)
        other_pos = max(g.pos_m for g in gear)
        ok = []
        for step in range(400):
            i_extra = step * 0.5e-3
            v_src, _ = _apply_electrics(gear, supply, mm2, i_other + i_extra, other_pos)
            lost = sum(1 for g in gear if not _found(g, v_src, sigma))
            # just above the limit: the bus is still up (gear threshold 9.5 V) but at
            # least one gear is not found at commissioning
            if lost >= 1 and C.GEAR_V_HIGH_MIN + 0.1 <= v_src <= 12.5:
                ok.append(i_extra)
        if not ok:
            return None
        i_other += rng.choice(ok)
        v_src, _ = _apply_electrics(gear, supply, mm2, i_other, other_pos)
        truth["gear_not_hearing"] = sum(1 for g in gear if not g.hears_bus())
        truth["v_gateway"] = v_src

    v_src, i_total = _apply_electrics(gear, supply, mm2, i_other, other_pos)

    # ---- commissioning (before the window): found gear get short addresses -----------
    found = [g for g in gear if _found(g, v_src, sigma)]
    addresses = rng.sample(range(C.N_SHORT_ADDRESSES), len(found)) if rng.random() < 0.5 \
        else list(range(len(found)))
    rng.shuffle(found)
    for g, a in zip(found, addresses):
        g.short = a
    known = sorted(g.short for g in found)
    doc_short = {g.uid: g.short for g in gear}     # as documented at commissioning
    truth["n_unfound"] = n - len(found)

    # ---- the observed window -----------------------------------------------------------
    circuit_log: list[tuple[float, float]] = []
    tests: list[tuple[int, float, float]] = []
    exchanged: list[int] = []
    replace_at = None
    short_from = math.inf
    hidden_lamp = None
    removed: list[Gear] = []
    addressed = [g for g in gear if g.short is not None]

    if fault == "MAINS_SWITCHED":
        t = rng.uniform(0.02, 0.3) * t_obs
        for _ in range(rng.randint(1, 3)):
            d = math.exp(rng.uniform(math.log(30.0), math.log(900.0)))
            persist = rng.random() < 0.2
            end = math.inf if persist else t + d
            circuit_log.append((t, end))
            if persist or end > 0.9 * t_obs:
                break
            t = end + rng.uniform(60.0, 400.0)
            if t > 0.9 * t_obs:
                break
        variant = "stays_off" if math.isinf(circuit_log[-1][1]) else f"{len(circuit_log)}_off"
    for i in circuit_members:
        gear[i].off = list(circuit_log)

    if fault == "LAMP_FAIL":
        g = rng.choice(addressed)
        g.lamp_fail_from = rng.uniform(0.05, 0.6) * t_obs
        truth["short"] = g.short
    if fault == "GEAR_FAIL":
        g = rng.choice([x for x in addressed if x.circuit is None] or addressed)
        t_f = rng.uniform(0.05, 0.6) * t_obs
        if rng.random() < 0.6:
            g.dead_from, variant = t_f, "silent"
        else:
            g.gear_fault_from, variant = t_f, "status_bit0"
        truth["short"] = g.short
    if fault == "EMERG_TEST":
        if not pairs or gear[pairs[0][0]].short is None:
            return None
        a, _ = pairs[0]
        t0 = rng.uniform(0.05, 0.6) * t_obs
        long = rng.random() < 0.2
        d = t_obs if long else rng.uniform(30.0, 300.0)       # A15
        tests.append((a, t0, t0 + d))
        gear[a].off.append((t0, t0 + d))
        variant = "duration_test" if long else "function_test"
        truth["short"] = gear[a].short
    if fault == "DUP_ADDR":
        twin = rng.choice(addressed)
        same = rng.random() < same_product_dup
        prod = twin.product if same else (twin.product + 1) % max(2, len(offsets) + 1)
        if prod not in offsets:
            offsets.update(reply_offsets([prod], rng))
            while offsets[prod] == offsets[twin.product]:
                offsets[prod] += 3
        groups = {rng.randrange(C.N_GROUPS)}
        if dup_twin_like:
            # sensitivity: a gear of the same product, programmed into the same group
            prod, groups, same = twin.product, set(twin.groups), True
        dup = Gear(uid=n, pos_m=rng.uniform(0.05, 1.0) * length, i_draw=rng.uniform(1e-3, 2e-3),
                   product=prod, short=twin.short, groups=groups,
                   lamp_on=True, power_cycle_seen=True, present_from=0.0)
        gear.append(dup)
        doc_short[dup.uid] = None
        variant = "twin_like" if dup_twin_like else ("same_product" if same else "other_product")
        truth["short"] = twin.short
    if fault == "NO_ADDR":
        free = [a for a in range(C.N_SHORT_ADDRESSES) if a not in known]
        pre = rng.random() < 0.4
        new = Gear(uid=n, pos_m=rng.uniform(0.05, 1.0) * length, i_draw=rng.uniform(1e-3, 2e-3),
                   product=rng.randrange(len(offsets)), short=rng.choice(free) if pre else None,
                   lamp_on=True, power_cycle_seen=True, reset_state=not pre, present_from=0.0)
        gear.append(new)
        doc_short[new.uid] = None
        variant = "pre_addressed" if pre else "factory_new"
    if fault == "REPLACE_TWO":
        two = rng.sample(addressed, 2)
        for g in two:
            g.dead_from = rng.uniform(0.05, 0.3) * t_obs
        t_x = rng.uniform(0.55, 0.75) * t_obs
        for g in two:
            g.off.append((t_x, math.inf))      # removed from the line
            removed.append(g)
            new = Gear(uid=len(gear), pos_m=g.pos_m, i_draw=g.i_draw, product=g.product,
                       short=None, lamp_on=True, power_cycle_seen=True, reset_state=True,
                       present_from=t_x)
            gear.append(new)
            doc_short[new.uid] = None
            exchanged.append(g.short)
        replace_at = t_x + 60.0
        truth["shorts"] = sorted(g.short for g in two)
    if fault == "BUS_SHORT":
        short_from = rng.uniform(0.2, 0.7) * t_obs
        if rng.random() < 0.5:
            hidden_lamp = rng.choice(addressed)
            hidden_lamp.lamp_fail_from = rng.uniform(short_from, t_obs)
            variant = "with_hidden_lamp_failure"
        else:
            variant = "alone"

    # the new gear in DUP_ADDR / NO_ADDR / REPLACE_TWO sit on the same cable
    v_src, i_total = _apply_electrics(gear, supply, mm2, i_other, other_pos)

    ev = _observe(gear, offsets, known, t_cycle, t_obs, rng, sigma, v_src, short_from,
                  replace_at, n_groups)

    # ---- E4 site facts ------------------------------------------------------------------
    on_line = [g for g in gear if g not in removed]
    ev.site = {
        "luminaires": [{"doc_short": doc_short[g.uid], "pos_m": g.pos_m, "circuit": g.circuit,
                        "converter": g.emergency_converter} for g in on_line],
        "n_installed": len(on_line),
        "circuit_log": list(circuit_log),
        "circuit_members": sorted(doc_short[gear[i].uid] for i in circuit_members
                                  if doc_short[gear[i].uid] is not None),
        "pairs": [(doc_short[gear[a].uid], doc_short[gear[b].uid]) for a, b in pairs],
        "tests": [(doc_short[gear[a].uid], t0, t1) for a, t0, t1 in tests],
        "exchanged": sorted(x for x in exchanged if x is not None),
        "cable_m": max(g.pos_m for g in gear),
        "mm2": mm2,
        "supply_guaranteed": i_g,
        "supply_max": C.I_SUPPLY_MAX,
        "i_total": i_total,
    }
    truth.update({"n": n, "known": len(known), "t_cycle": t_cycle, "short_from": short_from,
                  "hidden_lamp": hidden_lamp.short if hidden_lamp else None})
    return Run(fault, variant, ev, truth)


def _observe(gear, offsets, known, t_cycle, t_obs, rng, sigma, v_src, short_from,
             replace_at, n_groups) -> Evidence:
    events = []                              # (t, order, kind, payload)
    k = 0
    while k * t_cycle < t_obs:
        events.append((k * t_cycle, 2, "poll", k))
        k += 1
    t = rng.expovariate(1 / 20.0)
    while t < t_obs:                         # KNX switching traffic (A13)
        r = rng.random()
        on = rng.random() < 0.5
        if r < 0.05:
            target = ("broadcast",)
        elif r < 0.15 and known:
            target = ("short", rng.choice(known))
        else:
            target = ("group", rng.randrange(n_groups))
        events.append((t, 1, "cmd", (target, on)))
        t += rng.expovariate(1 / 20.0)
    for g in gear:                            # mains returns: power-on state (A12)
        for a, b in g.off:
            if b < t_obs:
                events.append((b, 0, "mains_on", g))
        if 0 < g.present_from < t_obs:
            events.append((g.present_from, 0, "mains_on", g))
    if replace_at is not None:
        events.append((replace_at, 3, "replace", None))
    events.sort(key=lambda e: (e[0], e[1]))

    gear_obj = {s: 0 for s in known}
    lamp_obj = {s: 0 for s in known}
    bus_obj = 0
    knx, trace = [], []
    replace_result = None
    n_known = len(known)

    for t, _, kind, payload in events:
        bus_down = t >= short_from
        if bus_down and not bus_obj and t >= short_from + C.BUS_FAIL_DETECT_S:
            bus_obj = 1
            knx.append((short_from + C.BUS_FAIL_DETECT_S, "bus", None, 1))
        if kind == "mains_on":
            payload.power_cycle_seen = True
            payload.lamp_on = True
        elif kind == "cmd":
            if bus_down:
                continue
            target, on = payload
            for g in gear:
                if g.addressed(target) and g.powered(t) and g.hears_bus():
                    g.lamp_on = on
                    g.power_cycle_seen = False
        elif kind == "poll":
            if bus_down or not n_known:
                continue
            slot = payload
            s = known[(slot // 2) % n_known]
            slot_type = "gear" if slot % 2 == 0 else "lamp"
            ans = [(g.status(t), offsets[g.product], E.low_level_at_gateway(g.r_loop))
                   for g in gear if g.short == s and g.can_answer(t)]
            rec = receive(ans, v_src, rng, sigma)
            trace.append((t, s, rec.kind, rec.value, rec.mark))
            if slot_type == "gear":
                new = 1 if rec.kind != "ok" else (rec.value & 1)
                if new != gear_obj[s]:
                    gear_obj[s] = new
                    knx.append((t, "gear", s, new))
            elif rec.kind == "ok":
                new = (rec.value >> 1) & 1
                if new != lamp_obj[s]:
                    lamp_obj[s] = new
                    knx.append((t, "lamp", s, new))
        elif kind == "replace":
            faulty = [s for s in known if gear_obj[s]]
            new_gear = [g for g in gear if g.short is None and g.can_answer(t)]
            if not faulty:
                replace_result = 7
            elif len(faulty) > 1:
                replace_result = 8
            elif not new_gear:
                replace_result = 9
            elif len(new_gear) > 1:
                replace_result = 11
            else:
                replace_result = 0
    if short_from < t_obs and not bus_obj:
        bus_obj = 1
        knx.append((short_from + C.BUS_FAIL_DETECT_S, "bus", None, 1))

    diag = {"known": list(known), "bus_state": "fail" if bus_obj else "ok",
            "replace_result": replace_result,
            "gear_error": {s: gear_obj[s] for s in known},
            "lamp_error": {s: lamp_obj[s] for s in known}}

    # ---- active probe after the window (E3) -------------------------------------------
    t_p = t_obs
    probe: dict = {"status": {}, "v_idle": 0.0 if t_p >= short_from else v_src}
    if t_p < short_from:
        for s in range(C.N_SHORT_ADDRESSES):
            ans = [(g.status(t_p), offsets[g.product], E.low_level_at_gateway(g.r_loop))
                   for g in gear if g.short == s and g.can_answer(t_p)]
            rec = receive(ans, v_src, rng, sigma)
            probe["status"][s] = (rec.kind, rec.value, rec.mark)
        ans = [(C.YES, offsets[g.product], E.low_level_at_gateway(g.r_loop))
               for g in gear if g.short is None and g.can_answer(t_p)]
        rec = receive(ans, v_src, rng, sigma)
        probe["missing_short"] = rec.kind
        probe["missing_short_mark"] = rec.mark
    else:
        probe["missing_short"] = "none"
        probe["missing_short_mark"] = ""
    return Evidence(knx=knx, diag=diag, trace=trace, probe=probe, site={})
