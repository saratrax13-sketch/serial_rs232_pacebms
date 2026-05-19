# Project Context

## Project Name

`serial_rs232_pacebms`

## Project Folder

`C:\Users\iCentre\Documents\Codex\serial_rs232_pacebms`

## Purpose

Pace BMS RS232 Monitor is used to monitor Pace-compatible BMS batteries over the Pace RS232/UART ASCII protocol.

The project reads battery data, rejects invalid data, interprets BMS values, exposes useful diagnostics, publishes MQTT/Home Assistant state, and optionally sends Telegram notifications.

The monitor is intended to help users know whether the battery pack is healthy, stale, warning, critical, charging, discharging, idle or disconnected.

## Current Direction

- Home Assistant add-on first.
- Read-only BMS communication.
- Current supported path is RS232 serial using Pace/UART ASCII frames.
- RS485 and standalone Docker may be considered later, but do not change protocol assumptions without proof from logs and maintainer approval.
- TCP/IP BMS connection code was intentionally removed.
- MQTT retained state drives the Web UI and Home Assistant sensors.
- Telegram is an optional monitoring/alerting layer.
- Web UI is split by audience:
  - Dashboard: user confidence
  - Tech Status: live technician review
  - Setup: first-run checklist and safe tests
  - Config: grouped Home Assistant add-on options
  - Diagnostics: support proof and detailed cell data
  - Logs: simple support log viewer
  - Events: local app history
  - Backups: add-on option backup/restore

## Battery Context

Primary battery type currently worked on:

- Hubble AM2
- Pace BMS
- 13S NMC battery architecture
- expected nominal full capacity: 100 Ah per battery
- two-battery system expected nominal capacity: 200 Ah total

Also tested:

- Eenovance MANA LFP Wall Mount 10.65kWh 51.2V
- 16S LFP battery architecture
- expected nominal full capacity: 200 Ah per battery

Do not assume all packs are 13S or all packs are 16S. Use detected cell count and model/profile context.

## Tested Batteries

| BMS / firmware string | Battery | Cells |
|---|---|---:|
| `P13S120A-12290-1.50` | Hubble Lithium AM2 5.5kWh 51V Battery | 13S |
| `P13S120A-12290-2.50` | Hubble Lithium AM2 5.5kWh 51V Battery | 13S |
| `P16S200A-C21084-3.10` | Eenovance Mana LFP Wall Mount 10.65kWh 51.2V | 16S |

## Important Data Points

The app may need to read, publish, display or calculate:

- pack voltage
- pack current
- state of charge
- state of health
- remaining capacity
- full capacity
- design capacity
- cell voltages
- highest cell voltage
- lowest cell voltage
- cell delta
- temperature values
- charge/discharge/idle state
- warning flags
- protection flags
- alarm state
- BMS internal warning state
- runtime estimate
- charging time estimate
- MQTT/Home Assistant sensor state
- Telegram alert state
- monitor heartbeat and stale-data state

## Important Behaviour

Prioritize accurate data over pretty output.

If data is missing, corrupt, impossible or stale, show it as invalid, unavailable, unknown or stale rather than replacing it with fake values.

For battery monitoring, it is better to show a problem than to hide a problem.

Do not publish bad BMS data from corrupt or partial frames.

Do not invent serial numbers, cell values, capacity values or health values when the BMS does not report them.

## Safety Position

Default and only supported BMS behavior is read-only monitoring.

Do not add BMS write/control code.

Do not add FET control, BMS threshold writes, calibration writes, protection setting writes or reset commands.

Any change that could affect real battery behavior must be rejected unless the maintainer explicitly changes the project policy.

## Known Issues / Watch Areas

### Incorrect Voltage Scaling

Pack voltage must not show impossible values such as over 60 V for a 13S Hubble AM2 battery unless raw data proves it. If values look impossible, investigate scaling and parsing before publishing or displaying them as valid.

### Capacity Scaling

