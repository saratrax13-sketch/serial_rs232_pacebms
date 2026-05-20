## 2.9.41 - 2026-05-20

### Fixed
- Improved Cell Delta Report history windows so overnight ranges after midnight use the just-finished SQLite window instead of a future window.
- Included SQLite history pack IDs in Cell Delta Report output even when the runtime pack count is lower than the stored history pack list.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.
- Monitor polling behavior was not changed.

## 2.9.40 - 2026-05-20

### Fixed
- Improved Daily BMS Summary reports so persisted SQLite history remains the source for daily energy movement after restarts.
- Included SQLite `power_kw` history when voltage/current samples are incomplete, while still respecting the configured current deadband when current can be derived.
- Included persisted SQLite warning events in Daily BMS Summary output even when same-day pack metric samples are missing for that pack.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.
- Monitor polling behavior was not changed.

## 2.9.39 - 2026-05-20

### Fixed
- Restored `connection_type` to the BMS Connection config card as a fixed Serial option so every add-on option is represented in the web form.
- Added regression coverage matching the config validation checklist for options, schema and web Config grouping alignment.
- Added `.codexignore` so dependency folders, build output, local runtime data, logs, databases and archives stay out of Codex context.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.
- Monitor polling behavior was not changed.

## 2.9.38 - 2026-05-20

### Fixed
- Added fallback help text for every Config card so info buttons remain meaningful even if the detailed browser modal falls back to server-provided content.
- Added detailed History & Live Data help explaining serial-first live snapshots, MQTT fallback and SQLite history storage.
- Updated Battery Profile & Alert References help so measured values are described as live serial-first values instead of retained MQTT-only values.

### Notes
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.
- Monitor polling behavior was not changed.

## 2.9.37 - 2026-05-20

### Fixed
- Aligned local SQLite pack/bank history writes with the configured `history_sample_seconds` interval instead of forcing a history row after every analog and warning phase.
- Kept cell and temperature history writes governed by `history_cell_sample_seconds`.
- Preserved live serial snapshot updates after analog, capacity and warning reads so the Web UI still receives fresh data as quickly as the monitor has it.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor serial polling cadence and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.36 - 2026-05-20

### Fixed
- Suppressed non-exceeded low-cell and low-pack reference rows from Warning Intelligence so safe low-voltage margins are not shown as warning detail.
- Suppressed non-exceeded low-voltage rows from Telegram BMS warning detail while keeping exceeded low-voltage rows visible.
- Kept BMS-reported warning text visible when the BMS is warning below the configured user reference.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.35 - 2026-05-20

### Fixed
- Changed warning reference calculations so Warning Intelligence, Telegram detail and Telegram filtering use edited user-defined alert reference values instead of silently falling back to profile defaults.
- Kept battery profile defaults as guidance and as safe defaults when the reference fields are still untouched.
- Updated the Config reference table to keep showing profile guidance separately from active user-defined alert values.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.34 - 2026-05-20

### Fixed
- Added a pending-options cache for successful Config saves so saved values remain visible before the add-on restart applies them to `/data/options.json`.
- Subsequent Config saves before restart now build from the pending saved values instead of the previous runtime options, preventing earlier saved edits from being lost.
- Keeps the header live-data badge based on the running monitor's runtime options while the Config tab displays pending saved options.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.33 - 2026-05-20

### Fixed
- Added persisted SQLite `warning_events` into the daily Telegram summary so same-day warnings are still reported when pack metric samples do not carry the warning text.
- Keeps live Telegram alerts live-only while making scheduled historical reports use the monitor-owned database where appropriate.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.32 - 2026-05-20

### Fixed
- Changed the scheduled cell delta Telegram report to use local SQLite history before falling back to in-memory delta tracking.
- Prevents add-on restarts from causing `No data in window` when valid pack delta history exists for the configured report window.
- Adds highest and lowest cell context to the history-based delta report where available.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.31 - 2026-05-20

### Fixed
- Changed the daily Telegram summary to calculate per-pack charge/discharge, SOC movement, worst-cell deviation and warnings from the local SQLite history database before falling back to in-memory counters.
- Prevents add-on restarts from erasing earlier same-day discharge/charge and warning evidence in the daily report.
- Cleans tiny rounded SOC changes so near-zero movement does not display as `-0.0%`.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.30 - 2026-05-20

