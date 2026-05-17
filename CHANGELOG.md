## 2.6.14 - 2026-05-17

### Fixed
- Fixed Report Schedules fields not being validated.
- Added explicit backend validation for:
  - `notify_daily_summary_time`
  - `notify_delta_report_time`
  - `notify_delta_window_start`
  - `notify_delta_window_end`
- Added explicit frontend validation for the same fields.
- Added HH:MM input hints for Report Schedule fields.

### Notes
- Valid format is 24-hour `HH:MM`, for example `19:00`, `10:15` or `00:00`.
- Invalid examples such as `7pm`, `25:99`, `10h15` and `abc` should now be blocked.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
