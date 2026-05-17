## 2.6.13 - 2026-05-17

### Fixed
- Hardened Config validation regex import handling.
- Added local `import re` inside `is_valid_time_hhmm()`.
- Added local `import re` inside `validate_config_options()`.
- Kept the global `import re` in `web_config.py`.
- This prevents `NameError: name 're' is not defined` during Config save.

### Notes
- This is a runtime hardening fix for Config save validation.
- The original Config help modal system remains unchanged.
- `bms_ip` and `bms_port` were not re-added.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
