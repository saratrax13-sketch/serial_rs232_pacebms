# Warning Deduplication and Repeat Cooldown

## Purpose

The BMS can report the same active warning with slightly different wording on each warning read.

Example:

```text
Above cell voltage
cell 8 Above upper limit, Above cell voltage
Above cell voltage
```

These represent the same ongoing warning family and should not spam Telegram every few seconds.

## Behaviour

The monitor now normalizes warning text into a warning family per pack.

Examples that are treated as the same family:

```text
Above cell voltage
cell 8 Above upper limit
cell 8 Above upper limit, Above cell voltage
```

Normalized family:

```text
Above cell voltage
```

## Telegram behaviour

The add-on sends a Telegram message when:

- a warning first appears
- a different warning family appears
- the same warning remains active and the repeat cooldown has passed
- the warning clears

Duplicate messages within the cooldown period are suppressed.

## Default cooldown

The default repeat cooldown is:

```yaml
notify_warning_repeat_seconds: 1800
```

That is 30 minutes.

This option is optional. If it is not present in `config.yaml`, the app uses the default.

## Recommended future config.yaml option

To make the cooldown visible in the native Home Assistant add-on options screen, add:

```yaml
options:
  notify_warning_repeat_seconds: 1800

schema:
  notify_warning_repeat_seconds: int
```

## Important note

This does not hide the warning in the app or MQTT. It only reduces repeated Telegram messages for the same active condition.

No BMS protocol changes were made.
No BMS write/control commands were added.
