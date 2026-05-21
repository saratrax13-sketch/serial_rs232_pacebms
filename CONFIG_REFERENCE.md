# Configuration Reference

This is the short root configuration reference. The detailed guide is [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md).

Release: `2.10.0`

## Required Groups

| Group | Purpose |
|---|---|
| BMS Connection | Serial path, baud rate and poll interval |
| History & Live Data | Serial-first web UI source and local SQLite history |
| MQTT | Optional MQTT publishing and Home Assistant discovery |
| Advanced | Debug level and MQTT topic padding |
| Battery Profile & References | Read-only UI/Telegram reference values and layout checks |

## Optional Groups

| Group | Purpose |
|---|---|
| Telegram | Direct Telegram delivery settings |
| Notifications | Alert category toggles |
| Notification Thresholds | SOC, SOH, stale-data and warning repeat timing |
| Warning Detail | Which measured values are included in explanations |
| FET Notifications | FET alerting only, never FET control |
| Scheduled Reports | Daily summary and cell-delta report schedule |

## Safety Rules

- Config values are Home Assistant add-on options or standalone `/data/options.json` values.
- They do not write to the BMS.
- Battery profile values are display and Telegram reference values only.
- MQTT topic padding and base topic settings are discovery-sensitive. Do not change them after Home Assistant has created entities unless you intentionally plan a cleanup.
- Leave sensitive fields blank in the web Config form to preserve saved values.

## Normal Defaults

```yaml
connection_type: Serial
bms_connection_mode: Serial
bms_baudrate: 9600
ui_data_source: auto
metrics_enabled: true
mqtt_retain_state: true
debug_output: "0"
battery_profile: auto
```
