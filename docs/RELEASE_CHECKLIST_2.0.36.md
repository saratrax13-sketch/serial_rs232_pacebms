# PaceBMS 2.0.36 Release Checklist

## Version

- [ ] `config.yaml` version is set to `2.0.36`
- [ ] `CHANGELOG.md` has the `2.0.36` entry at the top
- [ ] README reflects the current stable feature set

## Functional checks

- [ ] Add-on starts
- [ ] MQTT connects
- [ ] Telegram startup message works
- [ ] Home Assistant sensors update
- [ ] Web UI opens
- [ ] Overall Status is correct
- [ ] Detected Battery Layout is correct
- [ ] Last Analog Read updates
- [ ] Last Warning Read updates
- [ ] Data Stale is OFF during normal operation
- [ ] Last Events shows startup events
- [ ] Test Telegram button works
- [ ] Test MQTT button works
- [ ] Stop add-on sends Monitor Stopped
- [ ] Disconnect battery-side serial cable sends BMS Disconnected
- [ ] Reconnect sends BMS Reconnected

## Public GitHub safety

- [ ] No real Telegram bot token in `config.yaml`
- [ ] No real Telegram chat ID in `config.yaml`
- [ ] No real MQTT password in `config.yaml`
- [ ] No private credentials in README
- [ ] No private credentials in CHANGELOG
- [ ] No local-only notes that should not be public

## Release

- [ ] Commit changes
- [ ] Push to GitHub
- [ ] Check Home Assistant Add-on Store updates
- [ ] Rebuild/update add-on
- [ ] Restart add-on
- [ ] Confirm stable operation
