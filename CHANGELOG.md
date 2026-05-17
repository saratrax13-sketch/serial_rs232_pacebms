## 2.6.8 - 2026-05-17

### Changed
- Unified the Config section help system.
- All Config card info buttons now use the same `SECTION_HELP` mapping.
- Removed the direct 2.6.7 frontend workaround.
- Added canonical help text for all Config sections:
  - Telegram
  - Notifications
  - Notification Thresholds
  - Warning Detail
  - Report Schedules
  - MQTT
  - BMS Connection
  - Advanced

### Fixed
- Notification Thresholds now follows the same help route as the other Config sections.
- Report Schedules now follows the same help route as the other Config sections.

### Notes
- `bms_ip` and `bms_port` were not re-added.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
