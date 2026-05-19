# MQTT / Home Assistant Discovery

Use this guide when changing MQTT topics, retained values or Home Assistant discovery.

## Stability Rules

- Use stable MQTT topics.
- Use stable `unique_id` values.
- Use stable device identifiers.
- Do not rename discovery names unnecessarily.
- Avoid duplicate sensors.
- Do not change entity identifiers without explicit maintainer approval.

Home Assistant can keep stale retained discovery topics after IDs change. Treat MQTT discovery changes as migration-sensitive.

## Units

Use proper units:

| Data | Unit |
|---|---|
| Voltage | `V` |
| Current | `A` |
| Capacity | `Ah` |
| Energy | `kWh` |
| SOC / SOH | `%` |
| Temperature | `°C` |

## Device Classes

Use appropriate Home Assistant device classes where supported:

- voltage
- current
- temperature
- battery
- energy

Use diagnostic category for raw/debug/support sensors.

## Duplicate Entity Troubleshooting

If entities duplicate in Home Assistant:

1. Check MQTT discovery topic names.
2. Check `unique_id` changes.
3. Check retained discovery messages.
4. Clean old retained topics if needed.
5. Restart Home Assistant MQTT integration if required.

## Current Code Pointers

- `bms_monitor.py`
  - MQTT publish logic
  - discovery publish logic
  - retained monitor status topics
- `config.yaml`
  - MQTT defaults and schema
- `README.md`
  - MQTT topic documentation

