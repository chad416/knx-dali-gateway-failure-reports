"""Frame timing arithmetic, Manchester coding, status byte, duplicate-address collision."""
import pytest

from daligw import constants as C
from daligw import frames as F


def test_bit_time_and_half_bit():
    assert C.T_BIT == pytest.approx(0.8333e-3, rel=1e-4)
    assert C.T_HALF == pytest.approx(416.67e-6, rel=1e-4)


def test_backward_frame_matches_stated_9_95_ms():
    # 1 start + 8 data bits at 0.833 ms + 2.45 ms stop = 9.95 ms (S3)
    assert F.T_BACKWARD == pytest.approx(9.95e-3, abs=0.01e-3)


def test_forward_frame_against_stated_value():
    # 1 + 16 bits + 2.45 ms = 16.62 ms; S3 states 16.2 ms. The model keeps the derivation
    # from the verified bit time and stop condition; the difference is under 3 %.
    assert F.T_FORWARD == pytest.approx(16.617e-3, abs=0.01e-3)
    assert abs(F.T_FORWARD - C.T_FORWARD_STATED) / C.T_FORWARD_STATED < 0.03


def test_command_and_query_times():
    assert F.command_time("middle") == pytest.approx(17.0e-3 + F.T_FORWARD)
    assert F.command_time("high", 0) == pytest.approx(13.5e-3 + F.T_FORWARD)
    assert F.query_time("low") == pytest.approx(20.3e-3 + F.T_FORWARD + 8.0e-3 + F.T_BACKWARD)
    # the backward-frame window closes 10.5 ms after the forward frame
    assert F.query_time_no_answer("low") == pytest.approx(20.3e-3 + F.T_FORWARD + 10.5e-3)


def test_settling_times_increase_with_lower_priority():
    order = ["high", "middle_high", "middle", "middle_low", "low"]
    mins = [C.SETTLING[p][0] for p in order]
    assert mins == sorted(mins)
    for p in order:
        lo, mean, hi = C.SETTLING[p]
        assert lo < mean < hi


def test_stagger_64_individual_commands():
    per = F.command_time("middle")
    assert F.stagger(64, per) == pytest.approx(63 * per)
    assert 2.0 < F.stagger(64, per) < 2.2
    assert F.stagger(1, per) == 0.0


def test_manchester_halves_are_complementary():
    for one_low_first in (True, False):
        w = F.manchester([1, 0, 1, 1], one_low_first)
        assert len(w) == 8
        for i in range(0, 8, 2):
            assert w[i] != w[i + 1]


def test_backward_waveform_length():
    w = F.backward_waveform(0xA5)
    assert len(w) == 18 + F.STOP_HALF_BITS
    assert F.STOP_HALF_BITS * C.T_HALF >= C.T_STOP
    assert all(x == 1 for x in w[18:])


@pytest.mark.parametrize("value", [0x00, 0x01, 0x02, 0x04, 0x5A, 0x80, 0xFF])
@pytest.mark.parametrize("pol", [True, False])
def test_single_frame_roundtrip(value, pol):
    rec = F.receive_clean([(F.backward_waveform(value, pol), 0)])
    assert rec.kind == "ok" and rec.value == value


def test_no_answer_is_none():
    assert F.receive_clean([]).kind == "none"


@pytest.mark.parametrize("pol", [True, False])
def test_two_equal_aligned_answers_look_like_one(pol):
    w = F.backward_waveform(0x04, pol)
    rec = F.receive_clean([(w, 0), (w, 0)])
    assert rec.kind == "ok" and rec.value == 0x04


@pytest.mark.parametrize("pol", [True, False])
@pytest.mark.parametrize("a,b", [(0x04, 0x00), (0x84, 0x04), (0x00, 0xFF), (0x02, 0x03)])
def test_two_different_answers_collide_with_extra_low(pol, a, b):
    rec = F.receive_clean([(F.backward_waveform(a, pol), 0), (F.backward_waveform(b, pol), 0)])
    assert rec.kind == "corrupt"
    assert rec.mark == "extra_low"


def test_equal_answers_offset_less_than_half_a_half_bit_read_as_one():
    # the receiver samples the middle of each half-bit: a shift of 3/8 half-bit is not seen
    w = F.backward_waveform(0x04)
    rec = F.receive_clean([(w, 0), (w, 3)])
    assert rec.kind == "ok" and rec.value == 0x04


@pytest.mark.parametrize("offset", [5, 8, 13, 40, 77])
def test_equal_answers_with_offset_collide_with_extra_low(offset):
    w = F.backward_waveform(0x04)
    rec = F.receive_clean([(w, 0), (w, offset)])
    assert rec.kind == "corrupt" and rec.extra_low > 0 and rec.weak == 0


def test_collision_never_produces_a_weak_mark():
    # wired-AND can only add lows; a weak (missing) low needs a level problem
    import itertools
    for a, b in itertools.product([0x00, 0x13, 0x84, 0xFF], repeat=2):
        for off in (0, 4, 9):
            rec = F.receive_clean([(F.backward_waveform(a), 0), (F.backward_waveform(b), off)])
            assert rec.weak == 0


def test_status_byte_bits():
    assert F.encode_status(control_gear_failure=True) == 0x01
    assert F.encode_status(lamp_failure=True) == 0x02
    assert F.encode_status(lamp_on=True) == 0x04
    assert F.encode_status(limit_error=True) == 0x08
    assert F.encode_status(fade_running=True) == 0x10
    assert F.encode_status(reset_state=True) == 0x20
    assert F.encode_status(missing_short_address=True) == 0x40
    assert F.encode_status(power_cycle_seen=True) == 0x80


def test_status_decode_roundtrip():
    for v in range(256):
        assert F.encode_status(**F.decode_status(v)) == v
    d = F.decode_status(0x86)
    assert d["power_cycle_seen"] and d["lamp_failure"] and d["lamp_on"]
    assert not d["control_gear_failure"]


def test_status_rejects_bad_input():
    with pytest.raises(ValueError):
        F.decode_status(256)
    with pytest.raises(KeyError):
        F.encode_status(lamp_broken=True)
