# PaceBMS — Pace BMS to MQTT Bridge

A Python-based bridge for **Pace BMS** battery management systems that publishes real-time battery data to MQTT, with full **Home Assistant auto-discovery** support.

Connects via **TCP/IP or Serial (USB)**, supports **multiple packs**, and runs as a **Home Assistant addon** or standalone **Docker container**.

---

## Features

- Reads cell voltages, temperatures, current, voltage, SOC, SOH, cycles, and capacity per pack
- Publishes all data to MQTT with change-detection — only publishes when values change, minimising HA recorder writes
- Full Home Assistant MQTT Discovery — sensors appear in HA automatically with correct device class and units
- Supports multiple battery packs (dynamic — no hardcoded cell or pack count)
- Availability topic — HA shows the device as unavailable if the monitor stops
- Runs as an HA addon or standalone Docker container
- Serial (USB) and TCP/IP connection modes
- Structured logging with configurable debug levels

---

## Supported Hardware

| BMS | Connection | Tested |
|-----|-----------|--------|
| Pace BMS P16S200A | Serial (USB) | ✅ |
| Pace BMS AM-x series | TCP/IP | ✅ |

The protocol is compatible with other Pace-based BMS units using the same RS485/UART frame format.

---

## Requirements

- Python 3.11+
- MQTT broker (e.g. Mosquitto)
- Home Assistant (optional — for auto-discovery)
- USB-to-serial adapter or network-connected BMS

Python dependencies (see `requirements.txt`):
```
paho-mqtt
pyserial
pyyaml
```

---

## Installation

### Option A — Home Assistant Addon (recommended)

