# Changelog

All notable changes to this project will be documented in this file.

## 2.0.19 - 2026-05-16

### Added
- Added improved Home Assistant add-on configuration layout.
- Added detailed BMS warning threshold configuration.
- Added configurable cell high warning reference voltage.
- Added configurable cell low warning reference voltage.
- Added configurable cell delta warning threshold.
- Added configurable high and low temperature warning reference values.
- Added `notify_warning_detail_enabled` toggle for enhanced Telegram warning messages.

### Changed
- Simplified warning thresholds by removing early / attention warning levels.
- Warning detail now uses actual configured warning reference values only.
- Pack high and low voltage references can be calculated from detected cell count and configured cell voltage thresholds.
- Improved configuration order so commonly used settings appear higher and advanced/debug settings appear lower.
- Clarified that warning thresholds are read-only reference values used for notifications and do not write to the BMS.
- Recommended `debug_output: 0` for normal use and `debug_output: 3` only for troubleshooting.

### Fixed
- Improved documentation around 13-cell and 16-cell Pace-compatible packs.
- Improved explanation of detailed warning messages for cell voltage, pack voltage, SOC, SOH, cell delta, and temperature.

## 2.0.18 - 2026-05-16

### Added
- Added direct Telegram notifications from the Python monitor.
- Added BMS monitor startup notifications.
- Added BMS monitor shutdown notifications.
- Added BMS disconnect notifications.
- Added BMS recovery notifications.
- Added SOC low threshold notifications.
- Added SOC high / fully charged notifications.
- Added SOH degradation notifications.
- Added BMS warning notifications.
- Added Charge FET and Discharge FET change notifications.
- Added daily battery summary notifications.
- Added cell delta reporting.
- Added automatic cell-count detection for Pace-compatible BMS packs.
- Added automatic multi-pack detection when the battery link cables and DIP switch addresses are configured correctly.
- Added Home Assistant add-on changelog support through this `CHANGELOG.md` file.

### Changed
- Improved serial disconnect handling so a BMS that stops replying is treated as offline, even if the USB serial adapter remains connected.
- Improved service-stop handling so Home Assistant add-on shutdown can trigger a Telegram notification.
- Updated the README to clarify that this project is for any battery using the Pace BMS RS232 / UART ASCII protocol, not only Hubble AM2.
- Updated README examples to use the correct GitHub repository: `serial_rs232_pacebms`.
- Updated MQTT topic examples to match non-padded pack names such as `pack_1` and `pack_2`.
- Clarified that `zero_pad_number_cells` and `zero_pad_number_packs` only affect MQTT topic naming, not detection logic.
- Clarified that additional packs are detected automatically when each pack has a unique DIP switch address.

### Fixed
- Fixed missed BMS disconnect alerts when the retry counter passes the configured threshold.
- Fixed shutdown notifications not triggering reliably when the service is stopped.
- Fixed wording that made the project sound Hubble-specific.
- Fixed documentation around 13-cell and 16-cell Pace-compatible battery packs.
- Fixed documentation around master/slave battery addressing.

## 2.0.17 - 2026-05-16

### Added
- Added full Telegram notification engine via `bms_notify.py`.
- Added direct Telegram support without relying on Home Assistant automations.
- Added BMS status MQTT topic for startup and shutdown events.
- Added BMS error MQTT topic for disconnect and recovery events.
- Added timestamped MQTT error payloads to prevent stale retained error states.
- Added Home Assistant MQTT availability support.

### Changed
- Improved MQTT state publishing with change-detection to reduce unnecessary Home Assistant recorder writes.
- Improved Home Assistant MQTT Discovery support.
- Improved logging for analog reads, warning reads, disconnects, and recoveries.

## 2.0.6 - 2026-05-16

### Added
- Added Telegram bot token and chat ID configuration options.
- Added serial mode configuration for Pace-compatible RS232 connections.

### Changed
- Switched default examples to serial communication.
- Updated configuration examples for Home Assistant add-on use.

## 1.0.0 - 2026-05-16

### Added
- Initial Pace BMS to MQTT bridge.
- Added support for reading pack voltage, current, SOC, SOH, cycles, capacity, cell voltages, and temperatures.
- Added support for Pace BMS protocol constants in `constants.py`.
- Added support for MQTT publishing.
- Added Home Assistant MQTT Discovery.
- Added support for TCP/IP and serial communication modes.
