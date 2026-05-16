## 2.3.2 - 2026-05-17

### Fixed
- Fixed web UI header icon not displaying correctly by serving `icon.png` through Flask.
- Improved icon sizing and fallback behaviour in the web UI header.

### Changed
- Improved Configuration Backups section layout.
- Backups now show as a clearer table with Type, Created time, Backup File, Size and Actions.
- Restore confirmation now identifies the selected backup file, created time and backup type.
- Added backup type labels such as Manual, Before Save and Before Restore.

### Notes
- This is a web UI usability and icon fix release.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
