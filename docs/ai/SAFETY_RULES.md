# Safety Rules

These rules are non-negotiable unless the maintainer gives a direct, explicit instruction that changes project direction.

## Deployment Safety

Home Assistant add-on is the primary deployment mode.

Standalone Docker is a supported secondary deployment mode.

Do not break either mode. Do not refactor monitor behavior around Docker-only
assumptions, and do not make Home Assistant Ingress assumptions that break
standalone Docker.

## Read-Only BMS Policy

Do not add code that writes to the BMS.

Do not add:

- BMS threshold writes
- BMS setting writes
- calibration writes
- FET on/off commands
- charge/discharge control
- balancing control
- reset commands
- firmware/configuration writes

Allowed BMS actions are read/poll actions only, such as:

- version read
- serial number read
- analog data read
- capacity read
- warning/status read

## Web UI Safety

The Web UI may:

- save Home Assistant add-on options
- test MQTT connectivity
- send a Telegram test message
- perform a dry Full Monitoring check
- create/restore/delete local add-on config backups
- show diagnostics/logs/events

The Web UI must not:

- write BMS thresholds
- control BMS FETs
- send any BMS command from a test button
- change battery settings

Classic UI is the active UI. Do not reintroduce alternate UI experiments or
replace the Classic UI unless the maintainer explicitly asks.

The UI must show missing, invalid, stale or unavailable data clearly. Do not
hide bad data behind fake defaults.

## Serial-First Data Safety

Serial polling is the source of truth when directly connected.

The Web UI must not open the serial port directly.

The monitor owns:

- `/data/pacebms-live.json`
- `/data/pacebms_metrics.db`

MQTT is optional output/fallback. Do not treat retained MQTT as the primary UI
source when a valid live serial snapshot exists.

Reject corrupt, partial or checksum-invalid frames before publishing,
displaying, storing or alerting from their values.

Do not publish fake MQTT values.

Do not alert stale or invalid data as if it were live battery data.

## Alerting Safety

Telegram alerts should inform and explain. They must not imply the add-on has changed BMS behavior.

When warning reference values are shown, describe them as UI/Telegram references only. They are not BMS factory settings and are not written to the BMS.

## Breaking Change Guardrails

Do not rename MQTT topics, discovery IDs or Home Assistant entities unless the maintainer explicitly accepts the migration cost.

Do not reintroduce TCP/IP BMS connection code unless explicitly requested.

Do not change `config.yaml` option names or schema semantics without preserving
backward compatibility or documenting a migration.

## Release / Hotfix Safety

For every Home Assistant visible hotfix or release, update:

- `config.yaml` version
- README Current Version
- `CHANGELOG.md`

Release notes should state whether MQTT topics, Home Assistant discovery
identifiers, monitor polling behavior or BMS commands changed. When nothing
changed, say so explicitly.
