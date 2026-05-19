# Home Assistant Add-on Mode

Home Assistant add-on mode is the current primary deployment mode.

## Required Files

Check these files when changing add-on behavior:

- `config.yaml`
- `Dockerfile`
- `run.sh`
- `README.md`
- `web_config.py`
- `templates/index.html`

## Required Config Areas

`config.yaml` should include schema/options for:

- serial port
- baud rate
- scan interval
- MQTT host/user/password
- MQTT discovery and retain settings
- Telegram enable
- Telegram token
- Telegram chat ID
- notification toggles
- warning thresholds/repeat intervals
- logging/debug level
- version

## Add-on Store / Repository Notes

When repo name, add-on slug or URL changes, Home Assistant may still look for old metadata.

Check:

- repository URL
- add-on slug
- `config.yaml` name
- `panel_title`
- add-on store cache
- retained MQTT discovery topics

## Ingress/Web UI

The Web UI runs behind Home Assistant Ingress. Keep routes relative/Ingress-safe.

Do not assume static assets behave the same as a normal standalone web server.

## Safety

The add-on may save Home Assistant add-on options.

It must not write to the BMS.

