## 2.5.5 - 2026-05-17

### Added
- Added debug-only serial-number frame probe to `bms_monitor.py`.
- When `debug_output >= 3`, the monitor now logs:
  - raw C2 serial-number response info
  - decoded printable serial response text
  - serial-like candidates found in the response
  - candidate positions inside the decoded frame
  - a summary indicating whether one or multiple unique serial-like values were found

### Notes
- This is diagnostic logging only.
- Normal serial parsing is unchanged.
- This does not add slave serial support yet.
- This does not write to the BMS.
- No BMS control commands were added.
