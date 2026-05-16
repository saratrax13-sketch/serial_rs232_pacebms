## 2.2.9 - 2026-05-17

### Added
- Added `icon.png` for the Home Assistant add-on.

### Changed
- Expanded Advanced Config help text to explain `debug_output` levels 0, 1, 2 and 3.
- Removed `bms_ip` and `bms_port` from the web Config tab.
- Removed outdated IP/TCP wording from the BMS Connection help popup.

### Notes
- This is a web UI, icon and config-cleanup release.
- `bms_ip` and `bms_port` should also be removed from `config.yaml` under both `options:` and `schema:`.
- No BMS protocol changes were made.
- No BMS write/control commands were added.


# 2.2.9 config.yaml cleanup

Remove these from `options:` if present:

```yaml
bms_ip: "10.0.0.161"
bms_port: 5000
```

Remove these from `schema:` if present:

```yaml
bms_ip: str
bms_port: int
```

Then update:

```yaml
version: "2.2.9"
```
