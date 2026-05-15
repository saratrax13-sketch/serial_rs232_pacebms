# PaceBMS — Pace BMS to MQTT Bridge

A Python-based bridge for **Pace BMS** battery management systems that publishes real-time battery data to MQTT, with full **Home Assistant auto-discovery** support.

Connects via **TCP/IP or Serial (USB-RS485)**, supports **multiple packs** (auto-detected), and runs as a **Home Assistant addon**, standalone **Docker container**, or direct Python script.

---

## File Versions

| File | Version | Changed | Notes |
|------|---------|---------|-------|
| `bms_monitor.py` | 2.1.0 | 2026-05-16 | Added Telegram notifications, BMS status/error MQTT topics, startup/shutdown events |
| `constants.py` | 1.0.0 | 2026-05-16 | Pace BMS protocol constants, CID2 codes, warning/protection state maps |
| `config.yaml` | 2.0.6 | 2026-05-16 | Added Telegram token/chat_id, switched to Serial mode, zero_pad_number_packs=0 |
| `automations.yaml` | 1.0.0 | 2026-05-16 | HA automations for BMS startup, shutdown, disconnect, and recovery notifications |

---

## Features

- Reads cell voltages, temperatures, current, voltage, SOC, SOH, cycles, and capacity per pack
- Publishes all data to MQTT with change-detection — only publishes when values change, minimising HA recorder writes
- Full Home Assistant MQTT Discovery — sensors appear in HA automatically with correct device class and units
- **Supports multiple battery packs (dynamic — no hardcoded cell or pack count)**
- Availability topic — HA shows the device as unavailable if the monitor stops
- **Telegram notifications** — direct Bot API calls for pre-MQTT startup warnings and fatal errors
- **BMS status MQTT topic** — startup and shutdown events published to `pacebms/bms_status`
- **BMS error MQTT topic** — disconnect and recovery events with retry count and offline duration published to `pacebms/bms_error`
- **HA automations** — phone and Telegram notifications for all BMS events
- Runs as an HA addon, standalone Docker container, or direct Python script
- Serial (USB-RS485) and TCP/IP connection modes
- Structured logging with configurable debug levels

---

## Supported Hardware

| BMS | Connection | Tested |
|-----|-----------|--------|
| Pace BMS P16S200A | Serial (USB) | Yes |
| Pace BMS AM-x series (Hubble AM2) | Serial (USB-RS485) | Yes |
| Pace BMS AM-x series | TCP/IP | Yes |

The protocol is compatible with other Pace-based BMS units using the same RS485/UART frame format.

### Hubble AM2 Notes

- The AM2 has two communication ports: RS485 and RS232
- Connect only to the **RS485 port** on the **master battery** using a USB-RS485 adapter with RJ45 connector
- Link multiple batteries together using standard RJ45 LAN cables via the Battery Link port
- Set DIP switches: master = address 1, slave = address 2
- The RS485 port uses the **Pace BMS protocol** (not Modbus)
- Hubble officially reserves the RS485 port for firmware updates — use at your own risk

---

## Requirements

- Python 3.11+
- MQTT broker (e.g. Mosquitto)
- Home Assistant (optional — for auto-discovery and notifications)
- USB-to-RS485 adapter with RJ45 connector (for Hubble AM2 and similar)

Python dependencies (see `requirements.txt`):
```
paho-mqtt
pyserial
pyyaml
```

No additional dependencies needed for Telegram — uses Python's built-in `urllib`.

---

## Installation

### Option A — Home Assistant Addon (recommended)

