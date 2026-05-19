# Standalone Docker Mode

Standalone Docker mode is a supported secondary deployment path.

Home Assistant add-on mode remains the primary deployment path. Do not refactor
core monitor behavior around Docker-only assumptions.

## Expected Pieces

Standalone Docker may need:

- `Dockerfile`
- `docker-compose.yaml`
- `.env.example`
- README instructions
- restart policy
- config/log volume
- serial device mapping
- MQTT environment variables
- Telegram environment variables
- health check

## Serial Device Mapping

Example:

```yaml
devices:
  - /dev/ttyUSB0:/dev/ttyUSB0
```

The current `docker-compose.yaml` should map a specific serial device using
`PACEBMS_SERIAL_DEVICE` instead of requiring broad `/dev:/dev` access.

## Config Strategy

Standalone Docker uses `/data/options.json` as the runtime configuration file.
On first start, `standalone_config.py` creates it from `config.yaml` defaults and
`PACEBMS_` environment variables if it does not already exist.

Do not overwrite an existing `/data/options.json`.

Do not spread Docker environment variable reads through the monitor code. Keep
the conversion layer in the standalone bootstrap so the Home Assistant add-on
and standalone Docker share one runtime option format.

## Safety

Standalone Docker must keep the same read-only BMS rules as the add-on.
