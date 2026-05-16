## 2.1.3 - 2026-05-17

### Added
- Added Config Helper card to the Config tab.
- Added sanitized YAML output generated from current add-on options.
- Added Copy YAML button.
- Added Download YAML button at `/export-config.yaml`.
- Sensitive values are replaced with placeholders in the generated YAML.

### Notes
- This is a safe configuration-helper release.
- The web UI still does not save configuration directly.
- Settings must still be changed in the Home Assistant add-on Configuration tab.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
