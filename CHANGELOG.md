## 2.6.65 - 2026-05-18

### Changed
- Replaced partial live-field auto-refresh with quiet full active-tab refresh for Dashboard, Tech Status, Setup, Diagnostics and Logs.
- Set Dashboard soft refresh to 15 seconds.
- Added Logs sample time-span context with oldest and newest captured line timestamps.
- Added Logs viewer help explaining Refresh Logs, the latest 400-line sample and display-only filtering.
- Removed Open Config and Restart Add-on actions from the Logs tab.

### Notes
- Soft refresh replaces only the active tab content and keeps the page shell in place.
- Logs filters are preserved during automatic Logs refresh.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.64 - 2026-05-18

### Changed
- Simplified the Logs tab into a clearer Log Viewer section and a separate Debug Capture Setting section.
- Renamed the confusing debug display selector to View Detail with Normal, Summary, Detailed and Debug / Web access choices.
- Added clearer guidance that Logs tab filters do not change what the monitor records.
- Added Open Config and Restart Add-on actions beside the current `debug_output` capture setting.

### Notes
- This is a web UI wording and workflow polish update only.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.63 - 2026-05-18

### Changed
- Combined the Diagnostics page intro, support actions and live status/layout summary into one header card.
- Kept the top navigation on one equal-width row so Tech Status no longer wraps onto two lines.
- Improved the Logs empty/filter state with captured-line counts and clearer guidance about levels 2 and 3.
- Added soft tab switching so main tab clicks replace only the active tab content instead of redrawing the full page.

### Notes
- This is a web UI responsiveness and layout polish update only.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.62 - 2026-05-18

### Added
- Added a read-only Logs tab with display-level filtering for debug data levels 0, 1, 2 and 3.
- Added log category filtering for Monitor, Warnings, MQTT, Telegram, Web UI and Protocol entries.
- Added support log file capture for monitor and web UI output under `/data`.
- Added a Download Logs action for support troubleshooting.

### Changed
- Suppressed routine Flask web access logs from normal output unless `debug_output` is set to 3 or higher.
- Classified routine `/api/status` and `/health` access lines as Web UI debug level 3 noise in the Logs tab.

### Notes
- Logs are read-only support data. The Logs tab does not write to or control the BMS.
- Changing the Logs tab filter does not require an add-on restart.
- Changing `debug_output` in Config still requires an add-on restart before the monitor emits the new level of detail.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.61 - 2026-05-18

### Fixed
- Renamed the top navigation label from Admin Config to Config for a cleaner tab bar.
- Removed the Setup tab shortcut button that opened Config.
- Added the live Overall Status and Detected Battery Layout header to Diagnostics.
- Made automatic Dashboard, Tech Status and Diagnostics refreshes quiet so they no longer flash visible "refreshing" text during every timer update.
- Stopped Setup auto-refresh from reloading the whole page; it now quietly refreshes the retained MQTT cache in the background.

### Notes
- This is a web UI polish update only.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.60 - 2026-05-18

### Added
- Added a background retained-MQTT live snapshot cache for the web UI.

### Changed
- Dashboard, Tech Status, Setup and Diagnostics now render from the warm snapshot cache when available, so tab clicks no longer wait on a fresh MQTT broker round trip.
- `/api/status` still performs a full MQTT retained-value read and refreshes the cache after each live refresh.
- Dashboard, Tech Status and Diagnostics now request a live `/api/status` refresh immediately after the page opens instead of waiting for the first auto-refresh interval.

### Notes
- This is a web UI responsiveness update only.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.59 - 2026-05-18

### Fixed
- Reverted the short page-render MQTT snapshot because it could open live tabs with missing or unknown data.
- Restored reliable retained MQTT data loading for Dashboard, Tech Status, Setup and Diagnostics page renders.

### Notes
- This restores the stable live-tab behavior from before 2.6.58.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.58 - 2026-05-18

### Changed
- Made live tabs render with a short cached MQTT snapshot so tab clicks feel immediate.
- Kept full live MQTT refresh through `/api/status` after the tab is visible.

### Notes
- This is a web UI responsiveness update only.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.57 - 2026-05-18

### Changed
- Tightened top navigation tab spacing so equal-width buttons sit closer together.

### Notes
- This is a UI layout polish update only.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.56 - 2026-05-18

### Changed
- Adjusted top navigation tabs to be wider, slimmer and vertically centered.

