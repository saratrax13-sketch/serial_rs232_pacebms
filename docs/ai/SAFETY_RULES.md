# Safety Rules

These rules are non-negotiable unless the maintainer gives a direct, explicit instruction that changes project direction.

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

## Alerting Safety

Telegram alerts should inform and explain. They must not imply the add-on has changed BMS behavior.

When warning reference values are shown, describe them as UI/Telegram references only. They are not BMS factory settings and are not written to the BMS.

## Breaking Change Guardrails

Do not rename MQTT topics, discovery IDs or Home Assistant entities unless the maintainer explicitly accepts the migration cost.

Do not reintroduce TCP/IP BMS connection code unless explicitly requested.

