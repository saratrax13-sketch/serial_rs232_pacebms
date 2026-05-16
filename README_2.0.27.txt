Pace BMS 2.0.27 - Web UI tools and live read timestamps

Files:
- bms_monitor.py
- web_config.py
- templates/index.html

Recommended version:
version: "2.0.27"

Changelog entry:

## 2.0.27 - 2026-05-16

### Added
- Added Test Telegram button to the Home Assistant Ingress web UI.
- Added Test MQTT button to the Home Assistant Ingress web UI.
- Added retained MQTT monitor status topics under `pacebms/monitor/`.
- Added last successful analog read timestamp to the web UI.
- Added last successful warning read timestamp to the web UI.
- Added monitor state tile to the web UI.

### Notes
- Test buttons do not write to the BMS.
- Monitor status topics are MQTT-only status telemetry.

Commit:
git add bms_monitor.py web_config.py templates/index.html config.yaml CHANGELOG.md
git commit -m "Add web UI test buttons and monitor timestamps"
git push