### Notes
- This is a UI layout polish update only.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.55 - 2026-05-18

### Changed
- Updated first BMS Warning Telegram messages to match the web UI Warning Intelligence structure.
- Added Quick Metrics, BMS Warning Details, reference margins, Reference Check, Interpretation and Suggested Action to detailed BMS warning alerts.

### Notes
- This is a read-only notification wording/layout update.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.54 - 2026-05-18

### Changed
- Made visible refresh buttons reload the full current tab so server-rendered page data refreshes together.
- Added Setup tab auto-refresh every 15 seconds and a matching refresh icon button.
- Improved Tech Status spacing between pack cards and comparison charts.
- Grouped Admin Config actions by save changes, backups, export and add-on action.
- Made top navigation tabs equal width for a more balanced header.

### Notes
- This is a read-only UI behavior and layout update.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.53 - 2026-05-18

### Changed
- Removed Tech Status and Diagnostics explanatory banners to reduce visual noise.
- Added icon refresh buttons to Tech Status and Diagnostics headers.
- Removed duplicated Diagnostics health-check, safety and navigation sections.
- Color-coded the Diagnostics header by current status.
- Rebalanced Tech Status comparison charts into a cleaner two-column grid.

### Notes
- This is a read-only UI cleanup.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.52 - 2026-05-18

### Changed
- Shortened slave pack serial placeholders from "Not reported separately" to "N/A" so pack cards align better.

### Notes
- This is a read-only UI text cleanup.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.51 - 2026-05-18

### Changed
- Removed the old duplicated BMS warning and Reference Check blocks from the Tech Status pack cards.
- Kept warning explanation centralized in the expanded Warning Intelligence section.

### Notes
- This is a read-only UI cleanup.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.50 - 2026-05-18

### Added
- Expanded Tech Status Warning Intelligence with quick metrics for highest cell, lowest cell, delta, pack voltage, SOC, SOH and cycles.
- Added warning detail rows that compare warning cells and pack voltage against configured references.
- Added reference margin labels such as below reference, at reference and exceeded.
- Added plain-language interpretation and suggested action text for each pack warning card.

### Notes
- This is a read-only UI explanation improvement.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.49 - 2026-05-18

### Changed
- Removed the visible Monitoring Health, Live Status and technician tool cards from Tech Status.
- Kept Tech Status focused on Warning Intelligence, detailed pack cards and comparison charts.
- Kept Tech Status auto-refresh running silently while the tab is open.
- Updated README guidance to match the simplified Tech Status layout.

### Notes
- This is a UI/layout cleanup only.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.48 - 2026-05-18

### Changed
- Removed the extra Dashboard intro, Monitoring Snapshot and Warning Summary cards to reduce user-facing noise.
- Added a compact refresh icon button to the Battery Confidence card.
- Moved pack comparison charts from Dashboard to Tech Status.
- Reordered the top navigation to Dashboard, Tech Status, Diagnostics, Setup, Admin Config, Events and Backups.
- Fixed Pack Comparison role display so Pack 01 shows as Master and later packs show as Slave.
- Color-coded Pack Comparison status values for normal, warning/caution and critical states.

### Notes
- This is a UI/layout cleanup only.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.47 - 2026-05-18

### Added
- Added combined SOH to the Battery Confidence dashboard.

### Changed
- Reordered Battery Confidence tiles so operating state, SOC, SOH, time estimate, power, electrical values, capacity, health and safety fields are grouped more naturally.
- Renamed the previous health tile to Lowest Pack SOH so the difference between combined SOH and weakest-pack SOH is clearer.

### Notes
- Combined SOH is capacity-weighted when full capacity is reported; otherwise it falls back to the average of detected pack SOH values.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.46 - 2026-05-18

### Added
- Added a dynamic User Dashboard time label that switches between runtime, charge-time and idle states.
- Added clearer charging/discharging power wording and last-updated visibility to the User Dashboard.
- Added plain-language warning summary text to the User Dashboard.
- Added per-pack role, serial context and power to the Tech Status pack cards.

### Changed
- Polished User Dashboard capacity wording so remaining energy, full capacity and design capacity are easier to read.
- Re-grouped Tech Status pack cards into identity, energy/health, capacity, electrical, cell balance, references and BMS state.
- Slimmed button and tab styling for a less bulky web UI.
- Updated README guidance for runtime and charge-time estimates.

### Notes
- Charge time remains an estimate based on current charge power and reported capacity.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.45 - 2026-05-18

