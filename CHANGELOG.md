## 2.3.8 - 2026-05-17

### Fixed
- Fixed repeated backup delete actions causing a `Not Found` page.
- Backup POST actions now redirect back to the normal tab URL after completion.
- Create backup, delete backup, restore backup, save config and restart actions no longer leave the browser on action URLs.

### Notes
- This is a web UI routing/redirect polish release.
- Delete only removes selected backup JSON files.
- Config restore writes Home Assistant add-on options only.
- This does not write to the BMS.
- No BMS protocol changes were made.