### Fixed
- Moved the header version pill into the navigation row so it sits in the requested right-aligned position beside the tab row instead of under the live source badge stack.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.29 - 2026-05-20

### Fixed
- Repositioned the header version pill so it sits directly below the live source badge and remains right-aligned with the header badge stack.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.28 - 2026-05-20

### Fixed
- Adjusted the header version pill to match the compact navigation pill sizing and align right under the live source badge.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.27 - 2026-05-20

### Fixed
- Fixed the header version pill so it reads the installed add-on version reliably from the project `config.yaml`.
- Tightened the header badge layout so the version pill sits closer to the existing read-only and live source badges.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.26 - 2026-05-20

### Changed
- Added a header version pill showing the installed add-on version below the live data source badge.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.25 - 2026-05-20

### Changed
- Reordered the main navigation so History follows Diagnostics.
- Reordered Setup content so Setup Tests sit between Local History Storage and Setup Checklist.
- Improved live/history graph readability with clearer chart titles, unit-aware axis labels, softer chart typography and more useful hover text.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.24 - 2026-05-20

### Fixed
- Applied BMS warning cell labels to the serial-first live snapshot path used by the current UI, so Detailed Pack & Cell Data shows BMS High Warning or BMS Low Warning when the BMS reports a generic cell-voltage warning.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.23 - 2026-05-20

### Fixed
- Marked the current highest or lowest cell in Detailed Pack & Cell Data when the BMS reports a generic cell-voltage warning without naming the exact cell.
- Kept BMS warning cell labels separate from user reference threshold labels so a cell can show BMS High Warning even when it is below the configured user reference.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.22 - 2026-05-20

### Changed
- Renamed the warning explanation heading from BMS Warning Details to BMS Reported Warning Details in the web UI and Telegram messages.
- Added a reference-check note when a BMS warning is active below configured user references, making it clear that the BMS internal threshold appears lower than the UI/Telegram reference.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.21 - 2026-05-20

### Changed
- Clarified the Warning Intelligence Telegram decision text so BMS critical/protection warnings say plainly when Telegram will send, even if user reference values are not exceeded.
- Clarified filtered BMS warning wording when the warning is below user references and does not include critical/protection text.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.20 - 2026-05-20

### Fixed
- Tightened BMS warning deduplication so brief BMS clear/reappear flicker keeps using the existing warning cooldown instead of sending the same Telegram warning again.
- Preserved the last warning family after a confirmed clear so repeated top-of-charge warning flicker remains quiet until the configured repeat interval expires.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.19 - 2026-05-20

### Fixed
- Fixed History chart lifecycle during soft tab navigation so charts recreate reliably when switching away and back to History.
- Made History chart typography quieter and easier to read, with fewer crowded axis labels.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.18 - 2026-05-20

### Fixed
- Fixed History range and pack selector buttons so they keep working after Home Assistant Ingress soft tab navigation.
- Kept History graph updates in-place when switching between Bank, Pack 01 and Pack 02 views.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.17 - 2026-05-20

### Changed
- Added pack-specific History graph views so the History tab can switch between Bank, Pack 01 and Pack 02 trends.
- Improved History graph titles, selected-view summary and refresh text so the current graph context is clearer.
- Tuned default Telegram noise settings for normal use: low-SOC defaults now alert at 50/25/10%, FET repeat defaults to 3600 seconds and critical BMS warning reminders default to 1800 seconds.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.16 - 2026-05-20

### Changed
- Improved Dashboard and History graph scaling so SOC, power, pack voltage and cell delta use adaptive ranges instead of overly broad fixed axes.
- Improved graph hover behavior with a larger hit area and clearer local-history tooltip text.
- Kept Live Trends in a two-by-two layout with quieter supporting text.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.15 - 2026-05-20

### Changed
- Simplified Warning Intelligence when no BMS warning is active and no user alert reference is exceeded.
- Made Local History Storage visible on Setup without depending on the Diagnostics tab context.
- Added Local History to the Setup Checklist so storage health is visible during first-run validation.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.14 - 2026-05-20

