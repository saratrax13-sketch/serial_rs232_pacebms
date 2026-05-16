# Configuration Guide

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
