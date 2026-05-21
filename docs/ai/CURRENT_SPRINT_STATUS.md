# Current Sprint Status

Use this file as the quick handover note for a fresh Codex thread.

Update it when a sprint is started, paused, completed or handed over. Keep it short and current.

## Current State

- Home Assistant add-on is the primary deployment mode.
- Standalone Docker is supported as a secondary deployment mode.
- Classic UI is the active UI.
- Serial-first monitoring is the active architecture.
- MQTT is optional output/fallback, not the primary UI source.
- The monitor owns `/data/pacebms-live.json` and `/data/pacebms_metrics.db`.

## Open Sprint

- No active sprint recorded in this handover file.

## Latest Sprint Outcome

- Version `2.9.48` is prepared but uncommitted for a full operational UI audit sprint.
- Added regression coverage for all main tab buttons, rendered link/form route reachability, live refresh API payload contracts and stable serial-first values across Dashboard, Tech Status and Diagnostics.
- Added MQTT discovery stability regression coverage confirming discovery topics, `unique_id` values and advertised state topics remain unique across padding edge cases.
- Added MQTT discovery/state publisher coverage confirming advertised Home Assistant discovery state topics are backed by the serial monitor's MQTT state publishers.
- Added serial monitor regression coverage confirming the poll helpers use only the expected read-only Pace CID2 requests: version, serial number, analog data, pack capacity and warning/status.
- Replaced remaining MQTT-specific live-status wording with serial-first live-data wording in Dashboard, Tech Status and Diagnostics refresh/status messages.
- Operational audit found and fixed an unclosed SQLite connection in the per-pack cell history API used by History refreshes.
- Validation passed for `2.9.48`: compile, full unit suite (`104` tests), config coverage, rendered template JavaScript syntax check and `git diff --check` with only Windows CRLF normalization warnings.
- Live Home Assistant validation passed for `2.9.48`: the add-on was installed/updated on the live host, Dashboard, Tech Status, Diagnostics, History, Setup, Config, Events, Backups and Logs passed a user-facing click-through, and no new duplicate Home Assistant MQTT discovery entities or stale retained discovery topics were observed.
- Version `2.9.47` is prepared but uncommitted for Warning Intelligence and BMS Caution UI cleanup.
- BMS-reported warnings below configured user references now show as `BMS Caution` instead of top-level `Warning`, while reference-exceeded cases still escalate to Warning/Critical.
- Warning Intelligence now keeps active BMS warning context visible but hides user alert reference rows when measured values are safely inside configured references.
- BMS-reported warning detail rows now show measured cell/pack voltage, reference and margin rows for below-reference BMS cautions.
- Backend/API regression coverage confirms a normal BMS warning read clears warning count, pack severity, Warning Intelligence rows and BMS cell warning labels.
- Status and Diagnostics soft refresh now reload detailed warning sections when the live warning signature changes, so stale BMS warning badges do not linger after the BMS resets.
- Tech Status and Diagnostics now keep Overall Status as BMS Caution while Operating State shows actual power-flow state such as Charging, Discharging, Idle or Fully charged.
- Live serial Warning Intelligence now uses current add-on options for cell-delta references, alert toggles and BMS warning Telegram policy.
- The Warning Intelligence Telegram section is labelled BMS Warning Telegram Decision to avoid confusion with SOC/SOH/FET Telegram alerts.
- Validation passed for `2.9.47`: compile, full unit suite (`98` tests), config coverage and `git diff --check` with only Windows CRLF normalization warnings.
- Live Home Assistant validation passed for `2.9.47`: Pack 01 showed BMS Caution for BMS-only below-reference warnings, Tech Status/Diagnostics Operating State showed the power-flow state instead of repeating BMS Caution, and Status/Diagnostics cleared warning badges after `/data/pacebms-live.json` reported `"warnings": "Normal"`.
- Version `2.9.42` prepared Warning Intelligence and Telegram warning-detail row filtering.
- Warning Intelligence now hides user alert reference rows when the measured value is still safely inside the configured reference, while keeping active BMS warning context and explanation visible.
- Detailed Telegram warning output now hides non-exceeded high-cell and pack-voltage comparison rows, but still shows rows at the reference boundary or beyond it.
- Added regression coverage for hiding safe high-voltage, cell-delta and pack-voltage rows and for showing exceeded rows.
- Validation passed: compile, full unit suite, config coverage and `git diff --check` with only Windows CRLF normalization warnings.
- Version `2.9.41` committed in `e6839b5 fix cell delta report SQLite window handling`.
- Cell Delta Report now uses the just-finished SQLite overnight window after midnight instead of selecting a future window.
- Cell Delta Report includes pack IDs found in SQLite `pack_metrics` even when the runtime pack count is lower.
- Added regression coverage for overnight windows and persisted history pack IDs.
- Validation passed: compile, full unit suite, config coverage and `git diff --check` with only Windows CRLF normalization warnings.
- Standalone Docker smoke validation passed on Ubuntu VM `192.168.10.88`: Docker image built from the committed `2.9.41` snapshot, `/data/options.json` was bootstrapped, web UI `/`, `/health`, `/api/live` and `/api/history` returned HTTP 200, and the temporary validation container was removed.

## Recent Focus Areas

- Serial-first live snapshot and SQLite history.
- Daily summary SQLite energy and warning-event reporting.
- Cell delta report SQLite overnight-window and history-pack handling.
- History graph usability and tab refresh stability.
- Telegram warning deduplication and warning clarity.
- Config save/load behavior and reference-value consistency.
- Classic UI polish across Dashboard, History, Tech Status, Diagnostics, Setup and Config.

## Known Watch Areas

- Live Home Assistant add-on validation for `2.9.40` Daily Summary and `2.9.41` Cell Delta Report has not yet been run against a real BMS-backed `/data/pacebms_metrics.db`.
- Standalone Docker smoke validation used `/dev/null` instead of real BMS hardware, so it did not create `/data/pacebms-live.json` from a valid serial read.
- Daily summaries should keep using SQLite `pack_metrics` and `warning_events` for restart-safe energy movement and warnings.
- Cell delta reports should keep using SQLite `pack_metrics`, including overnight windows and persisted pack IDs.
- Warning Intelligence must keep separating BMS-reported warnings from user alert references.
- Reference comparison rows should not be shown as warnings when the measured value is safely inside the configured reference; keep active BMS warning context visible separately as BMS Caution. This was live-validated in `2.9.47`.
- Home Assistant visible hotfixes require a version bump in `config.yaml`, README Current Version and `CHANGELOG.md`.
- Do not rename MQTT discovery IDs, topics or Home Assistant entities without explicit migration approval. Padding, base topic, discovery topic and BMS serial changes remain retained-discovery migration risks even when the current code emits unique IDs.

## Next Recommended Validation

```powershell
python -m py_compile bms_monitor.py bms_notify.py web_config.py constants.py supervisor.py tests\test_core_behaviour.py battery_profiles.py bms_live.py bms_history.py standalone_config.py
python -m unittest discover -s tests -v
git diff --check
```

For future live add-on/container validation, run inside the PaceBMS container:

```sh
ls -lh /data/pacebms-live.json
ls -lh /data/pacebms_metrics.db*
```

Next recommended step: review the uncommitted `2.9.48` changes and commit/upload when ready.