### Changed
- Moved Local History Storage from Diagnostics to Setup so storage configuration and health checks live with installer checks.
- Updated Setup Checklist tiles so warning items use amber card styling instead of only a small warning pill.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.13 - 2026-05-20

### Changed
- Added a measured pack state pill to BMS Control State rows in Tech Status and Diagnostics.
- The new state pill shows Charging, Discharging, Idle or Unknown from measured pack power.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.12 - 2026-05-20

### Changed
- Added BMS-triggered cell status pills in Diagnostics Detailed Pack & Cell Data.
- Cells named by the BMS warning text now show `BMS High Warning` or `BMS Low Warning` separately from highest/lowest and user reference status.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.11 - 2026-05-20

### Changed
- Improved Tech Status Warning Intelligence so BMS-reported warnings and user-defined alert references are shown as separate sections.
- Added per-reference Telegram alert state and warning-policy explanation to the Warning Intelligence cards.
- Added app-side watch-condition handling when user references are exceeded but the BMS has not reported a warning.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.10 - 2026-05-20

### Fixed
- Bumped the Home Assistant add-on version so the Telegram alert noise hotfix is visible as an update.
- Suppressed startup replay of already-crossed low-SOC thresholds so a restart at very low SOC does not send 75/50/25/10 alerts in one burst.
- Added a cooldown for repeated FET OFF alerts to reduce Telegram noise from noisy ON/OFF state flicker.
- Added warning-clear confirmation reads so brief BMS warning flicker does not immediately clear and re-alert.
- Kept low-power warning wording as message detail when it accompanies low-voltage warnings, instead of treating it as a new primary warning family.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.9 - 2026-05-20

### Changed
- Bumped the Home Assistant add-on version so the Diagnostics cell-data UI sprint is visible as an update.
- Reworked Diagnostics Detailed Cell Data into a Detailed Pack & Cell Data layout matching the Tech Status Battery Packs cards.
- Kept individual cell readings below each pack so pack context and cell diagnostics stay together.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.8 - 2026-05-19

### Added
- Added a read-only History tab for local SQLite battery trends with selectable 30 minute, 1 hour, 6 hour and 24 hour ranges.
- Added Diagnostics visibility for local history database health, row counts, retention settings and latest sample time.
- Added serial-first history validation steps for Home Assistant and standalone Docker documentation.

### Changed
- Bumped the Home Assistant add-on version so the history/graph visibility sprint is available as an update.

### Fixed
- Closed short-lived SQLite diagnostic/query connections explicitly after history checks.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.7 - 2026-05-19

### Changed
- Bumped the Home Assistant add-on version so the live refresh timing hotfix is visible as an update.
- Aligned Tech Status and Diagnostics live-field refresh with Dashboard at 1 second while each tab is open.
- Corrected visible refresh wording for Dashboard and Diagnostics live fields.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.6 - 2026-05-19

### Changed
- Bumped the Home Assistant add-on version so the Dashboard graph text polish is visible as an update.
- Made the Dashboard Live Trends helper text quieter and shorter.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.5 - 2026-05-19

### Fixed
- Bumped the Home Assistant add-on version so the Dashboard graph hover hotfix is visible as an update.
- Improved Dashboard graph hover behavior so moving across a graph shows the nearest timestamp/value instead of requiring the pointer to hit an invisible data point.
- Clarified the voltage graph tooltip as average pack voltage.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.4 - 2026-05-19

### Fixed
- Bumped the Home Assistant add-on version so the Dashboard graph layout hotfix is visible as an update.
- Changed Dashboard Live Trends to a stable two-by-two layout.
- Reduced Dashboard graph title and axis font weight for a cleaner UI.
- Added metric-specific graph axis ranges so small SOC, voltage, power and cell-delta changes are not visually exaggerated.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.3 - 2026-05-19

### Fixed
- Bumped the Home Assistant add-on version so the Dashboard graph repair is visible as an update.
- Corrected Dashboard graph data mapping so bank SOC, battery power and pack voltage read the SQLite history API field names correctly.
- Changed the Dashboard refresh button to refresh displayed data and graphs in place instead of replacing the dashboard panel.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.2 - 2026-05-19

