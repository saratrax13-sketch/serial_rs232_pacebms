# Standalone Docker

Standalone Docker mode runs the same read-only Pace BMS monitor outside Home Assistant.

Home Assistant add-on mode and standalone Docker mode both use the same serial-first monitor. Standalone Docker is intended for users who want to run the monitor on a normal Linux host, mini PC, server, or other Docker-capable machine. MQTT/Home Assistant publishing is optional.

## Safety

Standalone Docker keeps the same safety position as the add-on:

- read-only Pace BMS serial polling only
- no BMS setting writes
- no FET control
- no threshold writes
- no calibration writes
- no TCP/IP BMS connection code

Configuration values are used for MQTT, Telegram, display and notification reference checks only.

## Files

| File | Purpose |
|---|---|
| `Dockerfile` | Builds the Python monitor image |
| `docker-compose.yml` | Standalone Docker Compose example |
| `.env.example` | Safe example environment file |
| `standalone_config.py` | Creates `/data/options.json` from defaults and env vars when missing |
| `run.sh` | Starts the config bootstrap and monitor supervisor |

## Configuration Model

The monitor still uses `/data/options.json` as the runtime configuration file.

On first standalone Docker start:

1. `standalone_config.py` checks whether `/data/options.json` exists.
2. If it exists, it is left unchanged.
3. If it does not exist, defaults are loaded from `config.yaml`.
4. Environment variables beginning with `PACEBMS_` override those defaults.
5. The result is written to `/data/options.json`.

This keeps the web UI, backups, logs, events and warning state using the same `/data` layout as the Home Assistant add-on.

## Quick Start

Copy the example environment file:

```powershell
copy .env.example .env
```

Edit `.env` and set at least:

```text
PACEBMS_SERIAL_DEVICE=/dev/ttyUSB0
PACEBMS_BMS_BAUDRATE=9600
PACEBMS_MQTT_ENABLED=false
```

Set `PACEBMS_MQTT_ENABLED=true` and provide MQTT host/user/password only if you want MQTT/Home Assistant output.

Start the container:

```powershell
docker compose up -d --build
```

Open the web UI:

```text
http://localhost:8099
```

View logs:

```powershell
docker compose logs -f
```

Stop the container:

```powershell
docker compose down
```

## Serial Device Mapping

The compose file maps the host serial device named by `PACEBMS_SERIAL_DEVICE` to a stable container path, `/dev/pacebms`. The monitor uses `/dev/pacebms` inside the container.

Common Linux example:

```text
PACEBMS_SERIAL_DEVICE=/dev/ttyUSB0
```

Stable by-id example:

```text
PACEBMS_SERIAL_DEVICE=/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_D-if00-port0
```

If your host cannot map a `/dev/serial/by-id/...` symlink cleanly, use the actual `/dev/ttyUSBx` device or adjust the compose device mapping for your host.

## Persistent Data

Standalone Docker stores runtime data in `./data` on the host, mounted to `/data` in the container.

That folder contains:

- `options.json`
- monitor health state
- warning notification state
- event history
- config backups
- support logs

The `data/` folder is ignored by Git and should not be committed.

## Environment Variables

The compose file exposes the common setup values:

