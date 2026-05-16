# v2.0.36 — Stable Home Assistant Pace BMS Add-on Release

## Highlights

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

## Safety

- The add-on remains read-only to the BMS.
- No BMS settings are changed.
- No protection thresholds are written to the BMS.
- No FET control commands are sent.

## Notes

- Stale-data detection is based on successful BMS reads, not whether values changed.
- A battery value staying the same is not considered stale if the BMS is still replying.
- Warning thresholds in the config are notification reference values only.
- This is a release polish update and does not require Python logic changes.

## Recommended Post-Install Checks

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
