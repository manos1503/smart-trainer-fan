# 0001: Control the fan through its IR remote protocol

- Status: accepted
- Date: 2026-10-19

## Context

The fan speed has to change automatically. Options considered:

1. DC fan (12/24 V) driven with PWM through a MOSFET.
2. Off-the-shelf fan with an infrared remote; the ESP32 replays the remote's codes.
3. Relays on the speed switches of a 230 V fan.
4. TRIAC dimmer on a 230 V fan.

## Decision

Option 2: IR control.

## Consequences

- No mains wiring, so it is safe to build and to share with others.
- Works with any fan that has an IR remote, which matters if other people use the project.
- Speed resolution is limited to the fan's own steps (a fan with many steps is preferred).
- One-way control: the ESP32 cannot read the fan's state, so it must track it itself and
  re-sync (e.g. power off → known state) when needed.
- Options 3 and 4 were rejected for safety; 4 also suits fan motors poorly.
- Option 1 remains a possible future hardware variant.
