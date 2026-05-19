# Agent Guide - Pace BMS RS232 Monitor

This repository is a Home Assistant add-on for read-only Pace BMS RS232 monitoring.

Agents working in this repo must behave like cautious coding partners. The project deals with real battery data, BMS alarms, warnings, SOC, SOH, cell voltage, pack voltage, current, capacity, Telegram notifications, Home Assistant integration and add-on deployment. Prefer safe, readable, well-tested changes over clever shortcuts.

Use this guide before making project changes. More detailed guidance lives in `docs/ai/`.

## Core Project Rules

- Treat this as a Home Assistant add-on first. Standalone Docker support is not the current priority.
- Never add BMS write/control code.
- Never add FET control, BMS threshold writes, calibration writes, or setting writes.
- TCP/IP BMS connection code was intentionally removed. Do not reintroduce it unless the maintainer explicitly asks.
- Web UI actions may save Home Assistant add-on options only. They must not send BMS commands.
- Test buttons may test MQTT and Telegram only. They must not touch the BMS.
- Preserve MQTT topics and Home Assistant discovery entity names unless the maintainer explicitly accepts breaking changes.
- Preserve support for tested 13S Hubble AM2 and 16S Eenovance MANA packs.

## UI/UX Instructions

When working on the frontend UI, keep the current Home Assistant ingress UI neat, tidy, compact, professional and easy for normal users, installers and technicians.

Avoid bulky layouts, oversized cards, full dark dashboards, unnecessary animations, and hiding stale, invalid or unavailable values.

Clearly separate normal user view, technician diagnostics, raw backend data, warnings/events and settings/configuration display.

Never silently hide bad data. Show `No data`, `Invalid`, `Stale` or `Offline` states clearly.

## Coding Style

Prefer readable code over clever code.

Use:

- clear function names
- clear comments where they explain non-obvious behavior
- defensive parsing for BMS, MQTT, config and retained-state data
- centralized constants for thresholds and repeated defaults
- configurable settings where useful
- version numbers for release work

Avoid:

- magic numbers scattered through the code
- silent exception swallowing
- fake default values that hide missing data
- overly broad rewrites
- changing unrelated files
- renaming entities, MQTT topics or config keys without explicit approval

## Sprint Workflow

For every sprint:

1. Confirm the requested scope.
2. Prefer meaningful sprint batches over tiny one-or-two-change uploads, unless the maintainer asks for an urgent small fix.
3. Update tests when behavior changes.
4. Keep `config.yaml`, `README.md`, and `CHANGELOG.md` aligned when version or user-facing behavior changes.
5. Run validation before final response.
6. Provide a concise git commit comment whenever a GitHub commit/upload is requested.
7. Provide a release/GitHub comment when a versioned release is requested.
8. Do not commit unless the maintainer explicitly asks.

## Required Validation

Run these before release-style handoff:

```powershell
python -m py_compile bms_monitor.py bms_notify.py web_config.py constants.py supervisor.py tests\test_core_behaviour.py battery_profiles.py
python -m unittest discover -s tests -v
git diff --check
```

For config changes, also verify:

- all `config.yaml` options exist in schema
- all schema keys exist in options
- all option keys are represented in `web_config.GROUPS`
- no duplicate group keys exist

## Key References

- `docs/ai/PROJECT_CONTEXT.md`
- `docs/ai/SAFETY_RULES.md`
- `docs/ai/SPRINT_WORKFLOW.md`
- `docs/ai/CONFIG_RULES.md`
- `docs/ai/ALERT_RULES.md`
- `docs/ai/UI_RULES.md`
- `docs/ai/CODING_STYLE.md`
- `docs/ai/SPRINT_PROMPTS.md`
- `docs/ai/VALIDATION_CHECKLIST.md`

## Project Skills

- `docs/ai/SERIAL_FRAME_DEBUGGING.md`
- `docs/ai/VOLTAGE_PARSING.md`
- `docs/ai/CAPACITY_PARSING.md`
- `docs/ai/WARNING_ALARM_HANDLING.md`
- `docs/ai/MQTT_HOME_ASSISTANT_DISCOVERY.md`
- `docs/ai/TELEGRAM_SETUP.md`
- `docs/ai/HOME_ASSISTANT_ADDON_MODE.md`
- `docs/ai/STANDALONE_DOCKER_MODE.md`
