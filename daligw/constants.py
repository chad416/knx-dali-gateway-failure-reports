"""Numeric facts of the DALI line and of the gateway behaviour.

Every value names its source id (see docs/SOURCES.md) or is marked as an assumption (A-id,
see DOSSIER.md section 7.1). IEC 62386 itself was not read; all protocol values are taken
from openly readable manufacturer documentation that restates it.
"""

from .variants import VARIANT_B as _B

# ---- physical layer -------------------------------------------------------------------
BIT_RATE = 1200.0                       # bit/s, Manchester coded            S1, S2, S3
T_BIT = 1.0 / BIT_RATE                  # 0.833 ms                            S1, S3
T_HALF = T_BIT / 2                      # 416.67 us                           S3
T_STOP = 2.45e-3                        # stop condition, at least 2.45 ms    S1 (DALI-2 framing)
FORWARD_BITS = 16                       # address byte + one data byte        S3 (16-bit forward frame)
BACKWARD_BITS = 8                       # one data byte                       S3
T_FORWARD_STATED = 16.2e-3              # 16-bit forward frame as stated      S3
T_BACKWARD_STATED = 9.95e-3             # backward frame as stated            S3

# backward frame starts 5.5 .. 10.5 ms after the end of the forward frame     S1, S3
T_FB_MIN, T_FB_MEAN, T_FB_MAX = 5.5e-3, 8.0e-3, 10.5e-3
# a master waits at least 2.4 ms after a backward frame                       S3
T_BF_TO_FF_MIN = 2.4e-3

# settling time before each forward frame, DALI-2 multi-master transmitter    S1
# (min, mean, max) in seconds, by DALI priority
SETTLING = {
    "high": (13.5e-3, 14.1e-3, 14.7e-3),
    "middle_high": (14.9e-3, 15.5e-3, 16.1e-3),
    "middle": (16.3e-3, 17.0e-3, 17.7e-3),
    "middle_low": (17.9e-3, 18.6e-3, 19.3e-3),
    "low": (19.5e-3, 20.3e-3, 21.2e-3),
}
# Version 1 single-master value: at least 22 Te = 9.17 ms between forward frames.
# NOT verified: the application note that states it could not be opened (HTTP 403);
# used only as a labelled alternative in the stagger table.
SETTLING_V1_UNVERIFIED = 22 * T_HALF    # 9.17 ms

# ---- addressing ----------------------------------------------------------------------
N_SHORT_ADDRESSES = 64                  # 6-bit short address                S2, S4, S5
N_GROUPS = 16                           # 4-bit group address                S2, S5
N_SCENES = 16                           #                                     S2, S5
MASK = 255                              # short address of a gear without one S4

# command opcodes (second byte of the forward frame)                         S6
OPC_OFF = 0x00
OPC_RECALL_MAX = 0x05
OPC_QUERY_STATUS = 0x90
OPC_QUERY_GEAR_PRESENT = 0x91
OPC_QUERY_LAMP_FAILURE = 0x92
OPC_QUERY_MISSING_SHORT = 0x96
YES = 0xFF                              # backward frame 0xFF = yes, silence = no  S3

# status byte, bit 0 = least significant                                     S4, S2
STATUS_BITS = (
    "control_gear_failure",   # bit 0
    "lamp_failure",           # bit 1
    "lamp_on",                # bit 2
    "limit_error",            # bit 3
    "fade_running",           # bit 4
    "reset_state",            # bit 5
    "missing_short_address",  # bit 6
    "power_cycle_seen",       # bit 7
)

# ---- electrical ----------------------------------------------------------------------
I_SUPPLY_MAX = 0.250                    # A, never above 250 mA on a line    S7, S8 (variant B max, S15)
I_GEAR_MAX = 2e-3                       # A, a unit draws at most 2 mA        S8
SUPPLY_RESERVE = 1.2                    # plan with guaranteed current / 1.2  S7 (attributed by S7 to IEC 62386)
V_DROP_MAX = 2.0                        # V along the wiring                  S2, S8
MAX_RUN_M = 300.0                       # m                                   S2
# minimum conductor cross-section by run length (m -> mm2)                  S2
CONDUCTOR_TABLE = ((100.0, 0.5), (150.0, 0.75), (300.0, 1.5))
SUPPLY_V_RANGE = (12.0, 20.5)           # V, supply output                    S8
GEAR_V_HIGH_MIN = 9.5                   # V, gear reads high above this       S8
GEAR_V_LOW_MAX = 6.5                    # V, gear reads low below this        S8
DEV_V_HIGH_MIN = 10.0                   # V, control device reads high        S8
DEV_V_LOW_MAX = 4.5                     # V, control device reads low         S8
RHO_CU = 1.0 / 58.0                     # ohm mm2 / m, annealed copper (textbook value, S11)

# ---- gateway -------------------------------------------------------------------------
# The simulated gateway polls like variant B, the only one of the three documented
# variants whose documents state the polling rule (daligw/variants.py). S9, a gateway of
# another manufacturer, states the same rule.
POLL_CYCLE_DEFAULT = _B.poll_default_s.value      # 1 s per gear and error type   S9, S13
POLL_ERROR_TYPES = _B.poll_error_types.value      # lamp and gear: 64 gear -> 128 s S9, S13
REPLACE_ERRORS = {7: "no faulty gear", 8: "more than one gear faulty",
                  9: "no new gear found", 10: "wrong device type",
                  11: "more than one new gear"}   # S9 section 4.1, S13 section 11.5

# ---- assumptions (DOSSIER 7.1) -------------------------------------------------------
V_SUPPLY_NOMINAL = 16.0                 # A1: inside the 12..20.5 V range of S8
NOISE_SIGMA = 0.6                       # A5: V, Gaussian noise on each half-bit sample
TX_RESIDUAL_V = 0.0                     # A4: V, residual voltage of a gear transmitter
# A8: s, gateway sets the bus failure object this long after a short begins. Variant B
# shuts its output down 0.6 s after a short (S15); that the object is sent at that moment
# is the assumption.
BUS_FAIL_DETECT_S = _B.short_shutdown_s.value
# A18: while a short lasts, variant B retries its output every short_restart_s seconds
# (S15 states one attempt 5 s after detection, not the repetition).