1. In Home Assistant go to **Settings → Add-ons → Add-on Store**
2. Click the three-dot menu → **Repositories**
3. Add: `https://github.com/broubart/pacebms`
4. Find **BMS Pace** in the store and click **Install**
5. Configure via the addon **Configuration** tab (see [Configuration](#configuration) below)
6. Click **Start**

### Option B — Docker Compose (standalone)

```bash
git clone https://github.com/broubart/pacebms.git
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
git clone https://github.com/broubart/pacebms.git
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
| `mqtt_host` | string | — | IP address of your MQTT broker |
| `mqtt_port` | int | `1883` | MQTT broker port |
| `mqtt_user` | string | — | MQTT username |
| `mqtt_password` | string | — | MQTT password |
| `mqtt_base_topic` | string | `bmspace` | Root MQTT topic |
| `mqtt_ha_discovery` | bool | `true` | Enable HA auto-discovery |
| `mqtt_ha_discovery_topic` | string | `homeassistant` | HA discovery prefix (must match HA config) |
| `connection_type` | `IP` or `Serial` | `IP` | How the BMS is connected |
| `bms_ip` | string | — | BMS IP address (IP mode only) |
| `bms_port` | int | `5000` | BMS TCP port (IP mode only) |
| `bms_serial` | string | `/dev/ttyUSB0` | Serial device path (Serial mode only) |
| `bms_baudrate` | int | `9600` | Serial baud rate (Serial mode only) |
| `scan_interval` | int | `5` | Seconds between full BMS polls |
| `zero_pad_number_cells` | int | `2` | Zero-pad cell topic names (`cell_01` vs `cell_1`) |
| `zero_pad_number_packs` | int | `1` | Zero-pad pack topic names (`pack_01` vs `pack_1`) |
| `force_pack_offset` | int | `0` | Legacy — leave at `0` |
| `debug_output` | int | `0` | `0`=info only, `1`=debug, `3`=raw frames |

### Finding your serial device path

On the HA host via SSH:
```bash
ls /dev/serial/by-id/
```
Use the full `by-id` path — it stays stable across reboots unlike `/dev/ttyUSB0`.

---

## MQTT Topics

All topics are published under `{mqtt_base_topic}/` (default: `bmspace/`).

### Per-pack topics

| Topic | Unit | Description |
|-------|------|-------------|
| `bmspace/pack_01/v_cells/cell_01` | mV | Individual cell voltage |
| `bmspace/pack_01/temps/temp_1` | °C | Temperature sensor |
| `bmspace/pack_01/v_pack` | V | Pack voltage |
| `bmspace/pack_01/i_pack` | A | Pack current (negative = charging) |
| `bmspace/pack_01/soc` | % | State of charge |
| `bmspace/pack_01/soh` | % | State of health |
| `bmspace/pack_01/i_remain_cap` | mAh | Remaining capacity |
| `bmspace/pack_01/i_full_cap` | mAh | Full charge capacity |
| `bmspace/pack_01/i_design_cap` | mAh | Design capacity |
| `bmspace/pack_01/cycles` | — | Charge cycle count |
| `bmspace/pack_01/cells_max_diff_calc` | mV | Max cell voltage spread |
| `bmspace/pack_01/warnings` | — | Active warning string |
| `bmspace/pack_01/balancing1` | — | Cell balancing state bits |
| `bmspace/pack_01/balancing2` | — | Cell balancing state bits |
| `bmspace/pack_01/charge_fet` | ON/OFF | Charge FET state |
| `bmspace/pack_01/discharge_fet` | ON/OFF | Discharge FET state |
| `bmspace/pack_01/prot_short_circuit` | ON/OFF | Short circuit protection active |

### Aggregate topics

| Topic | Unit | Description |
|-------|------|-------------|
| `bmspace/pack_remain_cap` | mAh | Total remaining capacity across all packs |
| `bmspace/pack_full_cap` | mAh | Total full capacity |
| `bmspace/pack_soc` | % | Overall SOC |
| `bmspace/pack_soh` | % | Overall SOH |
| `bmspace/availability` | online/offline | Bridge availability (LWT) |
| `bmspace/bms_version` | — | BMS firmware version |
| `bmspace/bms_sn` | — | BMS serial number |

---

## Home Assistant

When `mqtt_ha_discovery: true`, all sensors register automatically in HA under a single **Generic Lithium** device.

Sensors include correct `device_class` and `state_class` for the HA Energy Dashboard:
- Cell and pack voltages → `device_class: voltage`
- Current → `device_class: current`
- Temperatures → `device_class: temperature`
- SOC/SOH → `device_class: battery`
- Capacities → `device_class: energy`

Binary sensors (FETs, protections) use `ON`/`OFF` payloads natively.

Discovery topics are re-published automatically every hour, and immediately after any reconnect.

---

## Architecture

```
BMS Hardware
    │
    ├── Serial (USB/RS485)
    └── TCP/IP
            │
    ┌───────▼────────┐
    │  Transport     │  bms_connect / bms_send / bms_recv
    └───────┬────────┘
            │
    ┌───────▼────────┐
    │  Protocol      │  bms_request / bms_parse_response / checksums
    └───────┬────────┘
            │
    ┌───────▼────────┐
    │  Data Model    │  AnalogData / PackData / PackCapacity / WarnData
    └───────┬────────┘
            │
    ┌───────▼────────┐
    │  MQTT Publisher│  publish_analog_data / publish_warn_data / ha_discovery
    └───────┬────────┘
            │
         MQTT Broker → Home Assistant
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
Settings → Add-ons → BMS Pace → Logs

# Docker
docker compose logs -f
```

---

## Troubleshooting

**Sensors show `Unknown` in HA**
Delete stale retained MQTT topics using MQTT Explorer, then restart the addon to re-run discovery.

**Only some cells showing**
Check `force_pack_offset` — set it to `0`. The parser auto-detects pack boundaries.

**`zero_pad_number_cells: 0`**
Causes topics like `cell_1`, `cell_10`, `cell_2` which sort incorrectly. Set to `2` for `cell_01`–`cell_16`.

**Serial not connecting**
Use the full `by-id` path for `bms_serial`. Check the HA addon has `uart: true` and `usb: true` in config.

**Checksum errors in logs**
Usually indicates a noisy serial connection or wrong baud rate. Try `bms_baudrate: 9600`. Set `debug_output: 3` to inspect raw frames.

---

## Contributing

Pull requests welcome. Please test against a live BMS if possible and include relevant log output.

---

## License

MIT

---

## Acknowledgements

Originally based on the [bmspace](https://github.com/Tertiush/bmspace) project by Tertiush.
