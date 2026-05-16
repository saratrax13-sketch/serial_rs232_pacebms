## 2.1.0 - 2026-05-16

### Added
- Added tabbed web UI layout: Status, Config and Events.
- Added event history clear button.
- Added event history export as JSON.
- Added event history export as CSV.
- Added `/api/status` JSON endpoint for current monitor and battery status.
- Added `/api/events` JSON endpoint for event history.
- Added warning severity grouping for pack cards.
- Added severity labels such as Normal, Voltage Warning, Protection, Fault, Stale and Offline.

### Changed
- Moved configuration overview into a dedicated Config tab.
- Moved Last Events / Status History into a dedicated Events tab.
- Improved warning display with severity labels while keeping detailed reference checks.

### Notes
- This is a web UI and support-tooling release.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
- The add-on remains read-only to the BMS.
