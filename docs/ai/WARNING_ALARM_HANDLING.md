# Warning / Alarm Handling

Use this guide when changing warning, alarm, protection or Telegram alert behavior.

## Core Rules

- Separate BMS warning flags from app-calculated warning references.
- Do not clear a BMS warning in the app unless the BMS flag clears.
- Avoid repeated Telegram notifications for the same ongoing alarm.
- Do not hide active BMS warnings just because current measured values are below app references.
- Explain when the BMS warning is active below the configured reference.

## Notify When

Send or allow Telegram notification when:

- warning becomes active
- warning changes type/family
- severity escalates
- highest cell changes meaningfully enough to change interpretation
- configured repeat cooldown expires
- warning clears

## Recommended Telegram Warning Fields

Include enough detail for troubleshooting:

- pack number
- severity
- warning type/family
- highest cell number and voltage
- lowest cell number and voltage
- cell delta
- pack voltage
- SOC
- SOH
- cycles where available
- time
- whether warning came from BMS flag or app threshold/reference
- measured value vs configured/profile reference
- margin to reference

## Deduplication

Normalize equivalent warning text into a stable warning family.

Examples that should be treated as one family:

```text
Above cell voltage
cell 8 Above upper limit
cell 8 Above upper limit, Above cell voltage
```

Duplicate-suppressed warnings should be quiet in normal logs.

## Current Code Pointers

- `bms_monitor.py`
  - warning family normalization
  - warning severity classification
  - warning repeat state
- `bms_notify.py`
  - Telegram warning detail
  - daily warning observations
- `web_config.py`
  - Warning Intelligence
  - clear warning suppression action
- `docs/ai/ALERT_RULES.md`

