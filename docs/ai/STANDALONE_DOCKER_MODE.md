# Standalone Docker Mode

Standalone Docker mode is a possible future deployment mode, not the current priority.

Do not refactor for standalone Docker unless the maintainer starts that sprint.

## Expected Pieces

Standalone Docker may need:

- `Dockerfile`
- `docker-compose.yml`
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

The current `docker-compose.yaml` uses `/dev:/dev` and privileged mode. A future Docker sprint may tighten this.

## Config Strategy

Future standalone Docker work should decide whether configuration comes from:

- mounted `config.yaml`
- `/data/options.json`
- environment variables
- `.env`

Do not mix strategies casually. Keep Home Assistant add-on behavior stable.

## Safety

Standalone Docker must keep the same read-only BMS rules as the add-on.

