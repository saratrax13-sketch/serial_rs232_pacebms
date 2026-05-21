# Home Assistant Packaging Review

Release reviewed: `2.10.0`

This note records a conservative packaging review for the Home Assistant add-on
path. The add-on is working in Home Assistant, so packaging changes should be
made only when they reduce maintenance risk or improve Home Assistant build
compatibility without changing runtime behavior.

## Current Packaging

- `config.yaml` is the Home Assistant add-on metadata and options schema.
- `Dockerfile` builds from `python:3.11-slim`.
- `run.sh` starts the standalone/options bootstrap and supervisor.
- `supervisor.py` starts the web UI and serial monitor as sibling processes.
- `repository.yaml` identifies the add-on repository.
- Ingress is enabled on port `8099`.
- Watchdog uses `/health`.
- `uart: true` and `usb: true` are declared for serial hardware access.

## Review Outcome

No immediate packaging change is required for the working `2.10.0` add-on.

The current package is acceptable for the active Home Assistant add-on flow
because it has:

- Home Assistant add-on metadata in `config.yaml`.
- A Dockerfile that builds and starts the app.
- Ingress and watchdog settings.
- Architecture list coverage.
- Serial hardware declarations.
- A release version visible to Home Assistant.

## Optional Future Improvements

These are polish items, not blockers:

- Consider adding `build.yaml` only if Home Assistant build tooling or future
  multi-arch build requirements need per-architecture base image control.
- Keep the Dockerfile base explicit unless there is a tested reason to move to
  Home Assistant base images. Current Home Assistant app guidance supports
  explicit `FROM` statements, and changing the base image would need a full
  Home Assistant and standalone Docker validation pass.
- Consider adding a `DOCS.md` file if the repository is prepared for broader
  Home Assistant add-on store presentation. The README and docs already cover
  installation and use.
- Keep `config.yaml` option names stable. Renaming options would affect saved
  add-on configuration.
- Keep ingress port, MQTT discovery IDs, MQTT topics and entity identifiers
  stable unless a migration is explicitly approved.

## Do Not Change Casually

- Do not replace the working `run.sh`/`supervisor.py` startup path without a
  full Home Assistant and standalone Docker validation pass.
- Do not change the add-on slug unless the maintainer accepts a reinstall or
  migration path.
- Do not change MQTT discovery identifiers or topic naming as part of packaging
  cleanup.
- Do not add privileged access unless a real serial hardware issue proves it is
  necessary.

## Validation For Packaging Changes

If any packaging files change, run:

```powershell
python -B -m py_compile bms_monitor.py bms_notify.py web_config.py constants.py supervisor.py tests\test_core_behaviour.py battery_profiles.py bms_live.py bms_history.py standalone_config.py
python -m unittest discover -s tests -v
git diff --check
```

Then validate:

- Home Assistant rebuild/update sees the expected version.
- Add-on starts and Ingress opens.
- `/health` responds.
- `/api/status` responds.
- Serial reads still work with a real BMS.
- Standalone Docker smoke test still passes.