1. In Home Assistant go to **Settings -> Add-ons -> Add-on Store**
2. Click the three-dot menu -> **Repositories**
3. Add: `https://github.com/saratrax13-sketch/serial_rs485_pacebms`
4. Find **BMS Pace** in the store and click **Install**
5. Configure via the addon **Configuration** tab (see [Configuration](#configuration) below)
6. Click **Start**

### Option B — Docker Compose (standalone)

```bash
git clone https://github.com/saratrax13-sketch/serial_rs485_pacebms.git
cd pacebms
```

Edit `config.yaml` with your settings, then:

```bash
docker compose up -d
```

To view logs:
```bash
docker compose logs -f
```

### Option C — Direct Python

```bash
git clone https://github.com/saratrax13-sketch/serial_rs485_pacebms.git
cd pacebms
pip install -r requirements.txt
python3 bms_monitor.py
```

The script looks for config at `/data/options.json` (HA addon) or `pace-bms-dev/config.yaml` (local).

---

## Configuration

All settings are in `config.yaml` under the `options` key, or via the HA addon Configuration tab.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `telegram_bot_token` | string | — | Telegram bot token from @BotFather |
| `telegram_chat_id` | string | — | Telegram chat ID from @userinfobot |
| `mqtt_host` | string | — | IP address of your MQTT broker |
| `mqtt_port` | int | `1883` | MQTT broker port |
| `mqtt_user` | string | — | MQTT username |
| `mqtt_password` | string | — | MQTT password |
| `mqtt_base_topic` | string | `pacebms` | Root MQTT topic |
| `mqtt_ha_discovery` | bool | `true` | Enable HA auto-discovery |
| `mqtt_ha_discovery_topic` | string | `homeassistant` | HA discovery prefix (must match HA config) |
| `connection_type` | `IP` or `Serial` | `Serial` | How the BMS is connected |
| `bms_ip` | string | — | BMS IP address (IP mode only) |
| `bms_port` | int | `5000` | BMS TCP port (IP mode only) |
| `bms_serial` | string | `/dev/ttyUSB0` | Serial device path (Serial mode only) |
| `bms_baudrate` | int | `9600` | Serial baud rate (Serial mode only) |
| `scan_interval` | int | `5` | Seconds between full BMS polls |
| `zero_pad_number_cells` | int | `2` | Zero-pad cell topic names (`cell_01` vs `cell_1`) |
| `zero_pad_number_packs` | int | `0` | Zero-pad pack topic names — `0` disables padding (`pack_1`, `pack_2`) |
| `debug_output` | int | `0` | `0`=info only, `1`=debug, `3`=raw frames |

> `force_pack_offset` has been deprecated and removed. The parser now auto-detects pack boundaries.

### Finding your serial device path

On the HA host or RPi4 via SSH:
```bash
ls /dev/serial/by-id/
```
Use the full `by-id` path — it stays stable across reboots unlike `/dev/ttyUSB0`.

---

## MQTT Topics

All topics are published under `{mqtt_base_topic}/` (default: `pacebms/`).

### Per-pack topics

| Topic | Unit | Description |
|-------|------|-------------|
| `pacebms/pack_1/v_cells/cell_01` | mV | Individual cell voltage |
| `pacebms/pack_1/temps/temp_1` | °C | Temperature sensor |
| `pacebms/pack_1/v_pack` | V | Pack voltage |
| `pacebms/pack_1/i_pack` | A | Pack current (negative = charging) |
| `pacebms/pack_1/soc` | % | State of charge |
| `pacebms/pack_1/soh` | % | State of health |
| `pacebms/pack_1/i_remain_cap` | Ah | Remaining capacity |
| `pacebms/pack_1/i_full_cap` | Ah | Full charge capacity |
| `pacebms/pack_1/i_design_cap` | Ah | Design capacity |
| `pacebms/pack_1/cycles` | — | Charge cycle count |
| `pacebms/pack_1/cells_max_diff_calc` | mV | Max cell voltage spread |
| `pacebms/pack_1/warnings` | — | Active warning string |
| `pacebms/pack_1/balancing1` | — | Cell balancing state bits |
| `pacebms/pack_1/balancing2` | — | Cell balancing state bits |
| `pacebms/pack_1/charge_fet` | ON/OFF | Charge FET state |
| `pacebms/pack_1/discharge_fet` | ON/OFF | Discharge FET state |
| `pacebms/pack_1/prot_short_circuit` | ON/OFF | Short circuit protection active |

### Aggregate topics

| Topic | Unit | Description |
|-------|------|-------------|
| `pacebms/pack_remain_cap` | Ah | Total remaining capacity across all packs |
| `pacebms/pack_full_cap` | Ah | Total full capacity |
| `pacebms/pack_soc` | % | Overall SOC |
| `pacebms/pack_soh` | % | Overall SOH |
| `pacebms/availability` | online/offline | Bridge availability (LWT) |
| `pacebms/bms_version` | — | BMS firmware version |
| `pacebms/bms_sn` | — | BMS serial number |

### Status and error topics

| Topic | Payload | Description |
|-------|---------|-------------|
| `pacebms/bms_status` | JSON | Startup and shutdown events |
| `pacebms/bms_error` | JSON | Disconnect and recovery events |

#### bms_status payloads

```json
// Startup
{"status": "startup", "bms_sn": "ABC123", "bms_version": "1.23"}

// Shutdown
{"status": "shutdown", "bms_sn": "ABC123"}
```

#### bms_error payloads

```json
// Disconnected
{"status": "disconnected", "retry_count": 3, "offline_time": "1m 15s", "offline_secs": 75}

// Recovered
{"status": "recovered", "retry_count": 3, "offline_time": "1m 15s", "offline_secs": 75}
```

---

## Notifications

The script sends notifications through two channels:

### Direct Telegram (pre-MQTT)
Used for early startup warnings before MQTT is connected:
- `Could not retrieve BMS version` — BMS may still be booting
- `Cannot retrieve BMS serial` — fatal error, monitor exiting

Requires `telegram_bot_token` and `telegram_chat_id` in config. Uses Python's built-in `urllib` — no extra dependencies.

### Home Assistant Automations (via MQTT)
Once MQTT is connected, all events are published as JSON to MQTT topics and picked up by HA automations that notify via phone and Telegram:

| Event | Topic | Channels |
|-------|-------|----------|
| BMS monitor started | `pacebms/bms_status` | Phone + Telegram |
| BMS monitor stopped | `pacebms/bms_status` | Phone + Telegram |
| BMS disconnected | `pacebms/bms_error` | Phone + Telegram |
| BMS recovered | `pacebms/bms_error` | Phone + Telegram |

### Setting up Telegram

1. Create a bot via [@BotFather](https://t.me/botfather) — get your `bot_token`
2. Get your `chat_id` via [@userinfobot](https://t.me/userinfobot)
3. Add to HA `configuration.yaml`:

```yaml
telegram_bot:
  - platform: polling
    api_key: "YOUR_BOT_TOKEN"
    allowed_chat_ids:
      - YOUR_CHAT_ID

notify:
  - name: telegram
    platform: telegram
    chat_id: YOUR_CHAT_ID
```

4. Add `telegram_bot_token` and `telegram_chat_id` to `config.yaml`
5. Copy `automations.yaml` content into your HA `automations.yaml`

---

## Home Assistant

When `mqtt_ha_discovery: true`, all sensors register automatically in HA under a single **Generic Lithium** device.

Sensors include correct `device_class` and `state_class`:
- Cell and pack voltages -> `device_class: voltage`
- Current -> `device_class: current`
- Temperatures -> `device_class: temperature`
- SOC/SOH -> `device_class: battery`

Binary sensors (FETs, protections) use `ON`/`OFF` payloads natively.

Discovery topics are re-published automatically every hour and immediately after any reconnect.

---

## Architecture

```
BMS Hardware (Hubble AM2 / Pace BMS)
    |
    +-- Serial USB-RS485 (master battery only)
    +-- TCP/IP
            |
    +-------+--------+
    |  Transport     |  bms_connect / bms_send / bms_recv
    +-------+--------+
            |
    +-------+--------+
    |  Protocol      |  bms_request / bms_parse_response / checksums
    +-------+--------+
            |
    +-------+--------+
    |  Data Model    |  AnalogData / PackData / PackCapacity / WarnData
    +-------+--------+
            |
    +-------+--------+
    |  MQTT Publisher|  publish_analog_data / publish_warn_data / ha_discovery
    +-------+--------+
            |
         MQTT Broker --> Home Assistant
            |
    +-------+--------+
    | Notifications  |  Telegram (direct) + HA automations (phone + Telegram)
    +----------------+
```

---

## Debugging

Set `debug_output` in config:

| Level | What you see |
|-------|-------------|
| `0` | Startup, connect, pack summary per poll |
| `1` | Skipped bytes between packs, cell/temp arrays |
| `3` | Raw request and response frames (hex) |

Logs are available via:
```bash
# HA addon
Settings -> Add-ons -> BMS Pace -> Logs

# Docker
docker compose logs -f

# Direct Python
python3 bms_monitor.py
```

---

## Troubleshooting

**Sensors show `Unknown` in HA**
Delete stale retained MQTT topics using MQTT Explorer, then restart the addon to re-run discovery.

**Only some cells showing**
The parser auto-detects pack boundaries. Set `debug_output: 1` to see skipped bytes.

**`zero_pad_number_cells: 0`**
Causes topics like `cell_1`, `cell_10`, `cell_2` which sort incorrectly. Keep at `2` for `cell_01`-`cell_16`.

**Serial not connecting**
Use the full `by-id` path for `bms_serial`. Check the HA addon has `uart: true` and `usb: true` in config.

**Checksum errors in logs**
Usually indicates a noisy serial connection or wrong baud rate. Try `bms_baudrate: 9600`. Set `debug_output: 3` to inspect raw frames. Add termination (120 ohm) and bias resistors to the RS485 line.

**`Could not retrieve BMS version` warning**
The BMS may still be booting. The monitor will continue and attempt to read the serial number. A Telegram notification is sent directly if `telegram_bot_token` and `telegram_chat_id` are configured.

**Telegram notifications not working**
Check `telegram_bot_token` and `telegram_chat_id` in `config.yaml`. Ensure the bot has been started by sending it a `/start` message in Telegram first.

---

## Contributing

Pull requests welcome. Please test against a live BMS if possible and include relevant log output.

---

## License

MIT

---

## Acknowledgements

Originally based on the [bmspace](https://github.com/Tertiush/bmspace) project by Tertiush.
