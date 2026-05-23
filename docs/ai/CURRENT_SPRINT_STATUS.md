# Current Sprint Status

Use this file as the quick handover note for a fresh Codex thread.

Update it when a sprint is started, paused, completed or handed over. Keep it short and current.

## Current State

- Release version is `2.10.6`.
- Home Assistant add-on is the primary deployment mode.
- Standalone Docker is supported as a secondary deployment mode.
- Classic UI is the active UI.
- Serial-first monitoring is the active architecture.
- MQTT is optional output/fallback, not the primary UI source.
- The monitor owns `/data/pacebms-live.json` and `/data/pacebms_metrics.db`.
- Main and dev were previously aligned at the `2.10.0` normal-use release commit. Main now carries Home Assistant visible UI/reference hotfixes through `2.10.6`.

## Open Sprint

- No active implementation sprint recorded.

## Latest Sprint Outcome

- `2.10.6` is the latest Home Assistant visible Diagnostics cell reference hotfix.
- Detailed Pack & Cell Data now includes a display-only `OCV Ref` column beside the existing cell `Status` column for Hubble AM2/P13S NMC cell voltage reference bands.
- The Hubble AM2 NMC voltage/SOC reference table is available in a popup from the `OCV Ref` header and is color-coded by reference risk band.
- Existing cell `Status` labels, BMS warning labels, Telegram policy, MQTT discovery/entity names and monitor polling behavior were not changed.
- `2.10.5` added Diagnostics live-source clarity fields.
- Diagnostics Detailed Pack & Cell Data now shows the live data source, serial snapshot age, last analog read and last warning read directly on the card.
- Those live-source fields refresh from `/api/status` alongside the per-pack and per-cell values while the Diagnostics tab is open.
- `2.10.4` fixed generic BMS high/low warning candidate cell labels.
- Generic BMS high-cell and low-cell warnings now mark the relevant high-side or low-side candidate cell group in Detailed Pack & Cell Data instead of only marking the single highest or lowest cell.
- Exact BMS warning text that names specific cells still marks only those reported cells.
- MQTT-fallback cell detail normalization now keeps all rendered cell rows when building pack cell details.
- `2.10.3` fixed remaining Tech Status and Diagnostics live refresh gaps.
- Tech Status Warning Intelligence now refreshes live quick metrics, BMS warning details, reference checks, Telegram decision text, interpretation and suggested action from `/api/status` while the tab is open.
- Tech Status Battery Packs now refresh live per-pack values, capacity, cell balance, reference and FET state fields from `/api/status`.
- Diagnostics Battery Configuration now refreshes topology summary tiles and the pack topology table from `/api/status`.
- `2.10.2` fixed Diagnostics Detailed Pack & Cell Data live updates.
- `2.10.0` was marked as the normal-use release.
- Added close-off documentation:
  - `INSTALL.md`
  - `FIRST_TIME_SETUP.md`
  - `CONFIG_REFERENCE.md`
  - `CONFIG_BACKUP_RESTORE.md`
  - `docs/FINAL_ACCEPTANCE_TEST.md`
- Added `scripts/docker_smoke_test.ps1` for standalone Docker startup/UI health validation.
- Updated live Home Assistant Web UI screenshots for the `2.10.0` Classic UI.
- Added `docs/screenshots/History.png`.
- Updated README and setup/install/manual screenshot guidance for Dashboard, Tech Status, History, Setup, Config, Diagnostics, Events, Backups and Logs.
- Screenshot privacy guidance now explicitly requires redacting Home Assistant usernames and battery serial numbers, plus Telegram/MQTT secrets.
- Live screenshot capture was performed against the Home Assistant add-on UI at version `2.10.0`; saved screenshots were redacted before commit.

## Recent Validation

- Python compile passed:

```powershell
python -B -m py_compile bms_monitor.py bms_notify.py web_config.py constants.py supervisor.py tests\test_core_behaviour.py battery_profiles.py bms_live.py bms_history.py standalone_config.py
```

- Unit tests passed: `110` tests.

```powershell
python -m unittest discover -s tests -v
```

- Config/schema/Web UI group coverage passed with all empty lists.
- Markdown image link validation passed with `all_markdown_images_exist`.
- `git diff --check` passed with only the known Windows README line-ending warning.
- Local Docker validation could not run on the Windows host because `docker` was not available on PATH.
- Standalone Docker startup/UI smoke validation passed on Ubuntu VM `192.168.10.88` using `/dev/null`: image built, container started, `/health` returned `200`, `/api/status` returned `200`, and the temporary container was removed.

## Recent Focus Areas

- Serial-first live snapshot and SQLite history.
- Daily summary SQLite energy and warning-event reporting.
- Cell delta report SQLite overnight-window and history-pack handling.
- History graph usability and tab refresh stability.
- Telegram warning deduplication and warning clarity.
- Config save/load behavior and reference-value consistency.
- Classic UI polish across Dashboard, History, Tech Status, Diagnostics, Setup and Config.
- MQTT discovery stability and duplicate-entity prevention.
- Standalone Docker startup/UI smoke validation support.
- Close-off docs and screenshot/manual readiness.
- Home Assistant packaging review for the working `2.10.0` add-on layout.

## Known Watch Areas

- Standalone Docker tests using `/dev/null` validate build, startup, Web UI and health endpoints only. They do not validate real serial reads or Pace frame parsing.
- If packaging files change, rerun Home Assistant add-on validation and standalone Docker smoke validation.
- Daily summaries should keep using SQLite `pack_metrics` and `warning_events` for restart-safe energy movement and warnings.
- Cell delta reports should keep using SQLite `pack_metrics`, including overnight windows and persisted pack IDs.
- Warning Intelligence must keep separating BMS-reported warnings from user alert references.
- Reference comparison rows should not be shown as warnings when the measured value is safely inside the configured reference; keep active BMS warning context visible separately as BMS Caution.
- Home Assistant visible hotfixes require a version bump in `config.yaml`, README Current Version and `CHANGELOG.md`.
- Do not rename MQTT discovery IDs, topics or Home Assistant entities without explicit migration approval. Padding, base topic, discovery topic and BMS serial changes remain retained-discovery migration risks even when the current code emits unique IDs.
- Screenshots committed to the repo must not expose Telegram tokens, Telegram chat IDs, MQTT passwords, Home Assistant usernames or real battery serial numbers.

## Next Recommended Validation

For code or release handoff:

```powershell
python -B -m py_compile bms_monitor.py bms_notify.py web_config.py constants.py supervisor.py tests\test_core_behaviour.py battery_profiles.py bms_live.py bms_history.py standalone_config.py
python -m unittest discover -s tests -v
git diff --check
```

For future live add-on/container validation, run inside the PaceBMS container:

```sh
ls -lh /data/pacebms-live.json
ls -lh /data/pacebms_metrics.db*
```

For standalone Docker validation on a Docker host:

```powershell
.\scripts\docker_smoke_test.ps1
```

Next recommended step: install/update the Home Assistant add-on to `2.10.6`, set `ui_data_source` to `monitor_live` if pure serial-only UI data is required, then confirm Detailed Pack & Cell Data keeps the existing Status column while showing OCV Ref bands and the Hubble reference popup.
