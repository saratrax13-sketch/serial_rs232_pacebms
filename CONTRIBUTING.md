# Contributing

Contributions are welcome.

## Project Principles

This project should remain:

- Read-only to the BMS
- Safe for Home Assistant use
- Clear and easy to configure
- Useful for Pace-compatible BMS systems, not only one battery brand

## Read-Only Rule

Do not add BMS write/control commands without very clear review and explicit documentation.

The normal monitor should only read data from the BMS.

## Development Workflow

1. Fork or clone the repository.
2. Create a feature branch.
3. Make changes.
4. Test in Home Assistant.
5. Update README/CHANGELOG if needed.
6. Submit a pull request.

## Versioning

Use patch versions for small changes:

```text
2.0.41
2.0.42
2.0.43
```

Avoid accidental major version jumps such as:

```text
20.0.41
```

## Testing Checklist

Before submitting:

- Add-on starts
- MQTT connects
- Home Assistant sensors update
- Web UI opens
- Test Telegram works
- Test MQTT works
- Data Stale behaves correctly
- No secrets are committed
