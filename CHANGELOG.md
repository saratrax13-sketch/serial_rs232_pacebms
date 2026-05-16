## 2.0.38 - 2026-05-16

### Fixed
- Fixed MQTT availability staying `offline` while the monitor was running and data was fresh.
- Added explicit retained `online` availability publish after successful startup.
- Added explicit retained `online` availability publish after successful analog reads.
- Added explicit retained `online` availability publish after BMS recovery.

### Notes
- This is an MQTT availability status correction.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
- The add-on remains read-only to the BMS.
