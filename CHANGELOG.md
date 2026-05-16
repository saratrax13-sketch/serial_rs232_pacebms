# Changelog

All notable changes to this project will be documented in this file.

## 2.0.30 - 2026-05-16

### Fixed
- Fixed Home Assistant Ingress 404 error on Test Telegram and Test MQTT buttons.
- Changed web UI form actions to use relative Ingress-safe paths.

## 2.0.29 - 2026-05-16

### Fixed
- Fixed `publish_monitor_status` helper scope error in `bms_monitor.py`.
- Fixed add-on startup failure introduced in the 2.0.27 monitor status update.
- Retained web UI monitor status topics remain MQTT-only and do not write to the BMS.

## 2.0.28 - 2026-05-16

### Fixed
- Fixed indentation error in monitor status publishing added in 2.0.27.

## 2.0.27 - 2026-05-16

### Added
- Added Test Telegram button to the Home Assistant Ingress web UI.
- Added Test MQTT button to the Home Assistant Ingress web UI.
- Added retained MQTT monitor status topics under `pacebms/monitor/`.
- Added last successful analog read timestamp to the web UI.
- Added last successful warning read timestamp to the web UI.
- Added monitor state tile to the web UI.

### Notes
- Test buttons do not write to the BMS.
- Monitor status topics are MQTT-only status telemetry.

## 2.0.26 - 2026-05-16

### Changed
- Shortened detailed BMS warning Telegram messages.
- Improved wording from raw BMS warning strings to operator-friendly warning text.
- Cleaned startup Telegram version text.
- Telegram log output now shows the message title only.

### Added
- Added `notify_soc_high_on_startup` to prevent fully charged alerts on every add-on restart.
- Added `notify_soh_on_startup` to prevent SOH threshold alerts on every add-on restart.

### Notes
- Default behaviour suppresses startup-only SOC high and SOH alerts.
- Alerts still trigger again after SOC drops below `notify_soc_high_reset`, or SOH recovers above and later drops below the configured threshold.

## 2.0.25 - 2026-05-16

### Fixed
- Retained BMS identity MQTT topics: `bms_version`, `bms_sn`, and `pack_sn`.
- Fixed duplicate `Battery Fully Charged` Telegram messages after startup/midnight reset.
- High-SOC notifications now only reset after SOC drops below `notify_soc_high_reset`.

### Notes
- This remains read-only. No write/control commands are sent to the BMS.

## 2.0.24 - 2026-05-16

### Fixed
- Fixed Live Status showing BMS Serial as Unknown when the direct `bms_sn` MQTT topic is not retained.
- Added fallback to read BMS serial and version from the retained `bms_status` payload.

## 2.0.23 - 2026-05-16

### Added
- Added Live Status section to the Home Assistant Ingress web UI.
- Added MQTT-read status overview for BMS availability, detected packs, pack SOC, SOH, voltage, current, cell delta, FET states, and warnings.

### Notes
- Live Status reads MQTT values only.
- This feature does not write to the BMS.

## 2.0.22 - 2026-05-16

### Fixed
- Fixed Home Assistant Ingress web UI styling by embedding CSS directly into the page.
- Removed dependency on loading a separate static CSS file through the Ingress proxy.

## 2.0.21 - 2026-05-16

### Fixed
- Fixed Home Assistant Ingress web UI styling.
- Updated the web UI template to load static CSS correctly through Home Assistant Ingress.
- Improved visual appearance of the read-only configuration page.

## 2.0.20 - 2026-05-16

### Added
- Added read-only Home Assistant Ingress web UI.
- Added grouped configuration overview page inside the add-on.
- Added configuration sections for Telegram, Notifications, Warning Detail, MQTT, BMS Connection, and Advanced.
- Added masking of sensitive values such as Telegram token, chat ID, and MQTT password.
- Added `/health` endpoint for the web configuration UI.

### Changed
- Updated `run.sh` to start the web configuration UI in the background before starting the BMS monitor.
- Added Flask to `requirements.txt` for the web UI.
- Added Home Assistant Ingress settings to `config.yaml`.
- Bumped add-on version to `2.0.20`.

### Notes
- The web UI is read-only in this version.
- Settings must still be edited from the normal Home Assistant add-on Configuration tab.

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
