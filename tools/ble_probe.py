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
    python ble_probe.py --debug              # also print raw heart-rate packets
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

from hr_contact import ContactDetector, parse_hr_measurement

# Standard Bluetooth SIG UUIDs
CPS_SERVICE = "00001818-0000-1000-8000-00805f9b34fb"  # Cycling Power Service
CPS_MEASUREMENT = "00002a63-0000-1000-8000-00805f9b34fb"  # Cycling Power Measurement
HR_SERVICE = "0000180d-0000-1000-8000-00805f9b34fb"  # Heart Rate Service
HR_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"  # Heart Rate Measurement

POWER_WINDOW_S = 3.0  # rolling average window, like "3s power"
STALE_S = 3.0  # a value older than this is treated as missing (sensors send >= 1 per second)
SCAN_SLICE_S = 2.0  # rescan in short slices so Ctrl+C is never delayed by more than this

CSV_HEADER = ["timestamp", "elapsed_s", "power_w", "power_3s_w", "hr_bpm"]

power_samples: deque[tuple[float, int]] = deque()
latest_power: tuple[float, int] | None = None  # (monotonic time, watts)
latest_hr: tuple[float, int] | None = None  # (monotonic time, bpm)
hr_contact = ContactDetector()
hr_in_contact: bool | None = None  # last reported state, to print only on changes
debug = False  # --debug: print every raw heart-rate packet
stop = asyncio.Event()  # set on Ctrl+C so every task can finish cleanly


def on_power(_sender, data: bytearray) -> None:
    # Layout: uint16 flags (LE), sint16 instantaneous power in watts (LE), optional fields after
    global latest_power
    _flags, watts = struct.unpack_from("<Hh", data, 0)
    now = time.monotonic()
    latest_power = (now, watts)
    power_samples.append((now, watts))


def on_hr(_sender, data: bytearray) -> None:
    global latest_hr, hr_in_contact
    packet = parse_hr_measurement(bytes(data))
    in_contact = hr_contact.update(packet)
    if debug:
        rr = ", ".join(f"{ms:.0f}" for ms in packet.rr_ms) or "-"
        verdict = "contact" if in_contact else "NO CONTACT"
        print(f"  HR raw: {data.hex(' ')} | bpm={packet.bpm} rr_ms=[{rr}] -> {verdict}")

    if in_contact != hr_in_contact:
        if hr_in_contact is not None:
            print("[OK] HR strap: on the body" if in_contact else "[!!] HR strap: not on the body")
        hr_in_contact = in_contact
    # Off the body the strap keeps sending a stale or made-up value, so drop it right away.
    latest_hr = (time.monotonic(), packet.bpm) if in_contact else None


def fresh(sample: tuple[float, int] | None) -> int | None:
    """Return the value only if it arrived recently, so a lost sensor shows as missing."""
    if sample is None or time.monotonic() - sample[0] > STALE_S:
        return None
    return sample[1]


def avg_power() -> float | None:
    now = time.monotonic()
    while power_samples and now - power_samples[0][0] > POWER_WINDOW_S:
        power_samples.popleft()
    if not power_samples:
        return None
    return sum(w for _, w in power_samples) / len(power_samples)


async def wait_or_stop(seconds: float) -> None:
    """Sleep, but wake up immediately on Ctrl+C."""
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except TimeoutError:
        pass


async def stream(device, char_uuid: str, handler, label: str) -> None:
    """Keep one sensor connected for the whole session, reconnecting when the link drops.

    After a drop we scan continuously for the sensor's address and connect the moment it
    advertises again, instead of waiting between attempts.
    """
    target = device  # first connection: the device found by the initial scan
    connected_before = False
    while not stop.is_set():
        try:
            if target is None:
                # Returns as soon as the sensor is seen, or None after one scan slice.
                target = await BleakScanner.find_device_by_address(
                    device.address, timeout=SCAN_SLICE_S
                )
                if target is None:
                    continue  # not advertising yet: keep scanning
            async with BleakClient(target, timeout=10.0) as client:
                await client.start_notify(char_uuid, handler)
                verb = "Reconnected" if connected_before else "Connected"
                print(f"[OK] {verb} to {label}: {device.name}")
                connected_before = True
                while client.is_connected and not stop.is_set():
                    await asyncio.sleep(0.2)
            # leaving the "async with" block disconnects cleanly
            if stop.is_set():
                break
            print(f"[!!] {label} disconnected, searching...")
        except Exception as exc:  # keep the other sensor running if one fails
            if stop.is_set():
                break
            print(f"[!!] {label} connection failed ({str(exc) or type(exc).__name__}), retrying...")
            await wait_or_stop(0.5)  # brief pause so a failing sensor cannot spin the loop
        target = None


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
            power_now = fresh(latest_power)
            hr = fresh(latest_hr)
            p_txt = f"{p:4.0f} W" if p is not None else "  -- W"
            hr_txt = f"{hr:3d} bpm" if hr is not None else " -- bpm"
            print(f"power(3s): {p_txt} | HR: {hr_txt}")
            if writer:
                # Missing values are written as empty cells, so gaps stay visible in the data.
                writer.writerow(
                    [
                        datetime.now().isoformat(timespec="seconds"),
                        round(time.monotonic() - start, 1),
                        "" if power_now is None else power_now,
                        "" if p is None else round(p),
                        "" if hr is None else hr,
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
    parser.add_argument(
        "--debug",
        action="store_true",
        help="print every raw heart-rate packet with RR intervals and contact verdict",
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
    args = parse_args()
    debug = args.debug
    asyncio.run(main(args.csv))
