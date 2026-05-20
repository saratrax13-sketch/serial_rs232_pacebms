# Current Sprint Status

Use this file as the quick handover note for a fresh Codex thread.

Update it when a sprint is started, paused, completed or handed over. Keep it short and current.

## Current State

- Home Assistant add-on is the primary deployment mode.
- Standalone Docker is supported as a secondary deployment mode.
- Classic UI is the active UI.
- Serial-first monitoring is the active architecture.
- MQTT is optional output/fallback, not the primary UI source.
- The monitor owns `/data/pacebms-live.json` and `/data/pacebms_metrics.db`.

## Open Sprint

- No active sprint recorded in this handover file.

## Recent Focus Areas

- Serial-first live snapshot and SQLite history.
- History graph usability and tab refresh stability.
- Telegram warning deduplication and warning clarity.
- Config save/load behavior and reference-value consistency.
- Classic UI polish across Dashboard, History, Tech Status, Diagnostics, Setup and Config.

## Known Watch Areas

- Daily summaries and cell delta reports should use SQLite history when available.
- Warning Intelligence must separate BMS-reported warnings from user alert references.
- Low-cell reference rows should not be shown as warnings when the measured value is above the configured low reference.
- Home Assistant visible hotfixes require a version bump in `config.yaml`, README Current Version and `CHANGELOG.md`.
- Do not rename MQTT discovery IDs, topics or Home Assistant entities without explicit migration approval.

## Next Recommended Validation

```powershell
python -m py_compile bms_monitor.py bms_notify.py web_config.py constants.py supervisor.py tests\test_core_behaviour.py battery_profiles.py bms_live.py bms_history.py standalone_config.py
python -m unittest discover -s tests -v
git diff --check
```

For live add-on/container validation, run inside the PaceBMS container:

```sh
ls -lh /data/pacebms-live.json
ls -lh /data/pacebms_metrics.db*
```
