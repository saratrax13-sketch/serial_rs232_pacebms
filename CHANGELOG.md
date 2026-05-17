## 2.6.10 - 2026-05-17

### Fixed
- Restored Config info button JavaScript handler.
- Restored `openConfigHelp(groupName)` compatibility with the original Config help modal.
- Kept Notification Thresholds and Report Schedules inside the original `configHelpContent` object.
- Added aliases for older info/close functions so existing buttons continue to work.

### Notes
- This keeps the original Config help modal look and feel.
- `bms_ip` and `bms_port` were not re-added.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
