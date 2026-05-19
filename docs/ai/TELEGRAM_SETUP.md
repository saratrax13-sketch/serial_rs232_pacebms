# Telegram Setup

Use this guide when changing Telegram configuration, tests or alert behavior.

## Supported Settings

The project should support:

- bot token
- chat ID
- enable/disable notifications
- startup notification toggle
- disconnect/stale/recovery toggles
- warning toggle
- FET toggle
- warning cooldowns
- clear warning suppression/cooldown state
- test notification

## Placeholder Values

Placeholder values are not configured values.

Examples:

```text
YOUR_TELEGRAM_BOT_TOKEN
YOUR_TELEGRAM_CHAT_ID
```

Do not call Telegram when placeholders are present.

## Anti-Spam Rules

Telegram should not spam repeated messages while the same condition remains active.

Use:

- warning family normalization
- severity-aware repeat intervals
- stale-data repeat interval
- clear/recovery messages
- startup suppression for configured startup-only noise where applicable

## Test Behavior

Test Telegram may send a Telegram test message.

Test Full Monitoring must not send a Telegram message and must not send BMS commands. It should dry-check MQTT, Telegram configuration and notification thresholds.

## Current Code Pointers

- `bms_notify.py`
  - Telegram send
  - placeholder checks
  - warning/detail/report messages
- `web_config.py`
  - Test Telegram
  - Test Full Monitoring
  - setup checklist
  - clear warning suppression
- `tests/test_core_behaviour.py`
  - placeholder and full monitoring tests

