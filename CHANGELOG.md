## 2.6.24 - 2026-05-17

### Added
- Added BMS warning deduplication before Telegram notification handling.
- Added warning-family normalization so slight wording changes are treated as the same active condition.
- Added repeat cooldown support using optional config value `notify_warning_repeat_seconds`.
- Added warning clear handling per pack.
- Added `docs/WARNING_DEDUPLICATION.md`.

### Behaviour
- Same active warning family is no longer sent repeatedly every warning read.
- A new Telegram warning is sent when a warning first appears.
- A repeat Telegram warning is allowed only after the cooldown period.
- A clear notification is sent when the warning returns to normal.

### Default
- `notify_warning_repeat_seconds` defaults to `1800` seconds if not configured.

### Notes
- This is Telegram spam-control logic only.
- MQTT warning topics are still published normally.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
