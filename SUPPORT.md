# Support

## Before Asking for Help

Please collect the following information:

- Add-on version
- Battery model
- Number of packs
- Cell count per pack
- Connection type, currently Serial only
- Whether MQTT is connected
- Whether the web UI opens
- Relevant add-on logs
- `debug_output` level used

TCP/IP BMS support was intentionally removed. RS485/Modbus is not currently
supported by this monitor unless a future sprint explicitly investigates it
from raw logs and the maintainer approves the protocol change.

For protocol/debug issues, temporarily set:

```yaml
debug_output: 3
```

Then restart the add-on and capture the relevant request/response section.

Return `debug_output` to `0` after troubleshooting.

## Common Checks

### Add-on starts but no battery data

Check:

- Serial adapter path
- Battery RS232 port
- Cable orientation
- DIP switch addressing
- Home Assistant add-on hardware access
- Add-on logs for receive timeout errors

### Web UI says Offline

Check:

- `pacebms/availability`
- MQTT connection
- Add-on logs
- Whether analog reads are successful

### Web UI says Warning

This means the BMS is online and data is fresh, but one or more BMS warning bits are active.

Check the pack card warning and reference check sections.

### Values do not change

That is not always a problem.

A value staying the same is not stale if the BMS is still replying.

Stale-data detection is based on successful reads, not value changes.

## GitHub Issues

When opening an issue, include logs and describe what you expected to happen versus what actually happened.

Do not include real secrets.
