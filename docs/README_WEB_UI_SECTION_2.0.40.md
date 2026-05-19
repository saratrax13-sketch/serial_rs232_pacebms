## Home Assistant Ingress Web UI

The add-on includes a read-only Home Assistant Ingress web UI.

The web UI gives a quick operational view of the Pace BMS monitor without needing to open MQTT topics or Home Assistant entity lists.

### Dashboard

![Dashboard](screenshots/Dashboard.png)

### Tech Status

![Tech Status warning intelligence](screenshots/Tech%20Status%20p1.png)

![Tech Status pack detail](screenshots/Tech%20Status%20p2.png)

![Tech Status comparison charts](screenshots/Tech%20Status%20p3.png)

### Setup

![Setup](screenshots/Setup.png)

### Config

![Config](screenshots/Config.png)

![Config thresholds and references](screenshots/Config%20p2.png)

![Config scheduled reports](screenshots/Config%20p3.png)

### Diagnostics

![Diagnostics overview](screenshots/Diagnostics%20p1.png)

![Diagnostics cell data](screenshots/Diagnostics%20p2.png)

### Events, Backups and Logs

![Events](screenshots/Events.png)

![Backups](screenshots/Backups.png)

![Logs](screenshots/Logs.png)

### Telegram Examples

![Telegram warning example](screenshots/Telegram1.png)

![Telegram detail example](screenshots/Telegram2.png)

![Telegram report example](screenshots/Telegram3.png)

![Telegram recovery example](screenshots/Telegram4.png)

### Web UI Sections

The web UI includes:

- Dashboard battery confidence
- Tech Status warning intelligence and pack details
- Setup checklist and safe test buttons
- Config grouped add-on options
- Diagnostics support proof and cell data
- Events history
- Backups for add-on configuration
- Logs with Important, Battery reads and Everything views

### Warning Explanation

The web UI separates two important concepts:

1. **BMS internal warning active**
2. **Configured reference threshold check**

This matters because the BMS may set an internal warning bit before the configured reference threshold is exceeded.

### Read-Only Safety

The web UI is read-only to the BMS.

The buttons only test external services:

- Test Telegram sends a Telegram test message.
- Test MQTT checks broker connectivity.
- Test Full Monitoring checks MQTT, Telegram configuration and notification thresholds without sending a Telegram message.

No BMS commands are sent from the web UI.
No thresholds are written to the BMS.
No FET control commands are sent.
