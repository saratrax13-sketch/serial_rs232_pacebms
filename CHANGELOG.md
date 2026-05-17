## 2.6.9 - 2026-05-17

### Fixed
- Added missing `Notification Thresholds` entry directly to the original `configHelpContent` modal help object.
- Added missing `Report Schedules` entry directly to the original `configHelpContent` modal help object.
- These two sections now use the same original Config help route and modal style as the existing sections such as MQTT.
- Removed the unnecessary unified/direct help workaround scripts from the template.

### Notes
- This keeps the original look and feel of the Config help modals.
- `bms_ip` and `bms_port` were not re-added.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
