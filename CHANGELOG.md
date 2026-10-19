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

### Fixed
- `ble_probe.py`: disconnect cleanly on Ctrl+C instead of printing a traceback.
