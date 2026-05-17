## 2.4.3 - 2026-05-17

### Fixed
- Fixed Dashboard tab showing `No chart data available`.
- Dashboard now fetches the live retained MQTT snapshot, the same as the Status tab.
- Dashboard charts can now populate from retained pack MQTT values.

### Notes
- Charts still use current retained MQTT values only.
- No historical charting or database storage was added.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
