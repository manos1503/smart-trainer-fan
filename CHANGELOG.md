# Changelog

All notable changes are recorded here. Format: [Keep a Changelog](https://keepachangelog.com/),
versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Added
- Repository scaffold: firmware skeleton (PlatformIO, ESP32-S3), CI, contribution guide.
- `tools/ble_probe.py`: reads trainer power and heart rate over BLE from a computer.
- `ble_probe.py --csv FILE`: records power and heart rate once per second for offline analysis.
- `ble_probe.py`: reconnects automatically when a sensor drops, as soon as it advertises again;
  values older than 3 s are shown and recorded as missing instead of repeating the last reading.
- `tools/hr_contact.py`: detects when the heart-rate strap is off the body from its RR
  intervals (the HRM-Dual keeps sending stale values and ignores the standard contact bits);
  `ble_probe.py` shows and records heart rate as missing while the strap is off.
- `ble_probe.py --debug`: prints raw heart-rate packets with RR intervals and the verdict.
- Unit tests (`pytest`), including a real HRM-Dual on/off recording; run in CI.

### Fixed
- `ble_probe.py`: disconnect cleanly on Ctrl+C instead of printing a traceback.
