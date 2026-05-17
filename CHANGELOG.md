## 2.5.4 - 2026-05-17

### Added
- Added `Refresh Diagnostics` button to the Diagnostics tab.
- Diagnostics refresh now uses `/api/status` without a full page reload.
- Refresh updates key health cards and current system summary fields.

### Notes
- Refresh uses retained MQTT/add-on status values only.
- This is a web UI usability improvement.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
- The add-on remains read-only to the BMS.
