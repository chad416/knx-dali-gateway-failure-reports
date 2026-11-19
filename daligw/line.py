"""Control gear and the DALI line: who answers a query, and what the gateway receives."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import constants as C
from . import electrical as E
from . import frames as F


@dataclass
class Gear:
    uid: int
    pos_m: float
    i_draw: float                      # A
    product: int                       # product type: fixes the reply delay (A7)
    short: int | None = None           # None = no short address (reads MASK)
    groups: set[int] = field(default_factory=set)
    circuit: int | None = None         # separately switched mains circuit, None = permanent
    off: list[tuple[float, float]] = field(default_factory=list)   # mains off intervals
    dead_from: float = float("inf")    # gear electronics dead (never answers) from this time
    gear_fault_from: float = float("inf")   # answers with status bit 0 from this time
    lamp_fail_from: float = float("inf")    # answers with status bit 1 from this time
    lamp_on: bool = False
    power_cycle_seen: bool = False     # status bit 7 (A10: cleared by any switching command)
    reset_state: bool = False          # status bit 5
    v_bus: float = C.V_SUPPLY_NOMINAL  # idle bus voltage at the gear terminals
    r_loop: float = 0.0                # loop resistance gateway -> gear
    present_from: float = float("-inf")  # installed (powered first) at this time
    emergency_converter: bool = False

    def powered(self, t: float) -> bool:
        if t < self.present_from:
            return False
        return not any(a <= t < b for a, b in self.off)

    def hears_bus(self) -> bool:
        return self.v_bus >= C.GEAR_V_HIGH_MIN

    def can_answer(self, t: float) -> bool:
        return self.powered(t) and self.hears_bus() and t < self.dead_from

    def status(self, t: float) -> int:
        return F.encode_status(
            control_gear_failure=t >= self.gear_fault_from,
            lamp_failure=t >= self.lamp_fail_from,
            lamp_on=self.lamp_on and t < self.lamp_fail_from,
            reset_state=self.reset_state,
            missing_short_address=self.short is None,
            power_cycle_seen=self.power_cycle_seen,
        )

    def addressed(self, target: tuple) -> bool:
        kind = target[0]
        if kind == "broadcast":
            return True
        if kind == "short":
            return self.short == target[1]
        if kind == "group":
            return target[1] in self.groups
        if kind == "unaddressed":         # broadcast to gear without short address
            return self.short is None
        raise ValueError(kind)


def reply_offsets(products: list[int], rng: random.Random) -> dict[int, int]:
    """Reply delay of each product type in 1/SUB half-bits, uniform in 5.5..10.5 ms (A7)."""
    unit = F.C.T_HALF / F.SUB
    return {p: int(round(rng.uniform(C.T_FB_MIN, C.T_FB_MAX) / unit)) for p in products}


def receive(answers: list[tuple[int, int, float]], v_high: float, rng: random.Random,
            sigma: float = C.NOISE_SIGMA, one_low_first: bool = True) -> F.Reception:
    """Reception of one or more backward frames.

    answers: (status value, offset in 1/SUB half-bits, low level at the gateway in V).
    Noise is added per half-bit sample (A5). Undefined levels (between 4.5 V and 10 V)
    count as 'X'.
    """
    if not answers:
        return F.Reception("none")
    if len(answers) == 1:
        value, _, v_low = answers[0]
        if E.p_frame_error(v_low, v_high, sigma) < 1e-12:
            return F.Reception("ok", value)
    waves = [(F.backward_waveform(v, one_low_first), off) for v, off, _ in answers]
    t0 = min(off for _, off in waves)
    length = max(off - t0 + F.SUB * len(w) for w, off in waves)
    level = [v_high] * length
    for (w, off), (_, _, v_low) in zip(waves, answers):
        s = off - t0
        for i, lvl in enumerate(w):
            if lvl == 0:
                for k in range(s + i * F.SUB, s + (i + 1) * F.SUB):
                    if v_low < level[k]:
                        level[k] = v_low
    # A11: the receiver locks to the bit grid of the earliest frame
    classes = []
    for k in range(F.SUB // 2, length, F.SUB):
        v = level[k] + (rng.gauss(0.0, sigma) if sigma > 0 else 0.0)
        classes.append("L" if v <= C.DEV_V_LOW_MAX else ("H" if v >= C.DEV_V_HIGH_MIN else "X"))
    return F.classify_levels(classes)
