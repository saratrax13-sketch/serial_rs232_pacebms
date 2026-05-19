# Config Rules

Configuration is Home Assistant add-on configuration only. It must not write to the BMS.

## Required Alignment

Every config option should align across:

- `config.yaml` `options`
- `config.yaml` `schema`
- `web_config.GROUPS`
- `web_config.DEFAULT_OPTION_VALUES`
- UI/help text when user-facing

Avoid duplicate group keys.

## Sensitive Fields

Sensitive fields include:

- `telegram_bot_token`
- `telegram_chat_id`
- `mqtt_password`

When sensitive fields are blank in the Web UI form, keep the saved value. Blank means "leave unchanged", not "clear secret".

## Save Behavior

The Config tab saves Home Assistant add-on options only.

After saving, tell the user that monitor runtime changes require an add-on restart.

Create a config backup before save/restore where the existing backup flow supports it.

## Grouping Rules

Keep cards grouped by purpose:

- BMS Connection: serial path, baud, scan interval
- MQTT: broker, discovery, retain and republish behavior
- Advanced: debug/topic formatting defaults
- Telegram: credentials and delivery toggles
- Notifications: alert category toggles
- FET Notifications: FET-specific alert behavior
- Notification Thresholds: SOC/SOH/stale/repeat thresholds
- Warning Detail: contents included in detailed warning explanations
- Scheduled Reports: daily summary and delta report timing
- Battery Profile & References: read-only profile/reference table

`daily_energy_current_deadband_a` belongs at the bottom of Scheduled Reports.

Battery Profile & References belongs at the bottom of Config and should be wide enough to avoid horizontal scrolling where possible.

## Decimal Handling

Users may enter decimal comma values such as `0,2` or `3,51`. Preserve existing handling that accepts comma and dot where applicable.

