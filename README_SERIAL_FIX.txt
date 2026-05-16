Pace BMS Web UI BMS Serial Fix

This fixes BMS Serial showing as Unknown on the Live Status page.

Cause:
- The Live Status page reads MQTT values as a new subscriber.
- bms_sn may not be retained on older monitor versions.
- The retained bms_status payload already contains bms_sn, so web_config.py now uses it as a fallback.

Copy into repo:
- web_config.py

Recommended version:
- Bump config.yaml to version: "2.0.24"

Recommended changelog entry:

## 2.0.24 - 2026-05-16

### Fixed
- Fixed Live Status showing BMS Serial as Unknown when the direct bms_sn MQTT topic is not retained.
- Added fallback to read BMS serial and version from the retained bms_status payload.

Commit:
git add web_config.py config.yaml CHANGELOG.md
git commit -m "Fix BMS serial display in Live Status"
git push
