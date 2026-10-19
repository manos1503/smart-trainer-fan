from pathlib import Path

import pytest

from hr_contact import (
    CONTACT_DETECTED,
    CONTACT_NOT_DETECTED,
    ContactDetector,
    HrPacket,
    parse_hr_measurement,
)

DATA = Path(__file__).parent / "data"


def load_log(name: str) -> list[tuple[float, bytes]]:
    rows = []
    for line in (DATA / name).read_text().splitlines():
        if not line or line.startswith("#") or line.startswith("t_s"):
            continue
        t, hex_ = line.split(",")
        rows.append((float(t), bytes.fromhex(hex_)))
    return rows


def contact_timeline(rows: list[tuple[float, bytes]]) -> list[tuple[float, bool]]:
    detector = ContactDetector()
    return [(t, detector.update(parse_hr_measurement(data), now=t)) for t, data in rows]


def state_at(timeline: list[tuple[float, bool]], t: float) -> bool:
    """Contact state reported by the last packet at or before t."""
    return [state for time, state in timeline if time <= t][-1]


# --- parsing ---------------------------------------------------------------------------


def test_parse_uint8_hr_without_rr():
    p = parse_hr_measurement(bytes.fromhex("0043"))
    assert p == HrPacket(bpm=67, contact_status=0, rr_ms=())


def test_parse_rr_intervals_in_milliseconds():
    p = parse_hr_measurement(bytes.fromhex("103df204ab01"))
    assert p.bpm == 61
    assert p.rr_ms == pytest.approx((1236.3, 417.0), abs=0.1)


def test_parse_uint16_hr_and_skips_energy_expended():
    # flags 0x19: 16-bit HR, energy expended present, RR present
    p = parse_hr_measurement(bytes.fromhex("19b40034120004"))
    assert p.bpm == 180
    assert p.rr_ms == (1000.0,)


def test_parse_contact_bits():
    assert parse_hr_measurement(bytes.fromhex("0650")).contact_status == CONTACT_DETECTED
    assert parse_hr_measurement(bytes.fromhex("0450")).contact_status == CONTACT_NOT_DETECTED


# --- contact detection on a real HRM-Dual recording ------------------------------------


@pytest.fixture(scope="module")
def timeline():
    return contact_timeline(load_log("hrm_dual_on_off.csv"))


@pytest.mark.parametrize("t", [12, 16])
def test_worn_is_contact(timeline, t):
    assert state_at(timeline, t) is True


@pytest.mark.parametrize("t", [25, 30, 36])
def test_on_table_noise_is_no_contact(timeline, t):
    assert state_at(timeline, t) is False


@pytest.mark.parametrize("t", [40, 50])
def test_module_unclipped_is_no_contact(timeline, t):
    assert state_at(timeline, t) is False


@pytest.mark.parametrize("t", [57, 64, 68])
def test_clipped_but_not_worn_is_no_contact(timeline, t):
    assert state_at(timeline, t) is False


def test_worn_again_is_contact(timeline):
    assert state_at(timeline, 82) is True


# --- other straps ------------------------------------------------------------------------


def test_strap_without_rr_is_trusted():
    detector = ContactDetector()
    assert all(detector.update(HrPacket(70, 0, ()), now=t) for t in range(10))


def test_contact_bit_no_contact_wins():
    detector = ContactDetector()
    packet = HrPacket(70, CONTACT_NOT_DETECTED, (850.0,))
    assert detector.update(packet, now=0) is False


def test_single_odd_beat_does_not_drop_contact():
    detector = ContactDetector()
    beats = [800, 810, 790, 805, 400, 800, 795, 810]  # one ectopic beat in the middle
    states = [detector.update(HrPacket(75, 0, (rr,)), now=i * 0.8) for i, rr in enumerate(beats)]
    assert states[3:] == [True] * 5
