"""DALI frame timing, Manchester coding, wired-AND superposition and status byte.

Frames are modelled at half-bit resolution. The bus is idle high; a transmitter pulls it
low. Two transmitters at once therefore give the logical AND of their levels (low wins).
That is assumption A3 in the dossier: the sources state the voltage levels and the
current limit (S8), not the superposition itself.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import constants as C

# ---------------------------------------------------------------------------------------
# timing arithmetic
# ---------------------------------------------------------------------------------------


def frame_duration(n_data_bits: int, t_stop: float = C.T_STOP) -> float:
    """Start bit + data bits + stop condition, in seconds."""
    return (1 + n_data_bits) * C.T_BIT + t_stop


T_FORWARD = frame_duration(C.FORWARD_BITS)     # 16.62 ms
T_BACKWARD = frame_duration(C.BACKWARD_BITS)   # 9.95 ms


def command_time(priority: str = "middle", which: int = 1) -> float:
    """Bus time of one command without answer: settling before it + the forward frame.

    which: 0 = minimum, 1 = mean, 2 = maximum settling time of that priority (S1).
    """
    return C.SETTLING[priority][which] + T_FORWARD


def query_time(priority: str = "low", which: int = 1, t_fb: float = C.T_FB_MEAN) -> float:
    """Bus time of one query with answer: settling, forward frame, wait, backward frame."""
    return C.SETTLING[priority][which] + T_FORWARD + t_fb + T_BACKWARD


def query_time_no_answer(priority: str = "low", which: int = 1) -> float:
    """A query that gets no answer occupies the bus until the window has closed."""
    return C.SETTLING[priority][which] + T_FORWARD + C.T_FB_MAX


def stagger(n_gear: int, per_command: float) -> float:
    """Time from the end of the first to the end of the last of n individual commands."""
    return max(0, n_gear - 1) * per_command


# ---------------------------------------------------------------------------------------
# Manchester coding at half-bit level. Level 1 = high (idle), 0 = low (pulled).
# Polarity: bit 1 -> (low, high). The decision rules below do not depend on it
# (tests run both polarities).
# ---------------------------------------------------------------------------------------

STOP_HALF_BITS = int(round(C.T_STOP / C.T_HALF + 0.5))   # 6 half-bits >= 2.45 ms


def manchester(bits: list[int], one_low_first: bool = True) -> list[int]:
    out = []
    for b in bits:
        first = 0 if (b == 1) == one_low_first else 1
        out += [first, 1 - first]
    return out


def byte_bits(value: int, n: int = 8) -> list[int]:
    """MSB first (S3)."""
    return [(value >> (n - 1 - i)) & 1 for i in range(n)]


def backward_waveform(value: int, one_low_first: bool = True) -> list[int]:
    """Half-bit levels of a backward frame: start bit 1, 8 data bits, stop (high)."""
    return manchester([1] + byte_bits(value), one_low_first) + [1] * STOP_HALF_BITS


SUB = 8   # samples per half-bit for the superposition with time offset


def superpose(frames: list[tuple[list[int], int]]) -> list[int]:
    """Wired-AND of several waveforms, each (half-bit levels, offset in 1/SUB half-bits).

    Returns a sampled waveform at SUB samples per half-bit, starting at the earliest
    start. Idle (high) outside each frame.
    """
    if not frames:
        return []
    t0 = min(off for _, off in frames)
    length = max(off - t0 + SUB * len(w) for w, off in frames)
    bus = [1] * length
    for w, off in frames:
        s = off - t0
        for i, lvl in enumerate(w):
            if lvl == 0:
                for k in range(s + i * SUB, s + (i + 1) * SUB):
                    bus[k] = 0
    return bus


@dataclass
class Reception:
    """What the gateway's receiver makes of the bus during the backward-frame window."""
    kind: str                 # "none", "ok", "corrupt"
    value: int | None = None
    extra_low: int = 0        # half-bits low where a valid frame must be high
    weak: int = 0             # half-bits where a level did not reach its threshold

    @property
    def mark(self) -> str:
        """extra_low = a second transmitter (collision); weak = a level that did not reach its threshold."""
        if self.kind != "corrupt":
            return ""
        if self.extra_low and not self.weak:
            return "extra_low"
        if self.weak and not self.extra_low:
            return "weak"
        return "mixed"


def classify_levels(samples: list[str]) -> Reception:
    """Decode half-bit classes 'L', 'H', 'X' (undefined) aligned to the first start edge.

    samples[0] is the first half of the start bit. A valid frame has complementary halves
    in each of the 9 bits and only H in the stop condition.
    """
    if not samples or all(s == "H" for s in samples):
        return Reception("none")
    n_bits = 1 + C.BACKWARD_BITS
    need = 2 * n_bits + STOP_HALF_BITS
    samples = samples + ["H"] * (need - len(samples))
    extra = missing = 0
    bits = []
    for i in range(n_bits):
        a, b = samples[2 * i], samples[2 * i + 1]
        if {a, b} == {"L", "H"}:
            bits.append((a, b))
        elif a == "L" and b == "L":
            extra += 1
            bits.append(None)
        else:   # HH, or any undefined level: a low that did not arrive
            missing += 1
            bits.append(None)
    for s in samples[2 * n_bits: need]:
        if s == "L":
            extra += 1
        elif s == "X":
            missing += 1
    if extra or missing:
        return Reception("corrupt", None, extra, missing)
    start = bits[0]
    # the start bit is a 1: its half order fixes the polarity
    one = start
    value = 0
    for pair in bits[1:]:
        value = (value << 1) | (1 if pair == one else 0)
    return Reception("ok", value)


def receive_clean(frames: list[tuple[list[int], int]]) -> Reception:
    """Noise-free reception of superposed waveforms (logic levels only).

    The receiver samples the middle of each half-bit on the bit grid of the earliest
    frame (assumption A11).
    """
    bus = superpose(frames)
    idx = range(SUB // 2, len(bus), SUB)
    return classify_levels(["L" if bus[i] == 0 else "H" for i in idx])


# ---------------------------------------------------------------------------------------
# status byte
# ---------------------------------------------------------------------------------------


def encode_status(**flags: bool) -> int:
    value = 0
    for bit, name in enumerate(C.STATUS_BITS):
        if flags.get(name, False):
            value |= 1 << bit
    unknown = set(flags) - set(C.STATUS_BITS)
    if unknown:
        raise KeyError(f"unknown status flags: {sorted(unknown)}")
    return value


def decode_status(value: int) -> dict[str, bool]:
    if not 0 <= value <= 255:
        raise ValueError("status byte out of range")
    return {name: bool(value >> bit & 1) for bit, name in enumerate(C.STATUS_BITS)}
