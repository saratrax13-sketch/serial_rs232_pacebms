# Coding Skills

This file is the root index for project-specific coding skills used when maintaining Pace BMS RS232 Monitor.

Use these guides together with `AGENTS.md` and `docs/ai/PROJECT_CONTEXT.md`.

## Core Rules

- Keep the add-on read-only to the BMS.
- Do not add BMS write/control commands.
- Do not add FET control, BMS threshold writes, calibration writes, balancing control or reset commands.
- Do not reintroduce TCP/IP BMS connection code unless the maintainer explicitly changes project direction.
- Preserve MQTT topics, Home Assistant discovery identifiers and entity names unless a migration is explicitly approved.
- Prefer readable, defensive code over clever code.
- Show missing, invalid, stale or unavailable battery data clearly instead of hiding it.
- Keep `config.yaml`, README Current Version and `CHANGELOG.md` aligned for release-visible changes.

## Skill Guides

- `docs/ai/SERIAL_FRAME_DEBUGGING.md`
- `docs/ai/VOLTAGE_PARSING.md`
- `docs/ai/CAPACITY_PARSING.md`
- `docs/ai/WARNING_ALARM_HANDLING.md`
- `docs/ai/MQTT_HOME_ASSISTANT_DISCOVERY.md`
- `docs/ai/TELEGRAM_SETUP.md`
- `docs/ai/HOME_ASSISTANT_ADDON_MODE.md`
- `docs/ai/STANDALONE_DOCKER_MODE.md`

## Validation

Before release-style handoff, run:

```powershell
python -m py_compile bms_monitor.py bms_notify.py web_config.py constants.py supervisor.py tests\test_core_behaviour.py battery_profiles.py
python -m unittest discover -s tests -v
git diff --check
```

For config changes, also verify that every option is present in `config.yaml` options, `config.yaml` schema and `web_config.GROUPS`, with no duplicate group keys.
