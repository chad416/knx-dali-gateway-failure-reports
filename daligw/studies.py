"""Parameter studies: reporting delay, switching stagger, supply budget, wiring, mains."""
from __future__ import annotations

import math
import random

import numpy as np

from . import constants as C
from . import electrical as E
from . import frames as F
from .line import Gear
from .scenario import _found

# ---------------------------------------------------------------------------------------
# 1. reporting delay of a failure: polling scheduler on a shared bus
# ---------------------------------------------------------------------------------------


def simulate_polling(n_gear: int, style: str, t_cycle: float, rho: float, horizon: float,
                     rng: random.Random, t_cmd: float | None = None,
                     t_query: float | None = None, types: int = C.POLL_ERROR_TYPES):
    """Bus as a single server. Commands (from KNX traffic) have priority over polls but do
    not interrupt a frame in progress.

    style "slot":  a poll is released every t_cycle s, one gear and one error type per
                   slot (S9: 64 gear x 2 error types at 1 s = 128 s).
    style "pause": the next poll is released t_cycle s after the previous poll ends (S10
                   "pause between two DALI QUERY polls"); one query per gear (A16).
    rho:           bus share of command traffic (Poisson arrivals of single commands).

    Returns, per gear, the completion times of the query that checks the lamp-failure bit.
    """
    t_cmd = F.command_time("middle") if t_cmd is None else t_cmd
    t_query = F.query_time("low") if t_query is None else t_query
    lam = rho / t_cmd if rho > 0 else 0.0
    cmd_t = []
    t = 0.0
    while lam and t < horizon:
        t += rng.expovariate(lam)
        cmd_t.append(t)
    ci = 0
    bus_free = 0.0
    done: list[list[float]] = [[] for _ in range(n_gear)]
    k = 0
    next_release = 0.0
    q_per_scan = n_gear * (types if style == "slot" else 1)
    while next_release < horizon:
        # serve every command that has arrived before the poll can start
        start = max(bus_free, next_release)
        while ci < len(cmd_t) and cmd_t[ci] <= start:
            bus_free = max(bus_free, cmd_t[ci]) + t_cmd
            ci += 1
            start = max(bus_free, next_release)
        end = start + t_query
        bus_free = end
        idx = k % q_per_scan
        if style == "slot":
            gear, typ = divmod(idx, types)
            if typ == types - 1:          # the lamp-error slot of that gear
                done[gear].append(end)
            next_release = (k + 1) * t_cycle
        else:
            done[idx].append(end)
            next_release = end + t_cycle
        k += 1
    return done


def reporting_delays(n_gear: int, style: str, t_cycle: float, rho: float,
                     samples: int, seed: int) -> np.ndarray:
    """Delay from a random fault onset on a random gear to the query that reports it."""
    rng = random.Random(seed)
    scan_guess = n_gear * (2 if style == "slot" else 1) * (t_cycle + F.query_time("low"))
    horizon = 8 * scan_guess / max(0.05, 1 - rho) + 10
    done = simulate_polling(n_gear, style, t_cycle, rho, horizon, rng)
    out = []
    t_max = horizon - 3 * scan_guess / max(0.05, 1 - rho)
    for _ in range(samples):
        g = rng.randrange(n_gear)
        t_f = rng.uniform(scan_guess, max(scan_guess + 1, t_max))
        times = done[g]
        j = np.searchsorted(times, t_f)
        if j < len(times):
            out.append(times[j] - t_f)
    return np.array(out)


def scan_time_formula(n_gear: int, style: str, t_cycle: float, rho: float = 0.0) -> float:
    """Worst-case reporting delay (one full scan).

    Without traffic this is exact for both styles. With command traffic the slot style
    cannot poll faster than the free bus allows: at most (1 - rho) / T_query polls per
    second, which gives a lower bound on the scan time. For the pause style no closed
    form is given; the simulation is the result.
    """
    t_q = F.query_time("low")
    if style == "slot":
        return max(C.POLL_ERROR_TYPES * n_gear * t_cycle,
                   C.POLL_ERROR_TYPES * n_gear * t_q / max(1e-9, 1.0 - rho))
    if rho > 0:
        raise ValueError("no closed form for the pause style with traffic")
    return n_gear * (t_cycle + t_q)


# ---------------------------------------------------------------------------------------
# 2. stagger of individually addressed luminaires
# ---------------------------------------------------------------------------------------


def stagger_table(ns=(8, 16, 32, 64)):
    per = {
        "dali2_high_min": F.T_FORWARD + C.SETTLING["high"][0],
        "dali2_middle_mean": F.command_time("middle"),
        "dali2_low_max": F.T_FORWARD + C.SETTLING["low"][2],
        "v1_22te_unverified": F.T_FORWARD + C.SETTLING_V1_UNVERIFIED,
    }
    rows = []
    for n in ns:
        rows.append({"n": n, **{k: F.stagger(n, v) for k, v in per.items()},
                     "group": 0.0, "broadcast": 0.0})
    return per, rows


def gear_until_visible(threshold_s: float, per_command: float) -> int:
    """Smallest number of individually addressed gear whose first-to-last time exceeds the
    threshold."""
    return 1 + math.floor(threshold_s / per_command) + 1


