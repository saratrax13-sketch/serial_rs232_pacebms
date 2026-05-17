## 2.6.21 - 2026-05-17

### Fixed
- Fixed the compact header `Restart Add-on` button submitting through the normal Save Configuration form.
- The restart button now uses its own independent form and posts directly to `/restart-addon`.
- This prevents the incorrect `No configuration changes detected. Nothing to save.` message.
- Also changed the compact header `Create Backup` button back to its own independent form.

### Notes
- Save Configuration remains unchanged.
- Restart Add-on no longer depends on whether configuration changes were detected.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
