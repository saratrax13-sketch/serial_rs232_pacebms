# Installation

This is the short close-off install entrypoint for Pace BMS RS232 Monitor.

Release: `2.10.0`

The primary deployment mode is the Home Assistant add-on. Standalone Docker is supported for normal Docker hosts, but it uses the same read-only serial monitor and the same `/data/options.json` runtime model.

## Home Assistant Add-on

1. Open Home Assistant.
2. Go to **Settings > Add-ons > Add-on Store**.
3. Open the three-dot menu and choose **Repositories**.
4. Add this repository:

```text
https://github.com/saratrax13-sketch/serial_rs232_pacebms
```

5. Install **Pace BMS RS232 Monitor**.
6. Configure the serial device, baud rate and optional MQTT/Telegram settings.
7. Start the add-on.
8. Open the web UI from the Home Assistant sidebar.

For the detailed install guide, use [docs/INSTALL.md](docs/INSTALL.md).

Current Web UI screenshots are shown in the README and maintained in [docs/screenshots/README.md](docs/screenshots/README.md). They cover Dashboard, Tech Status, History, Setup, Config, Diagnostics, Events, Backups and Logs.

## Standalone Docker

1. Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

2. Edit `.env` for your serial device and optional MQTT/Telegram values.
3. Build and start:

```powershell
docker compose up -d --build
```

4. Open:

```text
http://localhost:8099
```

For the detailed standalone guide, use [docs/STANDALONE_DOCKER.md](docs/STANDALONE_DOCKER.md).

## Safety

The monitor is read-only to the BMS. It reads Pace RS232/UART data and does not write thresholds, control FETs, reset the BMS, calibrate values or change battery settings.