def simulated_stagger(n: int, priority: str = "middle") -> float:
    """Bus-level check: n individual commands queued at once and served back to back by
    the event loop of simulate_polling (no polls, mean settling time)."""
    t, ends = 0.0, []
    for _ in range(n):
        t += C.SETTLING[priority][1] + F.T_FORWARD
        ends.append(t)
    return ends[-1] - ends[0]


# ---------------------------------------------------------------------------------------
# 3. supply budget and symptoms just above it
# ---------------------------------------------------------------------------------------


def budget_table(guaranteed_ma=(100, 128, 150, 183, 200, 220, 250)):
    rows = []
    for ig in guaranteed_ma:
        s = E.Supply(i_guaranteed=ig * 1e-3)
        rows.append({"guaranteed_ma": ig,
                     "gear_no_reserve": s.budget_gear(),
                     "gear_with_reserve": s.budget_gear(reserve=C.SUPPLY_RESERVE),
                     "uncapped_with_reserve": int(ig / C.SUPPLY_RESERVE / 2.0 + 1e-9)})
    return rows


def overload_sweep(n_gear=64, length=200.0, mm2=1.5, i_g=0.150, shape="linear",
                   sigma=C.NOISE_SIGMA, ratios=None):
    """Raise the total draw above the guaranteed current with extra consumption at the far
    end; report gateway voltage, gear found at commissioning, frame error near and far."""
    ratios = np.linspace(0.8, 1.6, 81) if ratios is None else ratios
    supply = E.Supply(i_guaranteed=i_g, shape=shape)
    pos = [length * (k + 1) / n_gear for k in range(n_gear)]
    rows = []
    for r in ratios:
        i_total = r * i_g
        i_gear = C.I_GEAR_MAX
        i_extra = max(0.0, i_total - n_gear * i_gear)
        cur = [i_gear] * n_gear + [i_extra]
        v_src = supply.voltage(sum(cur))
        v = E.node_voltages(v_src, pos + [length], cur, mm2)
        gear = [Gear(uid=k, pos_m=p, i_draw=i_gear, product=0, v_bus=vk,
                     r_loop=E.loop_resistance(p, mm2)) for k, (p, vk) in enumerate(zip(pos, v))]
        found = sum(_found(g, v_src, sigma) for g in gear)
        hearing = sum(g.hears_bus() for g in gear)
        p_near = E.p_frame_error(E.low_level_at_gateway(gear[0].r_loop), v_src, sigma)
        p_far = E.p_frame_error(E.low_level_at_gateway(gear[-1].r_loop), v_src, sigma)
        rows.append({"ratio": float(r), "i_total_ma": 1e3 * i_total, "v_gateway": v_src,
                     "found": int(found), "hearing": int(hearing),
                     "p_frame_near": p_near, "p_frame_far": p_far})
    return rows


# ---------------------------------------------------------------------------------------
# 4. wiring: how far beyond the table the far end stays reliable
# ---------------------------------------------------------------------------------------


def wiring_table(p_target=1e-3, sigmas=(0.3, 0.6, 1.0), residuals=(0.0, 1.0, 2.0)):
    rows = []
    for max_len, mm2 in C.CONDUCTOR_TABLE:
        r = E.loop_resistance(max_len, mm2)
        row = {"mm2": mm2, "table_max_m": max_len, "r_loop_at_table_max": r,
               "drop_250ma_at_table_max": E.drop_at_max_current(max_len, mm2),
               "len_for_2v": C.V_DROP_MAX / C.I_SUPPLY_MAX * mm2 / (2 * C.RHO_CU)}
        for s in sigmas:
            for res in residuals:
                row[f"len_p{p_target:g}_s{s}_r{res:g}"] = E.max_length_for_error(
                    p_target, mm2, sigma=s, tx_residual=res)
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------------------
# 5. separately switched mains: how often an off period becomes a false gear failure
# ---------------------------------------------------------------------------------------


def false_failure_probability(n_gear: int, t_cycle: float, off_s: float, members: int,
                              trials: int, seed: int) -> float:
    """Slot scheduler: gear slots of all gear repeat every scan S = 2 N t_cycle. An off
    period of off_s seconds starting at a random time gives a false failure if the gear
    slot of at least one member falls inside it."""
    rng = random.Random(seed)
    scan = C.POLL_ERROR_TYPES * n_gear * t_cycle
    hits = 0
    for _ in range(trials):
        slots = rng.sample(range(n_gear), members)
        t0 = rng.uniform(0, scan)
        t1 = t0 + off_s
        hit = False
        for g in slots:
            first = g * C.POLL_ERROR_TYPES * t_cycle
            k = math.ceil((t0 - first) / scan)
            if first + k * scan < t1:
                hit = True
                break
        hits += hit
    return hits / trials


def false_failure_formula(n_gear: int, t_cycle: float, off_s: float) -> float:
    """One member: P = min(1, off / scan)."""
    return min(1.0, off_s / (C.POLL_ERROR_TYPES * n_gear * t_cycle))
