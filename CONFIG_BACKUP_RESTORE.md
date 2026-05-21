# Config Backup and Restore

The full guide is [docs/CONFIG_BACKUP_RESTORE.md](docs/CONFIG_BACKUP_RESTORE.md).

Release: `2.10.0`

The Backups tab manages Home Assistant add-on options only. It does not send BMS commands, change thresholds, control FETs or write battery settings.

## Backup Location

Backups are stored inside the add-on data folder:

```text
/data/config_backups/
```

## Recommended Use

- Create a manual backup before major configuration changes.
- Use Compare before restoring.
- Use Restore Preview before the final restore.
- Restart the add-on after restoring options.

## What Is Protected

- Sensitive values are hidden in compare/preview views.
- The current running configuration is not deleted by deleting a backup file.
- Restoring a backup writes add-on options only.

## Close-Off Check

Before project close-off, confirm:

- Manual backup creation works.
- Compare displays expected changes.
- Restore Preview displays expected changes.
- Download and Download All ZIP work.
