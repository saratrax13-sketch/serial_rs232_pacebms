## 2.6.25 - 2026-05-17

### Added
- Added `notify_warning_repeat_seconds` to the web Config tab under Notification Thresholds.
- Added validation for `notify_warning_repeat_seconds`.
- Added help text for `notify_warning_repeat_seconds`.
- Added `CONFIG_YAML_PATCH_2.6.25.md`.

### Behaviour
- Controls how often the same active BMS warning may repeat on Telegram.
- Recommended default is `1800` seconds.
- Web validation allows `60` to `86400` seconds.

### Notes
- This builds on 2.6.24 Warning Deduplication and Repeat Cooldown.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
