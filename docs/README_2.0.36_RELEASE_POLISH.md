# PaceBMS 2.0.36 Release Polish Notes

This is a release polish update for the PaceBMS Home Assistant add-on.

No BMS protocol changes were made.

No Python monitor logic changes are required.

No BMS write/control commands were added.

The project remains read-only to the BMS.

---

## Current Stable Feature Set

As of version `2.0.36`, the add-on includes:

- Pace BMS RS232 / UART ASCII read-only monitoring
- Home Assistant MQTT Discovery
- MQTT retained battery state topics
- Retained BMS identity topics
- Direct Telegram notifications
- BMS disconnect and recovery notifications
- Stale-data detection
- Stale-data recovery notifications
- Detailed BMS warning Telegram messages
- Configurable warning reference values
- Auto cell-count detection
- Auto multi-pack detection when DIP/address settings are correct
- Home Assistant Ingress web UI
- Live Status page
- Test Telegram button
- Test MQTT button
- Last Events / Status History
- Read-only BMS safety model

---

## Recommended Post-Install Checks

After updating to `2.0.36`, confirm:

```text
1. Add-on starts correctly.
2. MQTT connects.
3. Home Assistant sensors update.
4. Web UI opens.
5. Overall Status shows correctly.
6. Data Stale shows OFF.
7. Analog Age and Warning Age update.
8. Last Events shows startup events.
9. Test Telegram button works.
10. Test MQTT button works.
11. Stop add-on sends Monitor Stopped notification.
12. Battery-side serial disconnect triggers BMS Disconnected notification.
13. Reconnect triggers BMS Reconnected notification.
```

---

## Public GitHub Safety Check

Before publishing a public release, confirm that no real secrets are committed.

Check these files carefully:

```text
config.yaml
README.md
CHANGELOG.md
```

Do not commit real values for:

```text
telegram_bot_token
telegram_chat_id
mqtt_password
mqtt_user, if private
private IP addresses, if you do not want them public
```

Use placeholders such as:

```yaml
telegram_bot_token: "YOUR_TELEGRAM_BOT_TOKEN"
telegram_chat_id: "YOUR_TELEGRAM_CHAT_ID"
mqtt_user: "YOUR_MQTT_USER"
mqtt_password: "YOUR_MQTT_PASSWORD"
```

---

## Suggested GitHub Release Title

```text
v2.0.36 — Stable Home Assistant Pace BMS Add-on Release
```

---

## Suggested GitHub Release Summary

Version `2.0.36` is a release polish update for the PaceBMS Home Assistant add-on.

This release consolidates the recent work on direct Telegram notifications, Home Assistant Ingress web UI, live MQTT status, stale-data detection, detailed warning messages, and Last Events / Status History.

The monitor remains read-only to the BMS and does not send write/control commands.

---

## Suggested GitHub Release Notes

```markdown
## v2.0.36 — Stable Home Assistant Pace BMS Add-on Release

### Highlights
- Read-only Pace BMS RS232 / UART ASCII monitoring.
- Home Assistant MQTT Discovery.
- Direct Telegram notifications from Python.
- Home Assistant Ingress web UI.
- Live Status dashboard.
- Test Telegram and Test MQTT buttons.
- Stale-data detection and recovery alerts.
- Last Events / Status History.
- Auto cell-count detection.
- Auto multi-pack detection when DIP switch addressing is configured correctly.

### Safety
- The add-on remains read-only to the BMS.
- No BMS settings are changed.
- No protection thresholds are written to the BMS.
- No FET control commands are sent.

### Notes
- Stale-data detection is based on successful BMS reads, not whether values changed.
- A battery value staying the same is not considered stale if the BMS is still replying.
- Warning thresholds in the config are notification reference values only.
```

---

## Recommended Version

```yaml
version: "2.0.36"
```