| Variable | Purpose |
|---|---|
| `PACEBMS_WEB_PORT` | Host web UI port, default `8099` |
| `PACEBMS_SERIAL_DEVICE` | Host serial device mapped into the container |
| `PACEBMS_BMS_CONNECTION_MODE` | BMS connection mode. Current supported value is `Serial` |
| `PACEBMS_BMS_SERIAL` | Serial path used by the monitor inside the container. Compose sets this to `/dev/pacebms` |
| `PACEBMS_BMS_BAUDRATE` | Serial baud rate, normally `9600` |
| `PACEBMS_SCAN_INTERVAL` | Poll interval in seconds |
| `PACEBMS_UI_DATA_SOURCE` | `monitor_live`, `auto` or `mqtt_retained` |
| `PACEBMS_METRICS_ENABLED` | Enables local SQLite metrics/history |
| `PACEBMS_HISTORY_SAMPLE_SECONDS` | Bank and pack metrics sample interval |
| `PACEBMS_HISTORY_CELL_SAMPLE_SECONDS` | Cell and temperature metrics sample interval |
| `PACEBMS_HISTORY_RETENTION_DAYS` | Raw detailed history retention |
| `PACEBMS_HISTORY_EVENT_RETENTION_DAYS` | Event/rollup retention |
| `PACEBMS_MQTT_ENABLED` | Enables MQTT publishing and Home Assistant discovery |
| `PACEBMS_MQTT_HOST` | MQTT broker host |
| `PACEBMS_MQTT_PORT` | MQTT broker port |
| `PACEBMS_MQTT_USER` | MQTT username |
| `PACEBMS_MQTT_PASSWORD` | MQTT password |
| `PACEBMS_MQTT_BASE_TOPIC` | MQTT base topic, default `pacebms` |
| `PACEBMS_NOTIFY_ENABLED` | Enables direct Telegram notifications |
| `PACEBMS_TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `PACEBMS_TELEGRAM_CHAT_ID` | Telegram chat ID |
| `PACEBMS_DEBUG_OUTPUT` | Debug level `0`, `1`, `2` or `3` |
| `PACEBMS_BATTERY_PROFILE` | `auto`, `p13s_hubble_am2`, `p16s_eenovance_mana` or `custom` |
| `PACEBMS_EXPECTED_CELL_COUNT` | Optional expected total cell count; `0` means auto/detected |
| `PACEBMS_EXPECTED_PACK_COUNT` | Optional expected pack count; `0` means auto/detected |
| `PACEBMS_CAPACITY_FALLBACK_ENABLED` | Enables configured capacity fallback for estimates only when BMS capacity is unavailable |
| `PACEBMS_CAPACITY_PER_PACK_AH` | Fallback capacity per pack in Ah |

Advanced users can override any existing option by using:

```text
PACEBMS_<OPTION_KEY_IN_UPPERCASE>=value
```

Example:

```text
PACEBMS_NOTIFY_WARNING_REPEAT_CAUTION_SECONDS=21600
```

## Health Check

The Docker healthcheck calls:

```text
http://127.0.0.1:8099/health
```

This checks whether the monitor process is heartbeating. It does not mean the battery itself is healthy.

## Serial-first Validation

After startup, confirm the live snapshot, history database and graph API are available inside the container:

```sh
docker compose exec pacebms sh
ls -lh /data/pacebms-live.json
ls -lh /data/pacebms_metrics.db*
python - <<'PY'
import sqlite3
db = "/data/pacebms_metrics.db"
con = sqlite3.connect(db)
for table in ["bank_metrics", "pack_metrics", "cell_metrics", "temperature_metrics", "warning_events", "system_events"]:
    print(table, con.execute(f"select count(*) from {table}").fetchone()[0])
con.close()
PY
python - <<'PY'
import urllib.request
for url in [
    "http://127.0.0.1:8099/api/live",
    "http://127.0.0.1:8099/api/history?range_seconds=1800",
    "http://127.0.0.1:8099/static/vendor/chart.min.js",
]:
    response = urllib.request.urlopen(url, timeout=5)
    print(url, response.status, len(response.read()))
PY
```

Expected result:

- `/data/pacebms-live.json` exists after the first valid serial read.
- `/data/pacebms_metrics.db` exists when local history is enabled.
- `/api/live`, `/api/history` and the local Chart.js asset return HTTP `200`.

## Home Assistant Integration

Standalone Docker publishes MQTT state and Home Assistant discovery topics only when MQTT is enabled.

Keep these stable after Home Assistant discovers the entities:

- `mqtt_base_topic`
- `mqtt_ha_discovery_topic`
- `zero_pad_number_packs`
- `zero_pad_number_cells`

Changing them later can create duplicate or stale Home Assistant entities.
