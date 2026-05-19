# Configuration Guide

The Config tab saves Home Assistant add-on options only. It does not write thresholds, settings or FET commands to the BMS.

The current Config layout groups the settings by task:

- **BMS Connection**, **MQTT** and **Advanced** are the required baseline settings for polling and Home Assistant discovery.
- **Telegram**, **Notifications**, **FET Notifications** and **Scheduled Reports** control optional direct Telegram messages.
- **Notification Thresholds**, **Battery Profile & Alert References** and **Warning Detail** control how warnings are explained and when Telegram alerts are allowed.

![Config required and notification settings](screenshots/Config.png)

![Config thresholds and battery references](screenshots/Config%20p2.png)

![Config scheduled reports](screenshots/Config%20p3.png)

## Important Settings

### MQTT

```yaml
mqtt_host: "192.168.10.16"
mqtt_port: 1883
mqtt_user: "YOUR_MQTT_USER"
mqtt_password: "YOUR_MQTT_PASSWORD"
mqtt_base_topic: "pacebms"
mqtt_retain_state: true
```

### Serial BMS Connection

```yaml
connection_type: "Serial"
bms_serial: "/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_D-if00-port0"
bms_baudrate: 9600
scan_interval: 5
```

### Telegram

```yaml
notify_enabled: true
telegram_bot_token: "YOUR_TELEGRAM_BOT_TOKEN"
telegram_chat_id: "YOUR_TELEGRAM_CHAT_ID"
```

### Disconnect

```yaml
notify_disconnect: true
notify_retry_count: 1
```

For serial monitoring, `notify_retry_count: 1` is recommended.

### Stale Data

```yaml
notify_stale_data: true
notify_stale_recovery: true
notify_stale_data_seconds: 120
notify_stale_data_repeat_seconds: 1800
```

This is based on successful BMS reads, not whether values changed.

### Warning Reference Values

```yaml
notify_cell_high_warn_voltage: 4.20
notify_cell_low_warn_voltage: 3.00
notify_cell_delta_warn_mv: 100
notify_temp_high_warn_c: 55
notify_temp_low_warn_c: 0
```

These are notification/display reference values only.

They do not write to the BMS.

Battery profile references are shown beside measured values and user-defined alert references. Auto detection uses the detected cell count to choose the closest built-in reference profile; custom references use the values saved in the add-on options.

The Battery Profile & Alert References card shows profile reference, measured value, user-defined value, Telegram alert toggle and message detail option per reference line. These are explanation and notification settings only; they are never written to the BMS.

## Debugging

Normal:

```yaml
debug_output: 0
```

Raw protocol troubleshooting:

```yaml
debug_output: 3
```

Return to `0` after troubleshooting.
