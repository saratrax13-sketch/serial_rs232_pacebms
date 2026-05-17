## 2.6.26 - 2026-05-17

### Changed
- Removed unused TCP/IP BMS transport code from the monitor runtime.
- Improved add-on process supervision so the web UI and monitor are both watched.
- Updated energy tracking to calculate kWh from actual elapsed sample time instead of the configured scan interval.
- Synced README current version reference.

### Fixed
- Telegram placeholder credentials are now treated as unconfigured.
- Telegram failure logs no longer expose detailed exception text.

### Added
- Added focused unit tests for Pace frame parsing, Telegram placeholder handling, and energy tracking.

### Notes
- No BMS write/control commands were added.
- No MQTT topic or Home Assistant discovery entity names were changed.
- Standalone Docker config handling was intentionally left unchanged for a later sprint.
