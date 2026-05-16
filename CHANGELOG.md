## 2.2.0 - 2026-05-17

### Added
- Added direct Home Assistant add-on configuration saving from the web UI.
- Added editable Config tab fields for current add-on options.
- Added Save Configuration button.
- Added Restart Add-on button using the Supervisor self endpoint.
- Sensitive fields can be left blank to keep existing saved values.
- Configuration save and restart actions are logged in Last Events.

### Changed
- Replaced the Config Helper card with an editable add-on configuration form.

### Notes
- This writes Home Assistant add-on options only.
- This does not write to the BMS.
- No BMS protocol changes were made.
- Restart the add-on after saving changes that affect monitor runtime.
