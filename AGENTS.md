# Agent Guide - Pace BMS RS232 Monitor

This repository is for read-only Pace BMS monitoring over serial, with Home
Assistant add-on support and standalone Docker support.

Agents working here must behave like cautious coding partners. The project
handles real battery data, BMS alarms, SOC, SOH, cell voltage, pack voltage,
current, capacity, Telegram notifications, MQTT/Home Assistant integration,
local history and deployment packaging.

Use this file as the entrypoint. Detailed rules live in `docs/ai/`.

## Start Here

Read these before project work:

- `docs/ai/PROJECT_CONTEXT.md` - current architecture, batteries and data flow
- `docs/ai/CURRENT_SPRINT_STATUS.md` - current handover status and open watch areas
- `docs/ai/SAFETY_RULES.md` - non-negotiable BMS and deployment safety rules
- `docs/ai/SPRINT_WORKFLOW.md` - edit, version, validation and handoff flow
- `docs/ai/VALIDATION_CHECKLIST.md` - commands to run before handoff
- `docs/ai/CODING_STYLE.md` - code style and error-handling expectations

Use task-specific guides as needed:

- Config/UI: `docs/ai/CONFIG_RULES.md`, `docs/ai/UI_RULES.md`
- Serial/parser: `docs/ai/SERIAL_FRAME_DEBUGGING.md`
- Voltage/capacity: `docs/ai/VOLTAGE_PARSING.md`, `docs/ai/CAPACITY_PARSING.md`
- Warnings/Telegram: `docs/ai/WARNING_ALARM_HANDLING.md`, `docs/ai/ALERT_RULES.md`, `docs/ai/TELEGRAM_SETUP.md`
- MQTT/Home Assistant discovery: `docs/ai/MQTT_HOME_ASSISTANT_DISCOVERY.md`
- Deployment: `docs/ai/HOME_ASSISTANT_ADDON_MODE.md`, `docs/ai/STANDALONE_DOCKER_MODE.md`
- Prompt examples: `docs/ai/SPRINT_PROMPTS.md`

## Current Direction

- Home Assistant add-on is the primary deployment mode.
- Standalone Docker is a supported secondary deployment mode.
- Do not break either mode.
- Classic UI is the active UI. Do not revive alternate UI experiments unless
  the maintainer explicitly asks.
- Serial-first monitoring is the active architecture. The monitor writes
  `/data/pacebms-live.json` and `/data/pacebms_metrics.db`.
- MQTT is optional output/fallback, not the primary UI data source.

## Non-Negotiable Summary

- Do not add BMS write/control code.
- Do not add FET control, BMS threshold writes, calibration writes, balancing
  control or reset commands.
- Do not rename MQTT topics, Home Assistant discovery IDs or entity names unless
  the maintainer explicitly approves a migration.
- Do not commit unless the maintainer explicitly asks.
- For Home Assistant visible hotfixes, update `config.yaml`, README Current
  Version and `CHANGELOG.md`.

The complete hard-rule list is in `docs/ai/SAFETY_RULES.md`.