### Added
- Added charge-to-full estimate while charging.
- Updated the User Dashboard time tile to show runtime while discharging and charge time while charging.

### Notes
- Charge time is calculated from current charge power and the energy needed to reach reported full capacity.
- Charge time is an estimate and may increase near full SOC if charge current tapers.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.44 - 2026-05-18

### Added
- Added Tech Status auto-refresh every 15 seconds while the Tech Status tab is open.
- Added Diagnostics auto-refresh every 15 seconds while the Diagnostics tab is open.
- Added visible refresh notes for Tech Status and Diagnostics.

### Notes
- Setup remains manual only.
- Config has no auto-refresh.
- Events and Backups behaviour was not changed.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.43 - 2026-05-18

### Added
- Added estimated runtime remaining to the User Dashboard while the battery is discharging.
- Added safe runtime states for charging, idle/no-load and missing data.
- Added Dashboard auto-refresh every 30 seconds while the Dashboard tab is open.

### Notes
- Runtime is calculated from retained MQTT values using remaining kWh divided by current discharge kW.
- Runtime is an estimate based on current load and will change as load changes.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.42 - 2026-05-18

### Changed
- Made the Dashboard the default normal-user view.
- Renamed Status to Tech Status in the web UI navigation.
- Added a dedicated Setup tab for Setup Checklist and MQTT/Telegram/Full Monitoring tests.
- Moved setup tests away from the technician Status page.
- Added audience notes to Dashboard, Tech Status, Setup, Admin Config, Diagnostics, Events and Backups.
- Updated README and first-time setup guidance to match the user/technician/setup split.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.41 - 2026-05-18

### Added
- Added a simple User Dashboard section for daily battery confidence.
- Added combined SOC, operating state, power flow, total battery power, voltage/current, remaining Ah, estimated remaining kWh, full/design Ah, battery health, temperature status and active warning count.
- Added derived read-only user summary data to `/api/status` so Dashboard refresh updates the user view.

### Notes
- Power and energy values are calculated from existing BMS-reported voltage/current/capacity values.
- Runtime remaining is still not estimated because no reliable external load/inverter consumption source is available in this add-on yet.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.40 - 2026-05-17

### Added
- Added a compact quick summary strip to each Status pack card for SOC, SOH, cycles and cell delta.
- Added Diagnostics battery-life summary tiles for max cycles, lowest SOH and average SOC.

### Changed
- Improved pack-card scanability while keeping the grouped detail sections.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.39 - 2026-05-17

### Changed
- Reworked Status pack cards into clearer groups: Battery Health, Electrical, Cell Balance, Reference Limits and BMS Control State.
- Slimmed web UI buttons so tool actions and tab controls feel less bulky.

### Added
- Added cycle count to the Diagnostics Battery Configuration table.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.38 - 2026-05-17

### Added
- Added pack cycle count to the web UI Status pack cards.
- Added pack cycle count to the Dashboard pack comparison cards.
- Added live Dashboard refresh support for cycle count values.

### Changed
- Updated README and first-time setup guidance to mention cycle count visibility.

### Notes
- Cycle count was already parsed from the BMS and published to MQTT as `pack_x/cycles`; this release makes it visible in the web UI.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.37 - 2026-05-17

### Added
- Added Monitoring Health, analog age and warning age to the Dashboard summary.
- Added a Dashboard Monitoring Snapshot block for easier support screenshots.
- Added `docs/screenshots/README.md` with recommended screenshot names and privacy guidance.

### Changed
- Updated the first-time setup guide with clearer Status, Dashboard and screenshot validation steps.
- Updated README screenshot guidance to point users at the screenshot guide.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.36 - 2026-05-17

### Added
- Added a dedicated Monitoring Health card on the Status tab.
- Added monitor heartbeat, MQTT monitor state, analog read age, warning read age, detected pack count and cell count checks to the web UI.
- Added README guidance for Status screenshots and what the Monitoring Health card means.

### Changed
- Status refresh now updates the Monitoring Health card from `/api/status`.
- `/api/status` now includes the same read-only Monitoring Health summary used by the web UI.

### Tests
- Added regression coverage for healthy and stale Monitoring Health summaries.
- Extended the Status page render test to confirm the Monitoring Health section loads.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.35 - 2026-05-17

### Fixed
- Fixed a web UI 500 error on the Status tab caused by a Jinja dictionary key collision in the Setup Checklist.

