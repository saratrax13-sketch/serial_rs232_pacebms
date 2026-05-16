## 2.1.1 - 2026-05-16

### Changed
- Improved Home Assistant Ingress web UI responsiveness.
- Config and Events tabs no longer fetch a live MQTT snapshot before rendering.
- Live MQTT status is now fetched only on the Status tab and `/api/status` endpoint.
- Reduced MQTT snapshot wait time to make the Status tab feel faster.

### Notes
- This is a web UI performance polish release.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
- The add-on remains read-only to the BMS.
