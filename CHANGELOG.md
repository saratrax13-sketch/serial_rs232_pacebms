## 2.6.7 - 2026-05-17

### Fixed
- Directly fixed Config section info popup lookup in `templates/index.html`.
- Added a frontend override for Config section info buttons.
- Notification Thresholds info now shows comma-separated threshold format help.
- Report Schedules info now shows 24-hour HH:MM format help.

### Notes
- This fix targets the actual popup click path in the template.
- `bms_ip` and `bms_port` were not re-added.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