### Tests
- Added a Status page render regression test for the Setup Checklist.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.34 - 2026-05-17

### Added
- Added a web UI Setup Checklist card for guided first-run setup validation.
- Added clearer Telegram placeholder warnings when notifications are enabled but Telegram values are missing or placeholders.
- Added a Test Full Monitoring button that checks MQTT connectivity, Telegram configuration and notification thresholds without sending BMS commands or Telegram messages.
- Added README first-run setup checklist guidance.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.33 - 2026-05-17

### Fixed
- Changed the Home Assistant sidebar panel icon to `mdi:battery` for better compatibility with Home Assistant icon sets.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.32 - 2026-05-17

### Fixed
- Hardened warning-frame parsing for 16-cell multi-pack Pace BMS frames.
- Fixed false Pack 2 warning/protection/FET states caused by P16S inter-pack trailer bytes.
- Prevented clean 16-cell warning frames from decoding as `Lower cell volt protect`, `Above total volt protect`, or false FET OFF.

### Tests
- Added a regression test using the captured 16-cell two-pack warning payload.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.31 - 2026-05-17

### Fixed
- Hardened analog parsing for 16-cell multi-pack Pace BMS frames.
- Fixed P16S inter-pack trailer alignment so Pack 2 analog data is found by validating full pack candidates.
- Added analog frame bounds checks with clearer parser diagnostics.
- Prevented isolated analog parse errors from immediately causing false disconnect/reconnect Telegram alerts.

### Tests
- Added a regression test using the captured 16-cell two-pack analog payload.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.30 - 2026-05-17

### Changed
- Reordered Home Assistant add-on Configuration fields so Basic Required connection and MQTT options appear first.
- Moved Telegram, notification, warning-detail and report schedule fields after the required setup fields.
- Cleaned `config.yaml` comments to plain ASCII for easier repo maintenance.
- Updated README current version and setup guidance for the Home Assistant Configuration tab.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.29 - 2026-05-17

### Added
- Added Basic Required, Full Monitoring and Advanced View filters to the Config tab.
- Added clearer Caution / Warning / Critical severity labels in the web UI warning overview.

### Changed
- Updated Notification Thresholds help text for severity-aware warning repeat fields.
- Updated web UI validation for the new severity repeat interval fields.
- Improved Config tab button hierarchy so Save, backup, download and restart actions are easier to scan.
- Updated README guidance for Basic Required versus Full Monitoring setup.

### Removed
- Removed an unused stale static stylesheet that was no longer loaded by the Ingress UI.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.28 - 2026-05-17

### Added
- Added severity-aware BMS warning repeat intervals:
  - `notify_warning_repeat_caution_seconds`
  - `notify_warning_repeat_warning_seconds`
  - `notify_warning_repeat_critical_seconds`
- Added persisted warning notification state across add-on restarts.
- Added short reminder messages for repeated ongoing warnings.

### Changed
- Normalized BMS warning text into stable risk families such as high cell voltage and high pack voltage.
- Warning notifications now resend immediately only for new risks or severity escalation.
- Ongoing caution, warning and critical alerts use separate configurable cooldowns.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.27 - 2026-05-17

### Added
- Added monitor heartbeat file for runtime health tracking.
- Added `/health` endpoint checks for Home Assistant Supervisor watchdog support.
- Added add-on `watchdog` configuration pointing to the internal health endpoint.
- Added README guidance for Home Assistant offline-monitor alerting.

### Fixed
- Fixed warning deduplication label normalization so warning text is no longer split incorrectly in logs.

### Notes
- No BMS write/control commands were added.
- Health checks monitor the add-on process heartbeat, not battery health.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.26 - 2026-05-17

### Changed
- Removed unused TCP/IP BMS transport code from the monitor runtime.
- Improved add-on process supervision so the web UI and monitor are both watched.
- Updated energy tracking to calculate kWh from actual elapsed sample time instead of the configured scan interval.
- Synced README current version reference.

### Fixed
- Telegram placeholder credentials are now treated as unconfigured.
- Telegram failure logs no longer expose detailed exception text.

### Added
- Added focused unit tests for Pace frame parsing, Telegram placeholder handling, and energy tracking.

### Notes
- No BMS write/control commands were added.
- No MQTT topic or Home Assistant discovery entity names were changed.
- Standalone Docker config handling was intentionally left unchanged for a later sprint.
