## 2.2.4 - 2026-05-17

### Added
- Added changed-field highlighting on the Config tab.
- Added Changed badge on config cards with unsaved changes.
- Added Revert This Card button for each config card.
- Added Discard All Unsaved Changes button.
- Revert actions restore fields to the last saved values currently loaded in the web UI.

### Changed
- Improved Config tab safety and visibility when editing settings.
- Save Configuration remains disabled until a real change is detected.

### Notes
- Revert means "revert to last saved add-on options", not factory defaults.
- This writes Home Assistant add-on options only when Save Configuration is used.
- This does not write to the BMS.
- No BMS protocol changes were made.
