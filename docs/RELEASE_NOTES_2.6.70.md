# Release Notes 2.6.70

## Summary

This release completes the documentation and screenshot pass for the current web UI.

## Changed

- Added current screenshots to the main README.
- Added screenshots to first-run, configuration, backup/restore and warning-deduplication documentation.
- Added a complete screenshot guide under `docs/screenshots/README.md`.
- Updated the web UI documentation section to use the current Dashboard, Tech Status, Setup, Config, Diagnostics, Events, Backups, Logs and Telegram screenshots.
- Removed the old temporary `web-ui-2.0.39-warning-reference.png` image.

## Safety

- Documentation/screenshots only.
- No BMS write/control commands were added.
- No MQTT topics were changed.
- No Home Assistant discovery entity names were changed.
- No monitor polling or Telegram alert logic was changed.

## Validation

- Markdown image links were checked.
- Python compile validation passed.
- Unit tests passed.
- `git diff --check` passed.
