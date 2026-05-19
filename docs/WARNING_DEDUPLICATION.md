# Warning Deduplication and Repeat Cooldown

## Purpose

The BMS can report the same active warning with slightly different wording on each warning read.

![Telegram warning example](screenshots/Telegram1.png)

![Tech Status warning intelligence](screenshots/Tech%20Status%20p1.png)

![Logs warning view](screenshots/Logs.png)

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

The Tech Status Warning Intelligence cards still show the BMS warning context, measured values, reference checks, interpretation and suggested action even when Telegram repeats are being suppressed.

No BMS protocol changes were made.
No BMS write/control commands were added.


## 2.6.25 update

The cooldown is now visible/configurable in the web Config tab as:

```yaml
notify_warning_repeat_seconds
```

Recommended value:

```yaml
1800
```

Valid range:

```text
60 to 86400 seconds
```
