## 2.6.29 - 2026-05-17

### Added
- Added Basic Required, Full Monitoring and Advanced View filters to the Config tab.
- Added clearer Caution / Warning / Critical severity labels in the web UI warning overview.

### Changed
- Updated Notification Thresholds help text for severity-aware warning repeat fields.
- Updated web UI validation for the new severity repeat interval fields.
- Improved Config tab button hierarchy so Save, backup, download and restart actions are easier to scan.
- Updated README guidance for Basic Required versus Full Monitoring setup.

### Removed
- Removed an unused stale static stylesheet that was no longer loaded by the Ingress UI.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.28 - 2026-05-17

### Added
- Added severity-aware BMS warning repeat intervals:
  - `notify_warning_repeat_caution_seconds`
  - `notify_warning_repeat_warning_seconds`
  - `notify_warning_repeat_critical_seconds`
- Added persisted warning notification state across add-on restarts.
- Added short reminder messages for repeated ongoing warnings.

### Changed
- Normalized BMS warning text into stable risk families such as high cell voltage and high pack voltage.
- Warning notifications now resend immediately only for new risks or severity escalation.
- Ongoing caution, warning and critical alerts use separate configurable cooldowns.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.27 - 2026-05-17

### Added
- Added monitor heartbeat file for runtime health tracking.
- Added `/health` endpoint checks for Home Assistant Supervisor watchdog support.
- Added add-on `watchdog` configuration pointing to the internal health endpoint.
- Added README guidance for Home Assistant offline-monitor alerting.

### Fixed
- Fixed warning deduplication label normalization so warning text is no longer split incorrectly in logs.

### Notes
- No BMS write/control commands were added.
- Health checks monitor the add-on process heartbeat, not battery health.
- MQTT topics and Home Assistant discovery entity names were not changed.

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
