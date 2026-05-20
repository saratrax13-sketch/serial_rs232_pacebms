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
- the same warning escalates in severity
- the same warning remains active and the severity-aware repeat cooldown has passed
- the warning clears

Duplicate messages within the cooldown period are suppressed.

## Severity-aware cooldowns

The current configuration uses severity-aware repeat timing:

```yaml
notify_warning_repeat_seconds: 1800
notify_warning_repeat_caution_seconds: 21600
notify_warning_repeat_warning_seconds: 3600
notify_warning_repeat_critical_seconds: 900
```

Meaning:

- `notify_warning_repeat_seconds` is the legacy fallback repeat interval.
- `notify_warning_repeat_caution_seconds` is for low-risk ongoing warnings.
- `notify_warning_repeat_warning_seconds` is for warning-level conditions.
- `notify_warning_repeat_critical_seconds` is for protection, fault or measured out-of-reference conditions.

All values are seconds. The web Config tab validates these fields and recommends values of at least 60 seconds.

## Warning policy

The Config tab includes `notify_bms_warning_policy`.

The default policy is:

```text
Alert on user reference exceeded, plus BMS critical/protection
```

That means:

- BMS warnings remain visible in the UI.
- Telegram can ignore lower-severity BMS internal warnings when current measured values are still inside the configured user references.
- Telegram still alerts when a user reference is exceeded.
- Telegram still alerts for BMS protection or critical/fault conditions.
- Telegram clear messages can still report when an active warning clears.

This keeps the app honest about what the BMS reports while reducing noise from BMS internal thresholds that are lower than the user's configured alert references.

## Important note

This does not hide the warning in the app or MQTT. It only reduces repeated Telegram messages for the same active condition.

The Tech Status Warning Intelligence cards still show:

- BMS-reported warning state
- user alert reference checks
- measured values
- Telegram decision
- interpretation
- suggested action

This remains visible even when Telegram repeats are suppressed or filtered by warning policy.

No BMS protocol changes were made.
No BMS write/control commands were added.
