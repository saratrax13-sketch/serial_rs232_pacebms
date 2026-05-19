# Capacity Parsing

Use this guide when remaining capacity, full capacity, design capacity, Ah or kWh values look wrong.

## Required Checks

Confirm the source unit:

- mAh
- Ah
- Wh
- kWh

Confirm:

- scaling factor
- per-pack vs combined total
- dashboard rounding
- whether the BMS value is reported, estimated or unavailable

## mAh To Ah

Use:

```text
Ah = mAh / 1000
```

Example:

```text
207550 mAh = 207.55 Ah = 208 Ah rounded
```

For dashboard display, the maintainer often prefers rounded Ah with no decimals.

## Combined Capacity

For multiple packs, combined dashboard capacity should add valid per-pack values.

Example:

```text
Pack 01 full capacity: 100 Ah
Pack 02 full capacity: 100 Ah
Combined full capacity: 200 Ah
```

If a pack does not report capacity, do not invent it. Show Unknown or omit it from a clearly labelled calculated total.

## Current Code Pointers

- `bms_monitor.py`
  - capacity read and publish logic
  - analog pack data
- `web_config.py`
  - dashboard/user summary
  - diagnostics battery configuration
- `bms_notify.py`
  - daily summary energy movement

