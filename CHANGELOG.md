## 2.3.9 - 2026-05-17

### Fixed
- Fixed repeated backup delete actions still causing a `Not Found` page.
- Delete action now redirects back to the clean Backups tab URL after completion.
- Compare and Restore Preview now use normal Backups tab query links instead of separate action-page URLs.
- Reduced the risk of broken relative paths after backup actions.

### Notes
- Delete only removes selected local backup JSON files.
- Restore writes Home Assistant add-on options only.
- This does not write to the BMS.
- No BMS protocol changes were made.
