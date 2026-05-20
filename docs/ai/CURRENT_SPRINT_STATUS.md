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

- Version `2.9.45` is prepared but uncommitted for all-tabs BMS Caution UI alignment.
- Overall status, dashboard operating state, monitoring health and warning health cards now use BMS Caution for BMS-reported warnings below configured user references.
- Added regression coverage so below-reference BMS warnings remain visible as caution without top-level Warning labels.
- Version `2.9.44` prepared a Home Assistant test build for restored BMS Caution warning detail rows.
- Version `2.9.43` is prepared but uncommitted for Warning Intelligence UI severity polish.
- Web UI now shows BMS-reported warnings below configured user references as BMS Caution instead of Warning.
- BMS-reported warning details now still show measured cell/pack voltage, reference and margin rows for below-reference BMS cautions.
- Diagnostics cell badges now style BMS-only warning labels as caution, while reference crossings still use alert styling.
- Live serial Warning Intelligence now uses current add-on options for cell-delta references, alert toggles and BMS warning Telegram policy.
- The Warning Intelligence Telegram section is now labelled BMS Warning Telegram Decision to avoid confusion with SOC/SOH/FET Telegram alerts.
- Added regression coverage for BMS-only below-reference UI caution handling and made history-report tests deterministic around day-boundary windows.
- Validation passed: compile, full unit suite, config coverage and `git diff --check` with only Windows CRLF normalization warnings.
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
- Warning Intelligence must separate BMS-reported warnings from user alert references.
- Reference comparison rows should not be shown as warnings when the measured value is safely inside the configured reference; keep active BMS warning context visible separately as BMS Caution.
- Home Assistant visible hotfixes require a version bump in `config.yaml`, README Current Version and `CHANGELOG.md`.
- Do not rename MQTT discovery IDs, topics or Home Assistant entities without explicit migration approval.

## Next Recommended Validation

```powershell
python -m py_compile bms_monitor.py bms_notify.py web_config.py constants.py supervisor.py tests\test_core_behaviour.py battery_profiles.py bms_live.py bms_history.py standalone_config.py
python -m unittest discover -s tests -v
git diff --check
```

For live add-on/container validation, run inside the PaceBMS container:

```sh
ls -lh /data/pacebms-live.json
ls -lh /data/pacebms_metrics.db*
```

Next recommended step: after validation, install/update the Home Assistant add-on to `2.9.43` on the live Home Assistant host, confirm Warning Intelligence shows Pack 01 as BMS Caution for BMS-only below-reference warnings, and confirm reference-exceeded cases still show as Warning/Critical.
