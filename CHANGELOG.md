## 2.4.7 - 2026-05-17

### Added
- Added `Download Support Bundle ZIP` button to the Diagnostics tab.
- Added `/download-support-bundle.zip` route.
- Support bundle includes:
  - `diagnostics.json`
  - `events.json`
  - `backup-summary.json`
  - `sanitized-config.json`
  - `readme-support.txt`
- Sensitive values are redacted from the support bundle.
- Full backup files are not included in the support bundle.

### Notes
- This is a diagnostics/support export release.
- The support bundle exports information only.
- It does not change Home Assistant settings.
- It does not write to the BMS.
- No BMS protocol changes were made.
