# Configuration Backup and Restore

The add-on includes local backup and restore tools for Home Assistant add-on configuration.

![Backups tab](screenshots/Backups.png)

The Backups tab is only for Home Assistant add-on options. It does not write anything to the BMS and it does not change battery thresholds or FET state.

## Where backups are stored

Backups are stored inside the add-on data folder:

```text
/data/config_backups/
```

## How many backups are kept

The latest 10 backups are kept.

Older backups are automatically removed when the limit is exceeded.

## When backups are created

Backups are created automatically before:

- saving configuration from the web UI
- restoring a previous backup

You can also create a backup manually from the Backups tab.

## Backup types

| Type | Meaning |
|---|---|
| Manual Backup | Created by clicking Create Backup Now |
| Automatic Backup Before Save | Created before saving config from the web UI |
| Automatic Backup Before Restore | Created before restoring a previous backup |

## Compare

Use Compare before restoring a backup.

Compare shows what is different between the current configuration and the selected backup.

Sensitive values are hidden.

## Restore Preview

Use Restore Preview before the final restore.

Restore Preview shows what will change if you restore the selected backup.

## Restore

Restore writes Home Assistant add-on options only.

It does not write to the BMS.

Restart the add-on after restoring for runtime changes to apply.

## Download

Use Download to save a single backup file.

Use Download All ZIP to save all currently stored backups as a ZIP file.

## Delete

Delete removes only the selected local backup file.

It does not affect the current running configuration.
