## 2.4.0 - 2026-05-17

### Added
- Added Diagnostics tab to the web UI.
- Added health cards for MQTT, monitor state, BMS reads, warnings, Telegram, Home Assistant Discovery, backups and read-only BMS safety.
- Added Current System Summary section.
- Added Download Diagnostic Report button.
- Added `/download-diagnostics.json` route.
- Diagnostic report redacts sensitive values such as Telegram tokens and MQTT passwords.

### Notes
- This is the first 2.4 diagnostics release.
- No historical charts were added in this version.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
- The add-on remains read-only to the BMS.
