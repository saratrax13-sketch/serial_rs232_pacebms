## 2.6.4 - 2026-05-17

### Added
- Added server-side web config validation before saving.
- Added client-side Config tab validation before submit.
- Added validation for integer fields, decimal fields, required text fields, time fields and comma-separated SOC threshold lists.
- Added logical validation:
  - `notify_soc_high_reset` must be lower than `notify_soc_high_threshold`
  - `notify_cell_low_warn_voltage` must be lower than `notify_cell_high_warn_voltage`
- Added clear validation messages for incorrect field formats.

### Notes
- Example comma-separated threshold format: `75,50,25,15`
- Example time format: `19:00`
- Decimal comma is allowed for voltage fields, for example `4,2`.
- `bms_ip` and `bms_port` were not re-added.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
