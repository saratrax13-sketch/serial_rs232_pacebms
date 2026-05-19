# Config Reference

## Required sections

### BMS Connection

Required for RS232 BMS reading.

Fields:

- connection_type
- bms_serial
- bms_baudrate
- scan_interval

### MQTT

Required for MQTT and Home Assistant discovery.

Fields:

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

![Battery profile references](screenshots/Config%20p2.png)

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
