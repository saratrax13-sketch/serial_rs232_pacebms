## 2.5.2 - 2026-05-17

### Fixed
- Fixed Pack 01 incorrectly showing as Slave in detailed cell data.
- Added explicit `role` value to each detected pack.
- Templates now use the pack role from backend data instead of comparing pack ID text/number values.

### Notes
- Pack 01 is displayed as Master.
- Pack 02 and above are displayed as Slave.
- This is a display fix only.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
