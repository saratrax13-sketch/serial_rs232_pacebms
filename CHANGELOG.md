## 2.3.0 - 2026-05-17

### Added
- Added local configuration backup storage under `/data/config_backups/`.
- Added automatic backup before every web Config save.
- Added automatic backup before restoring a previous config backup.
- Added Configuration Backups section to the Config tab.
- Added Create Backup Now button.
- Added Download backup button.
- Added Restore backup button.
- Added backup and restore events to Last Events.

### Notes
- Backups are local to the add-on data folder.
- Latest 10 backups are kept.
- Restore writes Home Assistant add-on options only.
- Restart is required after restoring for monitor runtime changes to apply.
- This does not write to the BMS.
- No BMS protocol changes were made.
