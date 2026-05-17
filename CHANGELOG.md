## 2.6.22 - 2026-05-17

### Fixed
- Fixed `Restart Add-on` returning `404: Not Found` under Home Assistant Ingress.
- Changed the template form action from absolute `/restart-addon` to relative `restart-addon`.
- Kept the Flask backend route as `/restart-addon`.

### Notes
- Home Assistant Ingress requires relative links/actions so the request stays inside the add-on ingress path.
- No BMS protocol changes were made.
- No BMS write/control commands were added.
