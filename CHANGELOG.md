## 2.2.2 - 2026-05-17

### Fixed
- Fixed Save Configuration prompting even when no real value changed.
- Fixed confirmation popup line breaks so `\n` is no longer shown as text.

### Added
- Added real change detection on the Config tab.
- Disabled Save Configuration until a real config change is detected.
- Added server-side no-change detection before saving add-on options.
- Added "No configuration changes detected" message when save is attempted without changes.

### Notes
- This is a web config save polish release.
- This writes Home Assistant add-on options only when values actually changed.
- This does not write to the BMS.
- No BMS protocol changes were made.