### Changed
- Bumped the Home Assistant add-on version so the live-data-source repair sprint is visible as an update.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.1 - 2026-05-19

### Fixed
- Fixed Dashboard live trend graphs so Chart.js canvases are initialized before snapshot duplicate checks can skip rendering.
- Added stable graph canvas sizing and visible graph status text for missing history samples or chart refresh errors.
- Changed the vendored Chart.js script path to an Ingress-safe relative path for Home Assistant add-on use.
- Replaced the static Pace RS232 header badge with a live data-source badge.
- Hid the legacy `connection_type` field from the visible Config tab while preserving it internally for backward compatibility.
- Renamed Web UI data source choices to clearer display-source wording.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling behavior and BMS serial commands were not changed.
- No BMS write/control commands were added.

## 2.9.0 - 2026-05-19

### Added
- Added serial-first live snapshot support with `/data/pacebms-live.json` so the web UI can read monitor-owned live serial data before falling back to MQTT.
- Added local SQLite metrics storage at `/data/pacebms_metrics.db` with bank, pack, cell, temperature, warning and system history tables.
- Added `/api/live`, `/api/history`, `/api/history/pack/<pack_id>` and `/api/history/cells/<pack_id>` endpoints.
- Added local Chart.js graphs for Dashboard live trends using a vendored `static/vendor/chart.min.js` asset.
- Added configuration options for BMS connection mode, UI data source, MQTT enablement, metrics enablement, history sampling and retention.
- Added standalone Docker environment variables for MQTT-optional and metrics/history settings.

### Changed
- MQTT is now optional output/fallback instead of the required primary web UI source.
- Dashboard, Tech Status and Diagnostics live refresh now update fields through API polling instead of redrawing the full tab.
- Home Assistant discovery still uses the existing MQTT topic and unique-id structure when MQTT is enabled.

### Safety
- No BMS write, FET control, threshold write or command-control features were added.
- Invalid serial frames remain rejected by the existing parser path before data is published, snapshotted or stored.

## 2.8.0 - 2026-05-19

### Stable Release
- Marked the project as complete for normal Home Assistant add-on and standalone Docker use.
- Confirmed read-only Pace BMS monitoring remains the default safety position.
- Confirmed standalone Docker startup, health checks and disconnected-BMS recovery behavior on an Ubuntu Docker host.
- Confirmed Home Assistant add-on version metadata, README current version and changelog are aligned for release visibility.

### Included
- Home Assistant add-on support with MQTT discovery and Telegram notifications.
- Standalone Docker support with environment-based configuration, persistent data volume, health check and restart policy.
- Dashboard, technician status, diagnostics, logs, backups and configuration web UI.
- Profile-based warning references and Telegram noise reduction for BMS warnings.
- 13S and 16S Pace BMS parsing support validated through tests and real-world user checks.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling intervals were not changed.
- No BMS write/control commands were added.

## 2.7.4 - 2026-05-19

### Fixed
- Normalized the Docker startup script during image builds so standalone Docker containers can start correctly even when the source archive contains Windows line endings.
- Added Git line-ending rules for shell, Python, YAML, Markdown and JSON files to prevent future CRLF startup issues.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling intervals were not changed.
- No BMS write/control commands were added.

## 2.7.3 - 2026-05-19

### Fixed
- Kept the monitor process alive when the serial cable or BMS is unavailable during startup; it now reports disconnected health and retries instead of exiting.
- Made MQTT startup failures non-fatal so the monitor can keep running and retry MQTT.
- Allowed BMS polling to continue while MQTT reconnect attempts are in progress.
- Prevented the MQTT publish cache from marking values as sent while the MQTT client is disconnected.

### Notes
- MQTT topics and Home Assistant discovery identifiers were not changed.
- Monitor polling intervals were not changed.
- No BMS write/control commands were added.

## 2.7.2 - 2026-05-19

### Changed
- Moved expected pack/cell layout checks and capacity fallback controls into the wide Battery Profile & Alert References card.
- Removed the separate Battery Layout & Fallbacks card from the Config grid to improve layout balance.

