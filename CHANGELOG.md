## 2.6.0 - 2026-05-17

### Added
- Added Warning Intelligence section to the Status tab.
- Added per-pack warning intelligence cards.
- Added plain-language warning context for each detected pack.
- Added BMS internal warning summary per pack.
- Added highest cell, lowest cell and cell delta context per pack.
- Added reference check context per pack.
- Added suggested operator focus text.

### Notes
- This is a web UI operational clarity release.
- Warning Intelligence uses current retained MQTT values and already-decoded BMS warnings.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
- The add-on remains read-only to the BMS.
