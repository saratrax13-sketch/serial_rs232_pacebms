# First-Time Setup

Use this checklist after installation to get the add-on into a known-good state.

Release: `2.10.0`

The full guide is [docs/FIRST_TIME_SETUP.md](docs/FIRST_TIME_SETUP.md).

## Required Setup

- Set `connection_type` to `Serial`.
- Set `bms_connection_mode` to `Serial`.
- Set `bms_serial` to a stable serial path, preferably `/dev/serial/by-id/...`.
- Set `bms_baudrate` to `9600` unless your BMS requires otherwise.
- Keep `ui_data_source` as `auto`.
- Keep `metrics_enabled` enabled for local history graphs and reports.

## Optional Setup

- Enable MQTT only when Home Assistant MQTT entities or MQTT fallback are needed.
- Enable Telegram only when direct alerting is needed.
- Keep `debug_output` at `0` for normal use.

## First Checks

After starting the add-on, confirm logs show:

```text
BMS serial connected
Analog read OK
Warn read OK
```

Then open the web UI and check:

- Dashboard shows Battery Confidence values.
- Tech Status shows detected packs and Warning Intelligence.
- Diagnostics shows the expected cell count.
- History shows local SQLite trend data after a few minutes.
- Setup checklist shows Basic Required items as ready.

## Support Screenshots

When asking for support, hide secrets and capture:

- Home Assistant add-on Configuration tab.
- Dashboard.
- Tech Status.
- History.
- Diagnostics.
- Setup checklist.
- Logs tab with the relevant filter.

Redact Telegram tokens, Telegram chat IDs, MQTT passwords, Home Assistant usernames and battery serial numbers before sharing screenshots publicly.