### Notes
- This is a UI layout change only for existing read-only settings.
- MQTT topics, Home Assistant discovery identifiers and monitor polling behavior were not changed.
- No BMS write/control commands were added.

## 2.7.1 - 2026-05-19

### Added
- Added optional Battery Layout & Fallbacks settings for expected total cell count, expected pack count, capacity fallback enable and fallback capacity per pack.
- Added setup and diagnostics visibility for configured layout checks.
- Added capacity fallback support for dashboard runtime/charge estimates only when BMS capacity is missing or invalid.
- Added standalone Docker environment examples for the new layout/fallback settings.

### Notes
- Layout values are read-only checks only; they do not force BMS parsing and do not overwrite detected BMS values.
- Capacity fallback is used only for estimates when valid BMS capacity is unavailable.
- MQTT topics, Home Assistant discovery identifiers and monitor polling behavior were not changed.
- No BMS write/control commands were added.

## 2.7.0 - 2026-05-19

### Added
- Added standalone Docker support as a secondary deployment path while keeping Home Assistant add-on mode as the primary path.
- Added a Docker configuration bootstrap that creates `/data/options.json` from `config.yaml` defaults plus `PACEBMS_` environment variables when no options file exists.
- Added a standalone-friendly `docker-compose.yaml` with persistent `/data`, web UI port mapping, serial device mapping, restart policy, log rotation and healthcheck.
- Added `.env.example` and standalone Docker documentation.

### Changed
- Standardized the standalone compose file as `docker-compose.yml`.
- Mapped the configured host serial device to `/dev/pacebms` inside the container so the monitor uses a stable internal serial path.

### Notes
- Existing `/data/options.json` files are never overwritten by the Docker bootstrap.
- MQTT topics, Home Assistant discovery identifiers and monitor polling behavior were not changed.
- No BMS write/control commands were added.

## 2.6.102 - 2026-05-19

### Changed
- Fixed the Home Assistant repository metadata URL so it points to the current `serial_rs232_pacebms` repository.
- Added a root coding-skills index for future maintenance guidance.
- Removed stale one-off migration and old release-note archive files that no longer belong in the public release set.
- Redacted visible serial-number values from manual screenshots.
- Bumped the Home Assistant add-on version so the cleanup is visible as an update.

### Notes
- Repository/docs/screenshot hygiene only; no MQTT topics, Home Assistant discovery identifiers or monitor polling behavior changed.
- No BMS write/control commands were added.

## 2.6.101 - 2026-05-19

### Fixed
- Improved Telegram BMS warning detail so generic Pace warning text such as `Above cell voltage` and `Above total voltage` still produces measured cell and pack-voltage reference rows.
- Ensured same-family warning escalation can still send a Telegram alert even when the raw BMS warning text did not change.
- Kept duplicate warning suppression quiet during normal operation while still allowing first-send, escalation, cooldown reminder and clear notifications.

### Notes
- Telegram warning behavior only; no MQTT topics, Home Assistant discovery identifiers or monitor polling behavior changed.
- No BMS write/control commands were added.

## 2.6.100 - 2026-05-19

### Changed
- Updated README and manual screenshots guidance for the latest Classic UI captures across Dashboard, Tech Status, Setup, Config, Diagnostics, Events, Backups, Logs and Telegram examples.
- Refreshed First-Time Setup, Configuration, Backup/Restore, Warning Deduplication, Config Reference and Installation docs to match the current tab layout and screenshot set.
- Bumped the Home Assistant add-on version so the documentation/screenshot refresh is visible as an update.

### Notes
- Documentation/screenshots and add-on metadata only; no MQTT topics, Home Assistant discovery identifiers or monitor polling behavior changed.
- No BMS write/control commands were added.

## 2.6.99 - 2026-05-19

### Changed
- Documented MQTT/Home Assistant Discovery stability rules for base topic, discovery topic and pack/cell padding.
- Aligned README MQTT examples with the current default `pack_01` / `cell_01` topic format.
- Added Config help warnings that changing pack/cell padding after Home Assistant discovery can create duplicate or stale entities.

### Notes
- Documentation and Config help only; no MQTT topics, Home Assistant discovery identifiers or monitor polling behavior changed.
- No BMS write/control commands were added.

