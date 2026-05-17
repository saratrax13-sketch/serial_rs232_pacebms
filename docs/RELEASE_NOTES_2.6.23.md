# Pace BMS RS232 Monitor v2.6.23 Stable Release Notes

## Release purpose

This release is a stable documentation and cleanup checkpoint after the 2.6.x UI, backup, diagnostics, validation and notification improvements.

No BMS write or control commands were added. The monitor remains read-only to the BMS.

## Required base setup

The base system only needs these Config sections:

1. BMS Connection
2. MQTT
3. Advanced

These are marked as Required in the Config tab.

### BMS Connection

Required for reading the battery BMS over RS232.

Required fields:

- connection_type
- bms_serial
- bms_baudrate
- scan_interval

### MQTT

Required for publishing battery data and Home Assistant discovery.

Required fields:

- mqtt_host
- mqtt_port
- mqtt_user
- mqtt_password
- mqtt_base_topic
- mqtt_ha_discovery_topic
- mqtt_retain_state
- state_force_republish_seconds
- warn_force_republish_seconds

### Advanced

Required because it controls basic runtime/logging and topic formatting.

Important defaults:

- debug_output: 0
- zero_pad_number_cells: 2
- zero_pad_number_packs: 2

## Optional monitoring features

These Config sections are optional:

- Telegram
- Notifications
- Notification Thresholds
- Warning Detail
- Report Schedules

Users who only want BMS polling and MQTT publishing do not need Telegram notifications enabled.

## Telegram optional use

Telegram is optional.

If Telegram is disabled or not configured, the add-on can still:

- read the BMS
- publish MQTT topics
- publish Home Assistant discovery
- show the web UI
- show Status, Dashboard, Diagnostics and Backups

Telegram is only needed for external alert/report messages.

Recommended optional Telegram settings:

- notify_enabled
- notify_startup
- notify_disconnect
- notify_stale_data
- notify_stale_recovery
- notify_soc_low
- notify_soc_high
- notify_warnings
- notify_daily_summary
- notify_delta_report

## Home Assistant automations

If built-in Telegram notifications are enabled, old Home Assistant automations for the same alerts may become redundant.

Examples that may be disabled if they only duplicate Telegram alerts:

- BMS Disconnected Alert
- BMS Recovered Alert
- BMS Shutdown Alert
- BMS Started Alert

Keep Home Assistant automations if they do extra actions, such as mobile push notifications, lights, sirens, dashboards, logbooks or non-Telegram workflows.

## Config validation

The Config tab validates important fields before saving.

### Required text fields

- mqtt_host
- mqtt_user
- mqtt_base_topic
- mqtt_ha_discovery_topic
- connection_type
- bms_serial

### Whole number fields

- mqtt_port
- state_force_republish_seconds
- warn_force_republish_seconds
- bms_baudrate
- scan_interval
- debug_output
- zero_pad_number_cells
- zero_pad_number_packs
- notify_cell_delta_warn_mv
- notify_temp_high_warn_c
- notify_temp_low_warn_c
- notify_retry_count
- notify_stale_data_seconds
- notify_stale_data_repeat_seconds

### Decimal / number fields

Decimal comma is allowed where applicable, for example 4,2 or 4.2.

- notify_cell_high_warn_voltage
- notify_cell_low_warn_voltage
- notify_soc_high_threshold
- notify_soc_high_reset
- notify_soh_threshold

### Comma-separated list fields

- notify_soc_low_thresholds

Valid example:

```text
75,50,25,15
```

Invalid examples:

```text
75,abc,25
75%,50%,25%
75 50 25
```

### Time fields

Time fields must use 24-hour HH:MM format.

- notify_daily_summary_time
- notify_delta_report_time
- notify_delta_window_start
- notify_delta_window_end

Valid examples:

```text
19:00
10:15
00:00
```

Invalid examples:

```text
7pm
25:99
10h15
abc
```

### Logical validation checks

- notify_soc_high_reset must be lower than notify_soc_high_threshold
- notify_cell_low_warn_voltage must be lower than notify_cell_high_warn_voltage
- connection_type must be Serial

## Backups and restore

The add-on creates configuration backups before web config saves and before restores.

Backup features include:

- create config backup
- delete backups
- backup summary
- backup compare / restore preview
- download all backups ZIP
- restore protection

Recommended backup retention is 10 backups to avoid clutter while still keeping enough rollback history.

## Restart Add-on behaviour

The Restart Add-on button in the Config header uses the Home Assistant Ingress-safe relative route:

```text
restart-addon
```

The Flask backend route remains:

```text
/restart-addon
```

This avoids a 404 under Home Assistant Ingress.

## SOC high startup behaviour

If the monitor starts while a pack is already at or above the high SOC threshold, startup alert behaviour is controlled by:

```yaml
notify_soc_high_on_startup
```

When false, the add-on suppresses high SOC alerts that are already active during startup.

Example log:

```text
High SOC startup alert suppressed for Pack 01: SOC 98.0% >= 98.0%
```

This means the app saw the condition and intentionally suppressed it according to the setting.

## Slave serial limitation

The current decoded Pace C2 serial-number response exposes one unique serial number only.

Observed response:

```text
*HL2107001569*      *HL2107001569*
```

The add-on should therefore show:

```text
Pack 01 / Master: serial reported by BMS
Pack 02 / Slave: Not reported separately
```

Slave live data remains fully supported, including:

- cells
- temperatures
- voltage
- current
- capacity
- SOC
- SOH
- cycles
- warnings
- FET states

## Release test checklist

Before tagging a release, test:

### Config

- Config tab loads
- Required / Optional badges show
- Info buttons open original modal style
- Notification Thresholds info shows text
- Report Schedules info shows text
- Save Configuration works
- Create Backup works
- Restart Add-on works
- Download Sanitized YAML works
- Format Help expands/collapses
- Validation blocks invalid numbers/times/lists

### Status

- Status loads
- Pack 01 and Pack 02 show correctly
- Warning Intelligence appears
- Refresh Status works
- No duplicate or broken labels

### Dashboard

- Dashboard loads
- Pack comparison cards show correctly
- Refresh Dashboard works
- Charts have data when MQTT retained values exist

### Diagnostics

- Diagnostics loads
- Refresh Diagnostics works
- Battery Configuration shows Master / Slave
- Detailed Cell Data shows 13 cells per pack
- Download Diagnostic Report works
- Download Support Bundle ZIP works

### Backups

- Create Backup works
- Delete Backup works
- Delete twice does not cause Method Not Allowed
- Download All Backups ZIP works
- Restore preview/compare works

### Add-on logs

Run for at least 15 to 30 minutes and confirm:

- Analog read OK
- Warn read OK
- No recurring ERROR in app
- No Internal Server Error
- No MQTT reconnect loop
- No Telegram spam

## Important security reminder

Do not publish or share:

- telegram_bot_token
- telegram_chat_id
- mqtt_password
- full support bundles with secrets
- screenshots showing sensitive values

telegram_chat_id should use password schema if it should be redacted on the native Home Assistant add-on Options page.
