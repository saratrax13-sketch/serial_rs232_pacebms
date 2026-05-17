## 2.6.11 - 2026-05-17

### Fixed
- Restored the original Config help modal system.
- Removed the bad modal override/workaround behaviour from the previous help fixes.
- Added `Notification Thresholds` directly into the original `configHelpContent` object.
- Added `Report Schedules` directly into the original `configHelpContent` object.
- Fixed the issue where info buttons opened a different/bad-looking modal.

### Notes
- This keeps the same original look and feel as the working MQTT help modal.
- `bms_ip` and `bms_port` were not re-added.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
