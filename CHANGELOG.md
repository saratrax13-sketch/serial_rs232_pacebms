## 2.4.5 - 2026-05-17

### Added
- Added Battery Configuration section to the Diagnostics tab.
- Added Master / Slave pack role display.
- Added pack identity table with role, pack, serial, cells, SOC, SOH, voltage, current, delta and status.
- Added cleaned BMS serial display.
- Added cleaned BMS version display.
- Added clear wording when slave pack serials are not reported separately by the current BMS read.

### Notes
- The UI does not invent serial numbers. It only displays serials that are reported by the BMS/read data.
- This is a Diagnostics tab improvement.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
- The add-on remains read-only to the BMS.
