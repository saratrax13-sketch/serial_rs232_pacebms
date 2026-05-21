# Final Acceptance Test

Use this checklist before treating the project as ready for normal use.

Release: `2.10.0`

## Static Validation

- [ ] Confirm clean repo state:

```powershell
git status --short --branch
```

- [ ] Compile core Python files:

```powershell
python -B -m py_compile bms_monitor.py bms_notify.py web_config.py constants.py supervisor.py tests\test_core_behaviour.py battery_profiles.py bms_live.py bms_history.py standalone_config.py
```

- [ ] Run unit tests:

```powershell
python -m unittest discover -s tests -v
```

- [ ] Check whitespace:

```powershell
git diff --check
```

- [ ] Confirm config coverage:

```powershell
@'
import yaml
import web_config
with open("config.yaml", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)
options = set((cfg.get("options") or {}).keys())
schema = set((cfg.get("schema") or {}).keys())
groups = []
for keys in web_config.GROUPS.values():
    groups.extend(keys)
group_set = set(groups)
print("options_not_in_schema", sorted(options - schema))
print("schema_not_in_options", sorted(schema - options))
print("options_not_in_groups", sorted(options - group_set - web_config.DEPRECATED_OPTION_KEYS))
print("groups_not_in_options", sorted(group_set - options))
print("duplicate_group_keys", sorted([key for key in group_set if groups.count(key) > 1]))
'@ | python -
```

Expected output is all empty lists.

## Home Assistant Add-on

- [ ] Home Assistant sees the expected version from `config.yaml`.
- [ ] Add-on installs or rebuilds cleanly.
- [ ] Add-on starts without a crash.
- [ ] Logs are readable and do not expose secrets.
- [ ] Web UI opens through Ingress.
- [ ] Dashboard loads.
- [ ] Tech Status loads.
- [ ] Diagnostics loads.
- [ ] History loads.
- [ ] Setup loads.
- [ ] Config loads.
- [ ] Events loads.
- [ ] Backups loads.
- [ ] Logs loads.

## Serial Connection

- [ ] Correct serial device path is configured.
- [ ] `bms_baudrate` is `9600` unless the BMS requires otherwise.
- [ ] Logs show `BMS serial connected`.
- [ ] Logs show `Analog read OK`.
- [ ] Logs show `Warn read OK`.
- [ ] `/data/pacebms-live.json` exists after valid reads.
- [ ] `/data/pacebms_metrics.db` exists when history is enabled.
- [ ] Unplugging the serial cable shows disconnected/stale/offline clearly.
- [ ] Reconnecting serial recovers automatically.

## Valid Data

- [ ] Detected pack count is correct.
- [ ] Detected cell count is correct.
- [ ] 13S Hubble AM2 packs show 13 cells, not 16.
- [ ] Pack voltage is plausible for the battery family.
- [ ] Pack current and power direction are plausible.
- [ ] SOC and SOH are plausible.
- [ ] Remaining, full and design capacity display in Ah.
- [ ] Highest cell, lowest cell and cell delta match the cell table.
- [ ] Runtime or charge-time estimate matches charging/discharging/idle state.

## Invalid Data

- [ ] Corrupt/checksum-invalid serial frames are rejected.
- [ ] Invalid reads do not publish fake MQTT values.
- [ ] Invalid reads do not overwrite the last good live snapshot as fresh.
- [ ] Stale data is shown as stale, unavailable or offline.

## Warnings

- [ ] BMS warnings remain visible even below user references.
- [ ] Below-reference BMS-only warnings show as BMS Caution.
- [ ] User-reference exceeded values show measured value, reference and margin.
- [ ] Warning badges clear after the BMS reports normal for the configured confirmation reads.
- [ ] Telegram warning policy is explained in Warning Intelligence.
- [ ] Warning repeats respect severity-specific cooldowns.

## Telegram

- [ ] Placeholder token/chat ID values are rejected.
- [ ] Test Telegram sends when real values are configured.
- [ ] Test Full Monitoring does not send Telegram.
- [ ] Telegram API failure is logged without crashing the app.
- [ ] Disconnect, recovery, stale-data and warning alerts match enabled settings.

## MQTT and Home Assistant Discovery

- [ ] MQTT disabled mode runs serial web UI without MQTT.
- [ ] MQTT enabled mode connects to the broker.
- [ ] MQTT broker offline does not stop serial polling.
- [ ] MQTT reconnects automatically.
- [ ] Retained state works if enabled.
- [ ] Discovery creates expected entities.
- [ ] No duplicate entities are created.
- [ ] `mqtt_base_topic`, `mqtt_ha_discovery_topic`, `zero_pad_number_packs` and `zero_pad_number_cells` remain stable unless a migration is planned.

## Standalone Docker

- [ ] `.env` is created from `.env.example`.
- [ ] Serial device mapping is correct.
- [ ] `docker compose config` passes.
- [ ] `docker compose build` passes.
- [ ] Container starts.
- [ ] `/health` responds.
- [ ] `/api/status` responds.
- [ ] Logs are readable.

For startup-only validation without a BMS, `PACEBMS_SERIAL_DEVICE=/dev/null` can be used. This validates container build, startup, web UI and health endpoints only. It does not validate serial reads or BMS parsing.

## Close-Off

- [ ] No BMS write/control commands were added.
- [ ] No MQTT discovery/entity names were changed without approval.
- [ ] No secrets, logs, databases or local data files are tracked.
- [ ] README version, `config.yaml` version and `CHANGELOG.md` are aligned.
- [ ] Live Home Assistant add-on validation is complete.
- [ ] Standalone Docker smoke validation is complete if Docker mode is part of the release.
