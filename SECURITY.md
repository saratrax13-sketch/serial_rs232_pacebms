# Security Policy

## Read-Only BMS Safety

This project is intended to monitor Pace-compatible BMS batteries in a read-only manner.

The monitor is designed to read:

- BMS version
- BMS serial number
- Analog pack data
- Pack capacity
- Warning/status information

The project should not send write/control commands to the BMS.

It should not:

- Change BMS settings
- Write protection thresholds
- Enable or disable charge/discharge FETs
- Send BMS control commands

## Reporting a Security Issue

If you discover a security issue, please do not publish sensitive details publicly.

Open a private communication with the repository owner where possible, or create a GitHub issue with minimal non-sensitive details and mark it clearly as a security concern.

## Secrets and Credentials

Do not commit real credentials to the repository.

Never commit:

- Telegram bot tokens
- Telegram chat IDs, if private
- MQTT passwords
- Private broker credentials
- Local network secrets
- Home Assistant long-lived access tokens

Use placeholders in examples:

```yaml
telegram_bot_token: "YOUR_TELEGRAM_BOT_TOKEN"
telegram_chat_id: "YOUR_TELEGRAM_CHAT_ID"
mqtt_user: "YOUR_MQTT_USER"
mqtt_password: "YOUR_MQTT_PASSWORD"
```

## Supported Versions

Security fixes should normally be made against the latest stable release.
