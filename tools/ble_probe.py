"""
BLE probe: reads live power from a smart trainer (Cycling Power Service) and heart
rate from a strap (Heart Rate Service) over Bluetooth LE, from a computer.

Goal: prove that a second client (later: the ESP32) can read both sensors at the
same time as Zwift, and check the BLE payload format before writing firmware.

Usage (from tools/):
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python ble_probe.py
"""

import asyncio
import struct
import time
from collections import deque

from bleak import BleakClient, BleakScanner

# Standard Bluetooth SIG UUIDs
CPS_SERVICE = "00001818-0000-1000-8000-00805f9b34fb"  # Cycling Power Service
CPS_MEASUREMENT = "00002a63-0000-1000-8000-00805f9b34fb"  # Cycling Power Measurement
HR_SERVICE = "0000180d-0000-1000-8000-00805f9b34fb"  # Heart Rate Service
HR_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"  # Heart Rate Measurement

POWER_WINDOW_S = 3.0  # rolling average window, like "3s power"

power_samples: deque[tuple[float, int]] = deque()
latest_hr: int | None = None


def on_power(_sender, data: bytearray) -> None:
    # Layout: uint16 flags (LE), sint16 instantaneous power in watts (LE), optional fields after
    _flags, watts = struct.unpack_from("<Hh", data, 0)
    now = time.monotonic()
    power_samples.append((now, watts))
    while power_samples and now - power_samples[0][0] > POWER_WINDOW_S:
        power_samples.popleft()


def on_hr(_sender, data: bytearray) -> None:
    # Layout: uint8 flags; bit0 = 0 -> HR is uint8, 1 -> HR is uint16 (LE)
    global latest_hr
    flags = data[0]
    latest_hr = struct.unpack_from("<H", data, 1)[0] if flags & 0x01 else data[1]


def avg_power() -> float | None:
    if not power_samples:
        return None
    return sum(w for _, w in power_samples) / len(power_samples)


async def stream(device, char_uuid: str, handler, label: str) -> None:
    try:
        async with BleakClient(device) as client:
            await client.start_notify(char_uuid, handler)
            print(f"[OK] Connected to {label}: {device.name}")
            while client.is_connected:
                await asyncio.sleep(1)
            print(f"[!!] {label} disconnected")
    except Exception as exc:  # keep the other sensor running if one fails
        print(f"[!!] {label} error: {exc}")


async def printer() -> None:
    while True:
        await asyncio.sleep(1)
        p = avg_power()
        p_txt = f"{p:4.0f} W" if p is not None else "  -- W"
        hr_txt = f"{latest_hr:3d} bpm" if latest_hr is not None else " -- bpm"
        print(f"power(3s): {p_txt} | HR: {hr_txt}")


async def main() -> None:
    print("Scanning for 8 s (pedal a bit so the KICKR wakes up, wear the HR strap)...")
    found = await BleakScanner.discover(timeout=8.0, return_adv=True)

    trainer = hrm = None
    for device, adv in found.values():
        uuids = [u.lower() for u in adv.service_uuids]
        if trainer is None and CPS_SERVICE in uuids:
            trainer = device
        if hrm is None and HR_SERVICE in uuids:
            hrm = device

    print(f"Trainer: {trainer.name if trainer else 'NOT FOUND'}")
    print(f"HR strap: {hrm.name if hrm else 'NOT FOUND'}")
    if not trainer and not hrm:
        return

    tasks = [asyncio.create_task(printer())]
    if trainer:
        tasks.append(asyncio.create_task(stream(trainer, CPS_MEASUREMENT, on_power, "trainer")))
    if hrm:
        tasks.append(asyncio.create_task(stream(hrm, HR_MEASUREMENT, on_hr, "HR strap")))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
