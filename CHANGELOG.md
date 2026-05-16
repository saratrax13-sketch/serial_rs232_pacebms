## 2.1.2 - 2026-05-16

### Added
- Added Refresh Status button to the Status tab.
- Added client-side refresh using the existing `/api/status` endpoint.
- Added live update of Overall Status, availability, monitor state, stale status, last read timestamps, read ages, layout and BMS serial without a full page reload.

### Notes
- This is a web UI convenience release.
- No Python monitor logic changes were made.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
- The add-on remains read-only to the BMS.
