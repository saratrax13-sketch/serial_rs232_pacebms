# Config Reference

## Required sections

### BMS Connection

Required for RS232 BMS reading.

Fields:

- connection_type
- bms_connection_mode
- bms_serial
- bms_baudrate
- scan_interval

### History & Live Data

Required for serial-first web UI and local metrics history.

Fields:

- ui_data_source
- metrics_enabled
- history_sample_seconds
- history_cell_sample_seconds
- history_retention_days
- history_event_retention_days

### MQTT

Optional output/fallback for MQTT and Home Assistant discovery.

Fields:

- mqtt_enabled
- mqtt_host
- mqtt_port
- mqtt_user
- mqtt_password
- mqtt_base_topic
- mqtt_ha_discovery
- mqtt_ha_discovery_topic
- mqtt_retain_state
- state_force_republish_seconds
- warn_force_republish_seconds

### Advanced

Required for base runtime defaults and topic formatting.

Fields:

- debug_output
- zero_pad_number_cells
- zero_pad_number_packs

## Optional sections

### Telegram

Optional external notification delivery.

### Notifications

Optional alert category toggles.

### Notification Thresholds

Optional alert trigger thresholds and stale-data timing.

### Warning Detail

Optional extra data included in warning messages.

### Scheduled Reports

Optional scheduled Telegram report times.

### Battery Profile & References

Optional read-only reference values used to explain BMS warnings in the UI and Telegram. These values are saved as add-on options only and are never written to the BMS.

This card also includes optional read-only layout checks and estimate fallback values:

- expected_cell_count
- expected_pack_count
- capacity_fallback_enabled
- capacity_per_pack_ah

Use `0` for expected counts when the layout should be fully auto/detected.

These values do not force BMS parsing. They only help the UI show when the detected layout differs from what the installer expected.

Capacity fallback is used only for runtime/charge estimates when the BMS does not report valid capacity. Valid BMS-reported capacity always wins.

![Battery profile references](screenshots/Config%20p2.png)

The Battery Profile & Alert References table shows:

- profile reference value
- measured value from the latest retained data
- user-defined alert value
- whether Telegram alerting is enabled for that reference
- which warning detail is included in the message

The report schedule fields are shown in the final Config section:

![Scheduled report settings](screenshots/Config%20p3.png)

## Format rules

### Comma-separated thresholds

Use numbers only:

```text
75,50,25,15
```

### Time values

Use 24-hour HH:MM:

```text
19:00
10:15
00:00
```

### Decimal voltage values

Both decimal dot and decimal comma are accepted:

```text
4.20
4,20
```


## Warning repeat cooldown

`notify_warning_repeat_seconds` controls how often the same active BMS warning may repeat on Telegram.

Recommended default:

```yaml
notify_warning_repeat_seconds: 1800
```

This means repeat at most every 30 minutes for the same active warning family.
