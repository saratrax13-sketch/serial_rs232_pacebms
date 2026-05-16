## 2.0.35 - 2026-05-16

### Added
- Added persistent Last Events / Status History section to the Home Assistant Ingress web UI.
- Added local `/data/events.json` event history storage.
- Added monitor events for startup, shutdown, disconnect, recovery, stale data and fresh data recovery.
- Added web UI events for Test Telegram and Test MQTT actions.
- Event history keeps the latest 50 events and displays the latest 10 in the web UI.

### Notes
- Event history is local to the add-on data folder.
- This feature is read-only to the BMS.
- No BMS protocol or control commands were added.
