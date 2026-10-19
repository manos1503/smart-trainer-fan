# Bill of materials (v0, breadboard prototype)

Prices checked October 2026 (Greece). Check stock before ordering.

| # | Part | Qty | Example source | Approx. price |
|---|---|---|---|---|
| 1 | ESP32-S3 dev board (ESP32-S3-DevKitC-1-N8R8, or any pin-compatible ESP32-S3 board with headers) | 1 | Grobotronics | €19.90 |
| 2 | USB data cable matching the board (USB-C ↔ micro-USB for the original DevKitC-1, USB-C ↔ USB-C for USB-C clones) | 1 | any | €2–5 |
| 3 | IR receiver 38 kHz, TSOP38238 (to learn the remote's codes) | 1 | Grobotronics | €1.20 |
| 4 | IR LED 940 nm, 5 mm | 2 | Grobotronics | €0.15–0.20 each |
| 5 | NPN transistor (2N2222 / PN2222A / BC337) to drive the IR LED | 2 | Grobotronics | <€0.50 |
| 6 | Resistors: 1 kΩ (transistor base), 100 Ω (LED current) | 2 + 2 | Grobotronics | <€0.50 |
| 7 | Breadboard (830 points) + male–male jumper wires | 1 | Grobotronics | ~€5–8 |
| 8 | Fan with an **infrared** remote, many speed steps | 1 | electronics retailers | €65–90 (Osio OSF-9015) |

## Notes

- **Fan:** the Osio OSF-9015 is a 40 cm pedestal fan with a BLDC motor, 24 speeds and a remote.
  Before buying, confirm the remote is IR (point it at a phone camera and press a button: the LED
  should flash on screen) rather than RF. Buy online, where EU distance-selling rules give a
  14-day return window.
- **IR driver:** GPIO → 1 kΩ → transistor base; 5 V → 100 Ω → IR LED → collector; emitter → GND.
  About 30 mA through the LED. Wiring diagram to follow in `hardware/wiring.md`.
