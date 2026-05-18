# First-Time Setup Guide

## Basic MQTT-only setup

Use this mode if you only want to read the battery BMS and publish values to MQTT/Home Assistant.

Required Config sections:

1. BMS Connection
2. MQTT
3. Advanced

Optional sections can be left disabled or unchanged.

### Step 1: Configure BMS Connection

Set:

```yaml
connection_type: Serial
bms_serial: /dev/serial/by-id/your-usb-serial-device
bms_baudrate: 9600
scan_interval: 5
```

### Step 2: Configure MQTT

Set:

```yaml
mqtt_host: your_mqtt_broker_ip
mqtt_port: 1883
mqtt_user: your_user
mqtt_password: your_password
mqtt_base_topic: pacebms
mqtt_ha_discovery: true
mqtt_ha_discovery_topic: homeassistant
mqtt_retain_state: true
```

### Step 3: Keep Advanced defaults

Recommended:

```yaml
debug_output: 0
zero_pad_number_cells: 2
zero_pad_number_packs: 2
```

### Step 4: Start the add-on

Confirm logs show:

```text
BMS serial connected
MQTT connected
Analog read OK
Warn read OK
```

### Step 5: Confirm UI data

Open the web UI and check:

- Dashboard tab: user battery confidence values should be visible.
- Tech Status tab: Overall Status should not be Unknown once MQTT retained values are available.
- Tech Status tab: Monitoring Health should show whether heartbeat, MQTT monitor state, analog age and warning age are healthy.
- Setup tab: Setup Checklist should show Basic Required items as ready.
- Diagnostics tab: use this when you need a support report or deeper troubleshooting.

### Step 6: Capture setup screenshots

For support or release notes, capture these screens:

- Home Assistant add-on Configuration tab, with secrets hidden.
- Pace BMS Dashboard tab showing the User Dashboard.
- Pace BMS Tech Status tab showing Overall Status and Monitoring Health.
- Pace BMS Setup tab showing Setup Checklist.
- Test Full Monitoring result.

See `docs/screenshots/README.md` for screenshot names and privacy guidance.

## Optional Telegram monitoring setup

Enable this only if you want Telegram messages.

Configure:

```yaml
telegram_bot_token: your_token
telegram_chat_id: your_chat_id
notify_enabled: true
```

Then enable only the notifications you want.

## Recommended alert settings

Typical settings:

```yaml
notify_startup: true
notify_disconnect: true
notify_stale_data: true
notify_stale_recovery: true
notify_soc_low: true
notify_soc_high: true
notify_warnings: true
```

Optional reporting:

```yaml
notify_daily_summary: true
notify_delta_report: true
```

## Disable duplicate Home Assistant automations

If the add-on sends Telegram alerts, disable older Home Assistant automations that do the same thing.

Keep HA automations only if they perform other actions like push notifications, lights, sirens or logbook entries.
