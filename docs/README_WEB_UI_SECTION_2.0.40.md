## Home Assistant Ingress Web UI

The add-on includes a read-only Home Assistant Ingress web UI.

The web UI gives a quick operational view of the Pace BMS monitor without needing to open MQTT topics or Home Assistant entity lists.

![Pace BMS Web UI](docs/screenshots/web-ui-2.0.39-warning-reference.png)

### Web UI Sections

The web UI includes:

- Overall Status
- Detected Battery Layout
- Test Telegram button
- Test MQTT button
- Live Status
- Pack cards
- BMS internal warning explanation
- Reference threshold checks
- Notification/configuration overview
- Last Events / Status History

### Overall Status

The Overall Status card summarizes the current condition of the monitor:

| Status | Meaning |
|---|---|
| Healthy | BMS is online, data is fresh, and no BMS warnings are active |
| Warning | BMS is online and fresh, but one or more BMS warning bits are active |
| Stale | Monitor is running, but fresh BMS reads have not updated within the configured stale-data time |
| Offline | Monitor or BMS communication is offline |

### Warning Explanation

The web UI separates two important concepts:

1. **BMS internal warning active**
2. **Configured reference threshold check**

This matters because the BMS may set an internal warning bit before the configured reference threshold is exceeded.

Example:

```text
BMS internal warning active:
Warning State 1: Above cell volt warn | Above total volt warn

Reference Check:
- Cell reference not exceeded: no cell is above 4.20 V
- Pack reference not exceeded: pack voltage is not above 54.60 V
```

This means the BMS is reporting a warning, but the configured notification reference value has not been exceeded.

### Read-Only Safety

The web UI is read-only to the BMS.

The buttons only test external services:

- Test Telegram sends a Telegram test message.
- Test MQTT checks broker connectivity.

No BMS commands are sent from the web UI.
No thresholds are written to the BMS.
No FET control commands are sent.
