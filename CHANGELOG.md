## v2.2.9 — Stable Web Config + Status UI Release

This release is a stable milestone for the Pace BMS RS232 Monitor Home Assistant add-on.

### Highlights

- Read-only Pace BMS RS232 monitoring
- Home Assistant MQTT Discovery
- Direct Telegram notifications
- Web UI with Status, Config and Events tabs
- Direct Home Assistant add-on config saving from the web UI
- Restart Add-on button
- Test Telegram button
- Test MQTT button
- Event history with export options
- Stale-data monitoring
- Warning explanation with reference checks
- Config help popups
- Home Assistant add-on icon
- Removed unused `bms_ip` and `bms_port` config fields

### Web UI

The web UI now includes:

- Status tab for live BMS status
- Config tab for editable add-on settings
- Events tab for recent monitor events
- Help buttons on config cards
- Changed-field highlighting
- Revert card / discard unsaved changes tools

### Safety

- The monitor remains read-only to the BMS.
- No BMS settings are changed.
- No BMS thresholds are written.
- No charge/discharge FET control commands are sent.
- Web config saving only writes Home Assistant add-on options.

### Notes

After updating, confirm:

- Add-on starts normally
- MQTT connects
- Web UI opens
- Status tab shows live data
- Config tab saves correctly
- Events tab works
- Telegram test works
- MQTT test works