mAh must be converted correctly to Ah.

Example:

```text
207550 mAh -> about 208 Ah
```

Dashboard display often prefers Ah with no decimals.

### Cell Count

Hubble AM2 should expose 13 cell values. Eenovance MANA P16 should expose 16 cell values.

Do not assume 16 cells unless the BMS model/profile or detected payload requires it.

### Repeated Warnings

Telegram warnings should not spam repeatedly while the same alarm remains active.

Use warning family normalization, severity-aware repeat cooldowns and clear/recovery events.

### BMS Internal Warnings

The BMS may report an internal warning even when calculated reference thresholds are not crossed.

The app must distinguish between:

- BMS-reported warning/protection flags
- app-configured UI/Telegram reference thresholds

Warning Intelligence and Telegram detail should explain this difference clearly.

### Invalid Serial Frames

Corrupt, partial or checksum-invalid frames must be rejected.

Do not publish bad data.

### Duplicate Home Assistant Entities

MQTT discovery IDs and device identifiers must stay stable and unique.

Renaming repositories, add-ons, topics or discovery IDs may create stale Home Assistant entities if not handled carefully.

## Main Files

| File | Responsibility |
|---|---|
| `bms_monitor.py` | Serial polling, Pace frame parsing, MQTT publishing, monitor heartbeat |
| `bms_notify.py` | Telegram notifications, warning detail, daily summaries and deduplication state |
| `web_config.py` | Flask web UI, config save/restore, diagnostics, log view, live status |
| `battery_profiles.py` | Read-only battery reference profiles for UI/Telegram explanation |
| `config.yaml` | Home Assistant add-on metadata, default options and schema |
| `templates/index.html` | Ingress Web UI |
| `tests/test_core_behaviour.py` | Core behavior, warning, config and UI route tests |

## Data Flow

```text
Pace BMS RS232 -> bms_monitor.py -> retained MQTT topics
retained MQTT topics -> Home Assistant discovery/entities
retained MQTT topics -> web_config.py live UI
warning/status reads -> bms_notify.py -> Telegram
web_config.py -> Home Assistant add-on options only
```

## Deployment Modes

### Home Assistant Add-on Mode

This is the current primary mode.

The add-on needs:

- `config.yaml`
- Dockerfile
- run script
- options schema
- MQTT settings
- serial port settings
- Telegram settings
- logging options
- versioning

Telegram should not be assumed to be automatically enabled in Home Assistant. The add-on sends Telegram directly through the Telegram Bot API when configured.

### Standalone Docker Mode

Standalone Docker is a possible future mode, not the current priority.

It may need:

- `docker-compose.yml`
- `.env` file
- configurable serial port
- configurable MQTT broker
- configurable Telegram bot token and chat ID
- persistent config volume
- logs
- restart policy
- health check

Do not refactor around standalone Docker unless the maintainer starts that sprint.

## Versioning

Use semantic-style versioning:

```text
MAJOR.MINOR.PATCH
```

Typical meaning:

- PATCH: bug fix, parsing fix, notification fix, docs/screenshots update
- MINOR: new sensor, new config option, new deployment mode
- MAJOR: breaking configuration or architecture change

Update version numbers when meaningful functionality or release documentation changes.

Keep `config.yaml`, README Current Version and `CHANGELOG.md` aligned.

## GitHub Safety

Do not commit:

- `.env` files
- Telegram bot tokens
- MQTT passwords
- private serial/device details beyond safe examples
- private client data
- logs containing sensitive data
- screenshots exposing secrets

Do commit:

- source code
- tests
- example configuration
- README
- Dockerfile/add-on files
- documentation
- sanitized screenshots

## Preferred Assistant Output

When assisting with code changes:

- give exact file paths
- explain what changed
- provide a patch/diff when safer than a full-file dump
- include test steps
- include rollback notes for risky changes
- avoid unnecessary rewrites
- keep production and battery safety in mind
- state clearly when something was not tested

