## 2.6.36 - 2026-05-17

### Added
- Added a dedicated Monitoring Health card on the Status tab.
- Added monitor heartbeat, MQTT monitor state, analog read age, warning read age, detected pack count and cell count checks to the web UI.
- Added README guidance for Status screenshots and what the Monitoring Health card means.

### Changed
- Status refresh now updates the Monitoring Health card from `/api/status`.
- `/api/status` now includes the same read-only Monitoring Health summary used by the web UI.

### Tests
- Added regression coverage for healthy and stale Monitoring Health summaries.
- Extended the Status page render test to confirm the Monitoring Health section loads.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.35 - 2026-05-17

### Fixed
- Fixed a web UI 500 error on the Status tab caused by a Jinja dictionary key collision in the Setup Checklist.

### Tests
- Added a Status page render regression test for the Setup Checklist.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.34 - 2026-05-17

### Added
- Added a web UI Setup Checklist card for guided first-run setup validation.
- Added clearer Telegram placeholder warnings when notifications are enabled but Telegram values are missing or placeholders.
- Added a Test Full Monitoring button that checks MQTT connectivity, Telegram configuration and notification thresholds without sending BMS commands or Telegram messages.
- Added README first-run setup checklist guidance.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.33 - 2026-05-17

### Fixed
- Changed the Home Assistant sidebar panel icon to `mdi:battery` for better compatibility with Home Assistant icon sets.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.32 - 2026-05-17

### Fixed
- Hardened warning-frame parsing for 16-cell multi-pack Pace BMS frames.
- Fixed false Pack 2 warning/protection/FET states caused by P16S inter-pack trailer bytes.
- Prevented clean 16-cell warning frames from decoding as `Lower cell volt protect`, `Above total volt protect`, or false FET OFF.

### Tests
- Added a regression test using the captured 16-cell two-pack warning payload.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.31 - 2026-05-17

### Fixed
- Hardened analog parsing for 16-cell multi-pack Pace BMS frames.
- Fixed P16S inter-pack trailer alignment so Pack 2 analog data is found by validating full pack candidates.
- Added analog frame bounds checks with clearer parser diagnostics.
- Prevented isolated analog parse errors from immediately causing false disconnect/reconnect Telegram alerts.

### Tests
- Added a regression test using the captured 16-cell two-pack analog payload.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.30 - 2026-05-17

### Changed
- Reordered Home Assistant add-on Configuration fields so Basic Required connection and MQTT options appear first.
- Moved Telegram, notification, warning-detail and report schedule fields after the required setup fields.
- Cleaned `config.yaml` comments to plain ASCII for easier repo maintenance.
- Updated README current version and setup guidance for the Home Assistant Configuration tab.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

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