## 2.6.98 - 2026-05-19

### Fixed
- Aligned Config info-button help text with the current card grouping for Notifications, FET Notifications, Warning Detail and Scheduled Reports.
- Fixed Config save handling for decimal-comma float fields such as `daily_energy_current_deadband_a` and battery reference voltages.
- Aligned browser validation with the add-on schema so `debug_output` is limited to 0-3 and SOC/SOH percentage threshold fields remain integer values.

### Notes
- Config changes remain Home Assistant add-on option writes only; no BMS write/control commands were added.
- No MQTT topics, Home Assistant discovery entities or monitor polling behavior changed.

## 2.6.97 - 2026-05-19

### Changed
- Added a Tech Status Pack Comparisons section title around the SOC, SOH, voltage, cell delta and cell-extreme comparison cards.

### Notes
- UI structure only; no MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.96 - 2026-05-19

### Changed
- Added clearer Tech Status section titles for Warning Intelligence and Battery Packs so the grouped cards are easier to scan.

### Notes
- UI structure only; no MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.95 - 2026-05-19

### Changed
- Reduced Backups helper-note typography so backup guidance text matches the quieter backup row support text.

### Notes
- Styling only; no MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.94 - 2026-05-19

### Changed
- Reduced Events and Backups typography weight and size so event titles, backup filenames, helper text, badges and table rows match the calmer Dashboard and Tech Status styling.

### Notes
- Styling only; no MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.93 - 2026-05-19

### Changed
- Extended the Dashboard and Tech Status compact card language across Diagnostics, Setup, Config, Events, Backups and Logs.
- Normalized support/admin tab typography, card borders, table rows, inputs, badges and action spacing for a more consistent classic UI.

### Notes
- Styling only; no MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.92 - 2026-05-19

### Changed
- Reworked Tech Status pack cards to match the compact Dashboard pack-card style while keeping identity, capacity, electrical, cell, reference and FET details visible.
- Polished Warning Intelligence cards to use the same compact card styling and metric tiles as the Dashboard and Tech Status pack cards.

### Notes
- UI layout only; no MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.91 - 2026-05-19

### Fixed
- Corrected the Dashboard Last Updated tile text to say the page auto-refreshes every 15 seconds, matching the actual refresh timer.

### Notes
- Text-only UI fix; no MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.90 - 2026-05-19

### Changed
- Tightened classic UI spacing across all tabs to reduce unused vertical space while keeping existing data visible.
- Reduced header, tab, card, tile, table, Config form and helper-note padding for a more compact Home Assistant ingress layout.

### Notes
- Styling only; no MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.89 - 2026-05-19

### Changed
- Reworked the Dashboard Pack Comparison Cards into compact themed pack cards with headline SOC, SOH, voltage and current tiles.
- Added clearer pack comparison rows for remaining/full/design capacity, projected runtime or charge estimate, cell extremes, cycles and cell delta.

### Notes
- UI layout only; no MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.88 - 2026-05-19

### Removed
- Removed the abandoned alternate light UI preview, including its route, template, stylesheet, documentation and tests.
- Returned the project to a single Home Assistant web UI to avoid confusion during future UI work.

### Notes
- UI cleanup only; no MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.87 - 2026-05-19

### Changed
- Polished the classic web UI typography to reduce oversized bold text and align the visual weight closer to the Config tab.
- Tightened card, tile, table and field spacing across the dashboard, tech status, diagnostics, logs, events, backups and setup views.

### Notes
- Styling only; no MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.81 - 2026-05-19

### Changed
- Normalized Config tab typography so card headings, friendly labels, field values, inputs, badges and reference-table text use a lighter consistent font weight.

### Notes
- Web UI styling only; saved Home Assistant add-on option keys are unchanged.
- No MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.80 - 2026-05-19

### Changed
- Hid technical option keys on the Config tab and kept only the friendly user-facing labels.
- Matched Config field label typography to the smaller Battery Profile & Alert References table label style.

### Notes
- Web UI layout and labels only; saved Home Assistant add-on option keys are unchanged.
- No MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.79 - 2026-05-19

### Fixed
- Hardened monitor startup when Home Assistant stores `debug_output` from the dropdown as text.
- Normalized monitor debug output to the supported `0..3` range everywhere before numeric comparisons.

