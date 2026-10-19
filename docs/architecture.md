# Architecture

## Data flow

```
KICKR CORE 2 ──BLE (Cycling Power 0x1818)──┐
                                           ├──► ESP32-S3 ──► control logic ──► IR LED ──► fan
HRM-Dual ─────BLE (Heart Rate 0x180D)──────┘         │
                                                     └──► Wi-Fi web UI (settings, override)
```

Zwift keeps its own BLE connections. The ESP32 uses one of the spare slots on each sensor
(KICKR CORE 2: 3 slots, HRM-Dual: 2 slots).

## Control logic (planned)

1. **Input:** 3 s rolling average power; heart rate when power is unavailable.
2. **Mapping:** input → effort zone → fan speed step (zones configurable, e.g. % of FTP).
3. **Smoothing:** hysteresis between zones and a minimum dwell time, so short spikes
   (sprints, a single hard pedal stroke) do not make the fan jump up and down.
4. **Output:** send the IR code for the target speed only when it changes.
5. **Override:** manual speed from the web UI; auto-off after N seconds of zero power.

## BLE payloads

| Characteristic | UUID | Layout used |
|---|---|---|
| Cycling Power Measurement | `0x2A63` | `uint16 flags`, `sint16 power (W)`, … |
| Heart Rate Measurement | `0x2A37` | `uint8 flags`; bit0 = 0 → `uint8 bpm`, 1 → `uint16 bpm` |

All multi-byte fields are little-endian.
