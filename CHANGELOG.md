## 2.3.11 - 2026-05-17

### Fixed
- Fixed `Method Not Allowed` after deleting a backup.
- Delete was successful, but the browser was redirected back to the POST action route.
- POST actions now redirect back to the web UI root using `./?tab=...`.
- POST redirects now use HTTP 303 so the browser follows with a GET request.

### Notes
- Delete only removes selected local backup JSON files.
- Restore writes Home Assistant add-on options only.
- This does not write to the BMS.
- No BMS protocol changes were made.