### Notes
- Hotfix for add-on startup after the `debug_output` dropdown change.
- No MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.78 - 2026-05-19

### Changed
- Cleaned up the Config tab by showing friendly field names while keeping the original option keys visible below each label.
- Moved the general FET alert toggle into the FET Notifications card so related FET settings are grouped together.

### Notes
- Config UI layout and labels only; saved Home Assistant add-on option keys are unchanged.
- No MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.77 - 2026-05-19

### Fixed
- Changed `debug_output` from a free integer field to a fixed `0`, `1`, `2`, `3` selection in the web Config UI and Home Assistant add-on schema.
- Tightened web Config validation so `debug_output` values below `0` or above `3` are rejected.

### Notes
- If a saved add-on option currently contains `debug_output: -1`, select `0 - Normal` and save the Config page.
- No MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.76 - 2026-05-19

### Changed
- Widened the Config tab `Battery Profile & Alert References` card so the profile policy dropdown and reference table have more horizontal space.

### Notes
- Web UI layout only.
- No MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.75 - 2026-05-19

### Fixed
- Fixed a Home Assistant runtime-only web UI crash caused by `WARNING_TELEGRAM_POLICY_CHOICES` being defined after `app.run()`.
- The constant is now defined before the Flask server starts, matching both imported test behavior and Home Assistant script execution behavior.

### Notes
- No MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.74 - 2026-05-19

### Fixed
- Hardened the web UI against partial retained MQTT pack snapshots across Dashboard, Tech Status, Diagnostics and Setup.
- Missing pack fields such as highest cell, lowest cell, SOC, SOH, voltage, current, capacity, FET state or references now render as `Unknown` instead of causing an Internal Server Error.

### Notes
- This is a follow-up fix for startup/retained-MQTT timing cases where Home Assistant can open the add-on before every retained pack field is available.
- No MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.73 - 2026-05-19

### Fixed
- Prevented the web UI from crashing when retained MQTT pack snapshots are partial or missing chart fields.
- Pack comparison charts now show safe fallback values instead of raising a server error when SOC, SOH, voltage, delta or cell range values are temporarily unavailable.

### Notes
- No MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.72 - 2026-05-19

### Added
- Added a BMS warning Telegram policy for Battery Profile & Alert References:
  - alert on all BMS warnings,
  - alert on user reference exceeded plus BMS critical/protection,
  - or alert only when user reference is exceeded.
- Added per-reference Telegram alert switches for high/low cell voltage, cell delta, pack high/low voltage and high/low temperature.
- Added pack high and pack low calculated reference rows to the Battery Profile & Alert References table.

### Changed
- Telegram BMS warning notifications can now be filtered without hiding active BMS warnings in the web UI or MQTT state.
- Default BMS warning Telegram behavior now favors user reference crossings while still allowing critical/protection-level BMS warnings through.

### Notes
- No MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.71 - 2026-05-19

### Added
- Added compact Operating State cards to Tech Status and Diagnostics.
- Reused the Dashboard operating state, power flow, current and runtime/charge-time estimate logic.

### Notes
- No MQTT topics, Home Assistant discovery entities, monitor polling behavior or BMS commands changed.
- No BMS write/control commands were added.

## 2.6.70 - 2026-05-19

### Changed
- Added current Web UI screenshots to the README and support manuals.
- Added Dashboard, Tech Status, Setup, Config, Diagnostics, Logs, Events, Backups and Telegram examples to the documentation.
- Updated the screenshot guide to match the current checked-in screenshot files.
- Updated First-Time Setup, Configuration, Config Reference, Backup/Restore and Warning Deduplication docs with relevant screenshots.
- Added `AGENTS.md` and `docs/ai/` project guidance for future maintenance, safety rules, sprint workflow, config rules, alert rules, UI rules and validation.
- Added explicit cautious coding-partner and coding-style guidance for future project work.
- Expanded project context guidance with battery data points, known watch areas, deployment considerations, versioning and GitHub safety rules.
- Added focused project skill guides for serial frame debugging, voltage parsing, capacity parsing, warning/alarm handling, MQTT/Home Assistant discovery, Telegram setup, Home Assistant add-on mode and future standalone Docker mode.
- Added sprint batching and required git commit comment guidance for future GitHub uploads.
- Added sprint prompt examples for starting future review, implementation and release-note work.

