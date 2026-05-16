## 2.3.10 - 2026-05-17

### Fixed
- Fixed backup Delete showing `Method Not Allowed`.
- Delete now uses a stable POST route with the backup filename sent as a hidden form field.
- Restore now also uses a stable POST route with the backup filename sent as a hidden form field.
- Avoids filename-based POST routes that can behave inconsistently through Home Assistant Ingress.

### Notes
- Delete only removes selected local backup JSON files.
- Restore writes Home Assistant add-on options only.
- This does not write to the BMS.
- No BMS protocol changes were made.
