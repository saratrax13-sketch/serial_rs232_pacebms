# Current Sprint Status

Use this file as the quick handover note for a fresh Codex thread.

Update it when a sprint is started, paused, completed or handed over. Keep it short and current.

## Current State

- Release version is `2.10.0`.
- Home Assistant add-on is the primary deployment mode.
- Standalone Docker is supported as a secondary deployment mode.
- Classic UI is the active UI.
- Serial-first monitoring is the active architecture.
- MQTT is optional output/fallback, not the primary UI source.
- The monitor owns `/data/pacebms-live.json` and `/data/pacebms_metrics.db`.
- Main and dev were previously aligned at the `2.10.0` normal-use release commit.

## Open Sprint

- No active implementation sprint recorded.

## Latest Sprint Outcome

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

Next recommended step: push `main`, then confirm Home Assistant sees the current `2.10.0` release and run the final live acceptance checklist in `docs/FINAL_ACCEPTANCE_TEST.md`.