### Removed
- Removed the temporary `web-ui-2.0.39-warning-reference.png` screenshot.

### Notes
- Documentation/screenshots only. No monitor logic, MQTT topics, Home Assistant discovery entities or BMS behavior changed.
- No BMS write/control commands were added.

## 2.6.69 - 2026-05-19

### Changed
- Simplified the Logs tab to one Show dropdown: Important, Battery reads and Everything.
- Made Battery reads the default Logs view so normal Analog/Warn read summaries are visible without understanding debug levels.
- Removed the Logs category dropdown and View Detail wording.
- Kept Logs search, latest 400-line sampling, oldest/newest timestamps and 15-second soft refresh.
- Preserved the selected Logs view, search text and information panel state during automatic refresh.
- Moved Battery Profile & References to the bottom of the Config cards and widened it to reduce table scrolling.
- Moved the daily energy current deadband to the bottom of Scheduled Reports so report times stay grouped together.
- Included warning read and warning-related lines in the Logs Important view.

### Fixed
- Added config save/load coverage for upgraded default options, blank sensitive fields and restart-required save messaging.
- Confirmed config saves still write Home Assistant add-on options only and do not write anything to the BMS.

### Notes
- Logs filtering is display-only. Changing the Logs view does not change what the monitor records.
- No MQTT topics, Home Assistant discovery entity names or BMS write/control behavior were changed.

## 2.6.68 - 2026-05-19

### Changed
- Reworked the Config tab Battery Profile & References card into a measured/reference/user-defined table.
- Added profile-aware reference preview updates when the battery profile dropdown changes.
- Added full help text for the Battery Profile & References info button.
- Reorganized Config cards so FET notification settings, scheduled reports and battery reference settings are no longer mixed into unrelated sections.
- Moved the daily energy current deadband into Scheduled Reports where the daily summary behavior is configured.

### Notes
- Battery profile/reference values remain read-only display and notification references.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.67 - 2026-05-18

### Added
- Added read-only Battery Profile references for Auto, P13S / Hubble AM2 and P16S / Eenovance MANA LFP warning interpretation.
- Added `battery_profile` and `daily_energy_current_deadband_a` configuration options.
- Added a Config action to clear Telegram warning suppression/cooldown state without writing anything to the BMS.
- Added tested battery/model-number documentation for Hubble AM2 P13S and Eenovance MANA P16S packs.

### Changed
- Warning Intelligence and Telegram warning detail now show measured values beside configured/profile references and notification state.
- Daily summary energy tracking now follows the dashboard power-flow convention: positive current charges, negative current discharges.
- Daily summaries now avoid useless `0.000 kWh` lines and report no measurable energy movement when appropriate.
- Daily summaries now include SOC movement and warnings observed during the day.
- Duplicate-suppressed BMS warning logs are silent during normal operation and only appear at deeper debug output.
- Fixed the Config tab sanitized YAML download link.

### Notes
- Battery profile references are display/notification references only. They do not configure or write to the BMS.
- No BMS write/control commands were added.
- MQTT topics and Home Assistant discovery entity names were not changed.

## 2.6.66 - 2026-05-18
### Changed
- Changed version number to upgrade addon in HA

## 2.6.65 - 2026-05-18

### Changed
- Replaced partial live-field auto-refresh with quiet full active-tab refresh for Dashboard, Tech Status, Setup, Diagnostics and Logs.
- Set Dashboard soft refresh to 15 seconds.
- Added Logs sample time-span context with oldest and newest captured line timestamps.
- Added Logs viewer help explaining Refresh Logs, the latest 400-line sample and display-only filtering.
- Removed Open Config and Restart Add-on actions from the Logs tab.
- Preserved the Logs viewer information panel open/closed state during soft refresh.
- Changed the Logs default View Detail to Detailed so captured Analog/Warn read summaries are visible immediately.
- Renamed the quietest Logs view to Alerts / events only so it is clear that it can be empty during normal operation.

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
