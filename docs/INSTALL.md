# Installation Guide

## Home Assistant Add-on Installation

1. Open Home Assistant.
2. Go to **Settings**.
3. Open **Add-ons**.
4. Open the **Add-on Store**.
5. Click the three-dot menu.
6. Select **Repositories**.
7. Add the repository URL:

```text
https://github.com/saratrax13-sketch/serial_rs232_pacebms
```

8. Install the Pace BMS add-on.
9. Configure the add-on.
10. Start the add-on.

## After Installation

Check the add-on logs for:

```text
MQTT connected
Startup notification published
Analog read OK
Warn read OK
```

Open the web UI and confirm:

```text
Availability: online
Monitor: running
Data Stale: OFF
```

## Serial Connection Notes

For serial use, select the correct serial device path in the add-on configuration.

A stable path is recommended, for example:

```text
/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_D-if00-port0
```

## MQTT

Make sure MQTT is running and reachable from the add-on.

Recommended:

```yaml
mqtt_retain_state: true
state_force_republish_seconds: 300
warn_force_republish_seconds: 300
```

## Telegram

Telegram notifications are optional.

You need:

- Telegram bot token
- Telegram chat ID

Use the web UI **Test Telegram** button to confirm it works.
