"""
Heart-rate packet parsing and "is the strap actually on the body?" detection.

Why this exists: the Garmin HRM-Dual does not fill in the standard sensor-contact bits.
When it loses skin contact it keeps sending packets, repeating the last heart rate (or a
drifting, made-up one while it is handled), so the BLE link alone cannot tell us anything.

What does tell us: RR intervals (the time between two heartbeats). On the body the strap
reports plausible, steady RR intervals. Off the body it reports none, or noise (values far
too short or jumping wildly from one to the next). So we call the strap "in contact" only
while it keeps producing a short run of plausible, consistent RR intervals.

Straps that never report RR intervals are trusted as-is, and straps that do support the
contact bits are honoured when they report "no contact".
"""

import struct
import time
from collections import deque
from dataclasses import dataclass
from itertools import pairwise

RR_MIN_MS = 270  # ~220 bpm; anything shorter is noise
RR_MAX_MS = 2000  # 30 bpm; anything longer is a gap or noise
RR_MAX_STEP = 0.30  # consecutive beats may differ by at most 30 %
RR_RUN = 3  # this many consecutive good beats prove contact...
RR_RUN_MAX_AGE_S = 5.0  # ...if they all arrived within this window
CONTACT_HOLD_S = 3.0  # keep "in contact" this long after the last proof (absorbs odd beats)

CONTACT_UNSUPPORTED = (0, 1)
CONTACT_NOT_DETECTED = 2
CONTACT_DETECTED = 3


@dataclass(frozen=True)
class HrPacket:
    bpm: int
    contact_status: int  # flags bits 1-2, see CONTACT_* constants
    rr_ms: tuple[float, ...]  # RR intervals in milliseconds, possibly empty


def parse_hr_measurement(data: bytes) -> HrPacket:
    """Decode a Heart Rate Measurement (0x2A37) notification. All fields are little-endian."""
    flags = data[0]
    i = 1
    if flags & 0x01:  # bit0: 16-bit heart rate
        bpm = struct.unpack_from("<H", data, i)[0]
        i += 2
    else:
        bpm = data[i]
        i += 1
    if flags & 0x08:  # bit3: energy expended present (uint16), skip it
        i += 2
    rr: list[float] = []
    if flags & 0x10:  # bit4: RR intervals, uint16 each, in units of 1/1024 s
        while i + 1 < len(data):
            rr.append(struct.unpack_from("<H", data, i)[0] * 1000 / 1024)
            i += 2
    return HrPacket(bpm=bpm, contact_status=(flags >> 1) & 0b11, rr_ms=tuple(rr))


class ContactDetector:
    """Feed every packet to update(); it returns whether the strap is on the body."""

    def __init__(self) -> None:
        self._recent: deque[tuple[float, float]] = deque(maxlen=RR_RUN)  # (time, rr_ms)
        self._last_proof: float | None = None
        self.rr_supported = False  # becomes True once the strap sends any RR interval

    def update(self, packet: HrPacket, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        if packet.contact_status == CONTACT_NOT_DETECTED:
            self._last_proof = None
            self._recent.clear()
            return False
        for rr in packet.rr_ms:
            self.rr_supported = True
            self._recent.append((now, rr))
            if self._run_is_good(now):
                self._last_proof = now
        if not self.rr_supported:
            return True  # nothing better to go on: trust the strap
        return self._last_proof is not None and now - self._last_proof <= CONTACT_HOLD_S

    def _run_is_good(self, now: float) -> bool:
        if len(self._recent) < RR_RUN or now - self._recent[0][0] > RR_RUN_MAX_AGE_S:
            return False
        values = [rr for _, rr in self._recent]
        if not all(RR_MIN_MS <= rr <= RR_MAX_MS for rr in values):
            return False
        return all(abs(b - a) <= RR_MAX_STEP * a for a, b in pairwise(values))
