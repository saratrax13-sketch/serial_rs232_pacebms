# Voltage Parsing

Use this guide when pack voltage, cell voltage or warning references look wrong.

## Debugging Steps

1. Check the raw frame/register value.
2. Confirm the value source:
   - individual cell
   - pack voltage
   - combined-bank value
   - configured UI/Telegram reference
3. Check scaling:
   - millivolts to volts
   - centivolts to volts
   - decivolts to volts
4. Check endian format.
5. Check signed vs unsigned interpretation.
6. Compare pack voltage against the sum of cell voltages where available.
7. Reject impossible values instead of displaying fake confidence.

## Sanity Checks

For a 13S Hubble AM2 battery, pack voltage over realistic limits should trigger investigation before being trusted. Do not publish or display impossible voltage as normal without proving the raw data and scaling.

For 16S LFP packs, use detected cell count and profile context rather than Hubble 13S assumptions.

## Warning Reference Separation

Always distinguish:

- measured BMS values
- BMS-reported warning/protection flags
- app-configured UI/Telegram reference values
- profile default references

The app reference value is not a BMS threshold unless the BMS explicitly reports it as such.

## Current Code Pointers

- `bms_monitor.py`
  - analog data parsing
  - cell voltage parsing
  - pack voltage parsing
- `battery_profiles.py`
  - read-only warning reference profiles
- `web_config.py`
  - Warning Intelligence reference margins
- `bms_notify.py`
  - Telegram warning detail

