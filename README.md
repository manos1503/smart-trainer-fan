# smart-trainer-fan

An ESP32-based smart fan for indoor cycling. It reads live **power** from a smart trainer
and **heart rate** from a chest strap over Bluetooth LE, and sets the fan speed to match
the effort, while Zwift (or any other app) stays connected to the same sensors.

> Status: early development, step 0 (BLE probe on the Mac).

## How it works

```
HR strap / trainer ──BLE──► ESP32 ──IR LED──► fan with IR remote
                              │
                              └─ small Wi-Fi web page (zones, manual override)
```

- **Power first, heart rate as fallback.** Power reacts instantly; heart rate lags effort by 30–60 s.
- **IR control.** The ESP32 learns the fan's remote-control codes and replays them, so it works with
  an ordinary fan and never touches mains wiring. See [ADR 0001](docs/decisions/0001-ir-fan-control.md).

## Repository layout

| Path | What lives there |
|---|---|
| `firmware/` | PlatformIO project for the ESP32-S3 (C++, Arduino framework) |
| `tools/` | Python helpers that run on a computer (BLE probe, IR code tools) |
| `hardware/` | Bill of materials, wiring, enclosure files |
| `docs/` | Architecture notes and decision records (`docs/decisions/`) |

## Tested setup

- Trainer: Wahoo KICKR CORE 2 (up to 3 simultaneous BLE connections)
- HR strap: Garmin HRM-Dual (2 simultaneous BLE connections)
- App: Zwift on macOS

## Getting started

### Step 0: BLE probe (no hardware needed)

```bash
cd tools
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python ble_probe.py
```

Wear the strap and pedal for a few seconds so both devices advertise. Run it once with Zwift
closed and once with Zwift connected.

### Firmware

Install the [PlatformIO](https://platformio.org/install/ide?install=vscode) extension in VS Code, then:

```bash
cd firmware
pio run            # build
pio run -t upload  # flash
pio device monitor # serial output
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, commit style and signed commits.

## License

[MIT](LICENSE)
