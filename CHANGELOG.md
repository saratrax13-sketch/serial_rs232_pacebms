## 2.5.1 - 2026-05-17

### Added
- Added Dashboard warning summary.
- Added Pack Comparison Cards.
- Added API-based Refresh Dashboard button using `/api/status`.
- Added live dashboard refresh for summary values, pack cards, bar charts and highest/lowest cell range indicators.

### Changed
- Improved Dashboard chart labels and descriptions.
- Clarified that dashboard charts use current retained MQTT values only.

### Notes
- No historical charting or database storage was added.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
- The add-on remains read-only to the BMS.
