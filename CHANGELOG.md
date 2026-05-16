## 2.2.1 - 2026-05-17

### Added
- Added confirmation prompt before saving configuration from the web UI.
- Added unsaved changes detection on the Config tab.
- Added visible restart-required banner when config fields are changed.
- Added basic validation for common configuration mistakes before saving.
- Added clearer save-blocked event logging when validation fails.

### Changed
- Improved save success message to clearly state that restart is required for monitor runtime changes.

### Notes
- This is a web config save safety-polish release.
- This writes Home Assistant add-on options only.
- This does not write to the BMS.
- No BMS protocol changes were made.
