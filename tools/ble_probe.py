"""
BLE probe: reads live power from a smart trainer (Cycling Power Service) and heart
rate from a strap (Heart Rate Service) over Bluetooth LE, from a computer.

Goal: prove that a second client (later: the ESP32) can read both sensors at the
same time as Zwift, and check the BLE payload format before writing firmware.

Usage (from tools/):
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python ble_probe.py                      # live view only
    python ble_probe.py --csv recordings/ride.csv   # live view + 1 Hz recording
"""

import argparse
import asyncio
import csv
import signal
import struct
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from bleak import BleakClient, BleakScanner

# Standard Bluetooth SIG UUIDs
CPS_SERVICE = "00001818-0000-1000-8000-00805f9b34fb"  # Cycling Power Service
CPS_MEASUREMENT = "00002a63-0000-1000-8000-00805f9b34fb"  # Cycling Power Measurement
HR_SERVICE = "0000180d-0000-1000-8000-00805f9b34fb"  # Heart Rate Service
HR_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"  # Heart Rate Measurement

POWER_WINDOW_S = 3.0  # rolling average window, like "3s power"

CSV_HEADER = ["timestamp", "elapsed_s", "power_w", "power_3s_w", "hr_bpm"]

power_samples: deque[tuple[float, int]] = deque()
latest_power: int | None = None
latest_hr: int | None = None
stop = asyncio.Event()  # set on Ctrl+C so every task can finish cleanly


def on_power(_sender, data: bytearray) -> None:
    # Layout: uint16 flags (LE), sint16 instantaneous power in watts (LE), optional fields after
    global latest_power
    _flags, watts = struct.unpack_from("<Hh", data, 0)
    latest_power = watts
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
            while client.is_connected and not stop.is_set():
                await asyncio.sleep(0.2)
            if not stop.is_set():
                print(f"[!!] {label} disconnected")
        # leaving the "async with" block disconnects cleanly
    except Exception as exc:  # keep the other sensor running if one fails
        print(f"[!!] {label} error: {exc}")


def open_recording(path: Path):
    """Create the CSV file (and its folder) and write the header row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    f = path.open("w", newline="")
    writer = csv.writer(f)
    writer.writerow(CSV_HEADER)
    return f, writer


async def printer(csv_path: Path | None) -> None:
    f = writer = None
    if csv_path:
        f, writer = open_recording(csv_path)
        print(f"Recording to {csv_path}")
    start = time.monotonic()
    rows = 0
    try:
        while not stop.is_set():
            await asyncio.sleep(1)
            if stop.is_set():
                break
            p = avg_power()
            p_txt = f"{p:4.0f} W" if p is not None else "  -- W"
            hr_txt = f"{latest_hr:3d} bpm" if latest_hr is not None else " -- bpm"
            print(f"power(3s): {p_txt} | HR: {hr_txt}")
            if writer:
                writer.writerow(
                    [
                        datetime.now().isoformat(timespec="seconds"),
                        round(time.monotonic() - start, 1),
                        "" if latest_power is None else latest_power,
                        "" if p is None else round(p),
                        "" if latest_hr is None else latest_hr,
                    ]
                )
                f.flush()  # keep the file usable even if the program is killed
                rows += 1
    finally:
        if f:
            f.close()
            print(f"Saved {rows} rows to {csv_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--csv", type=Path, metavar="FILE", help="also record one row per second to FILE"
    )
    return parser.parse_args()


async def main(csv_path: Path | None) -> None:
    asyncio.get_running_loop().add_signal_handler(signal.SIGINT, stop.set)
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

    tasks = [asyncio.create_task(printer(csv_path))]
    if trainer:
        tasks.append(asyncio.create_task(stream(trainer, CPS_MEASUREMENT, on_power, "trainer")))
    if hrm:
        tasks.append(asyncio.create_task(stream(hrm, HR_MEASUREMENT, on_hr, "HR strap")))
    await asyncio.gather(*tasks)
    print("\nStopped.")


if __name__ == "__main__":
    asyncio.run(main(parse_args().csv))
