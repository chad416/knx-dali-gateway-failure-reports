"""Wiring resistance, bus supply, voltage along the line, and the reception error model.

The supply and the gateway receiver sit at the near end of the line (integrated supply,
S5, S9). Gear are constant-current loads along one cable run (daisy chain).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import constants as C

# ---------------------------------------------------------------------------------------
# cable
# ---------------------------------------------------------------------------------------


def loop_resistance(length_m: float, cross_section_mm2: float, rho: float = C.RHO_CU) -> float:
    """Resistance of the two DALI wires (out and back) over length_m."""
    return 2.0 * length_m * rho / cross_section_mm2


def required_cross_section(length_m: float) -> float | None:
    """Minimum conductor size from the table of S2; None above 300 m (not recommended)."""
    for max_len, mm2 in C.CONDUCTOR_TABLE:
        if length_m <= max_len:
            return mm2
    return None


def drop_at_max_current(length_m: float, mm2: float, i_max: float = C.I_SUPPLY_MAX) -> float:
    """Voltage across the wiring when a far gear pulls the bus low and the supply limits at i_max."""
    return i_max * loop_resistance(length_m, mm2)


# ---------------------------------------------------------------------------------------
# supply
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Supply:
    i_guaranteed: float                  # A
    i_max: float = C.I_SUPPLY_MAX        # A
    v_nominal: float = C.V_SUPPLY_NOMINAL
    shape: str = "linear"                # A6: "linear" sag above i_guaranteed, or "hard" limit at i_max

    def voltage(self, i_load: float) -> float:
        """Output voltage at a steady load current (assumption A6 above the guaranteed current)."""
        if i_load <= self.i_guaranteed:
            return self.v_nominal
        if self.shape == "hard":
            return self.v_nominal if i_load < self.i_max else 0.0
        if i_load >= self.i_max:
            return 0.0
        return self.v_nominal * (self.i_max - i_load) / (self.i_max - self.i_guaranteed)

    def budget_gear(self, i_gear: float = C.I_GEAR_MAX, reserve: float = 1.0,
                    i_other: float = 0.0) -> int:
        """How many gear of i_gear each the supply carries, capped at 64 short addresses."""
        n = int(math.floor((self.i_guaranteed / reserve - i_other) / i_gear + 1e-9))
        return max(0, min(C.N_SHORT_ADDRESSES, n))


def node_voltages(v_source: float, positions_m: list[float], currents_a: list[float],
                  mm2: float) -> list[float]:
    """Idle-bus voltage at each load on one cable run fed from position 0.

    positions_m and currents_a are per load. The current through a cable segment is the
    sum of all loads beyond it; the drop counts both wires.
    """
    order = sorted(range(len(positions_m)), key=lambda k: positions_m[k])
    v = [0.0] * len(positions_m)
    remaining = sum(currents_a)
    x_prev, v_prev = 0.0, v_source
    for k in order:
        seg = positions_m[k] - x_prev
        v_prev = v_prev - remaining * loop_resistance(seg, mm2)
        v[k] = v_prev
        remaining -= currents_a[k]
        x_prev = positions_m[k]
    return v


# ---------------------------------------------------------------------------------------
# reception error model (assumptions A4, A5)
# ---------------------------------------------------------------------------------------


def low_level_at_gateway(r_loop: float, i_max: float = C.I_SUPPLY_MAX,
                         tx_residual: float = C.TX_RESIDUAL_V) -> float:
    """Voltage the gateway sees while a gear at loop resistance r_loop pulls the bus low."""
    return tx_residual + i_max * r_loop


def _q(x: float) -> float:
    return 0.5 * math.erfc(x / math.sqrt(2.0))


def p_half_bit_classes(v: float, sigma: float = C.NOISE_SIGMA) -> tuple[float, float, float]:
    """Probabilities that a sample of true level v is read as L, X (undefined) or H."""
    if sigma <= 0:
        if v <= C.DEV_V_LOW_MAX:
            return 1.0, 0.0, 0.0
        if v >= C.DEV_V_HIGH_MIN:
            return 0.0, 0.0, 1.0
        return 0.0, 1.0, 0.0
    p_l = 1.0 - _q((C.DEV_V_LOW_MAX - v) / sigma)
    p_h = _q((C.DEV_V_HIGH_MIN - v) / sigma)
    return p_l, max(0.0, 1.0 - p_l - p_h), p_h


def p_frame_error(v_low: float, v_high: float, sigma: float = C.NOISE_SIGMA) -> float:
    """Probability that a backward frame from one gear is not read cleanly.

    A backward frame has 9 low half-bits and 9 + 6 high half-bits (start, 8 data, stop).
    """
    p_low_ok = p_half_bit_classes(v_low, sigma)[0]
    p_high_ok = p_half_bit_classes(v_high, sigma)[2]
    return 1.0 - p_low_ok ** 9 * p_high_ok ** 15


def max_length_for_error(p_target: float, mm2: float, sigma: float = C.NOISE_SIGMA,
                         tx_residual: float = C.TX_RESIDUAL_V,
                         i_max: float = C.I_SUPPLY_MAX,
                         v_high: float = C.V_SUPPLY_NOMINAL) -> float:
    """Longest run (m) at which the far gear's frame error probability stays below p_target."""
    lo, hi = 0.0, 5000.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        r = loop_resistance(mid, mm2)
        if p_frame_error(low_level_at_gateway(r, i_max, tx_residual), v_high, sigma) < p_target:
            lo = mid
        else:
            hi = mid
    return lo
