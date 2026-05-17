# Screenshot Guide

Use this folder for project screenshots used in the README, support notes and release notes.

Recommended screenshots:

1. `ha-addon-config-basic-required.png`
   - Home Assistant add-on Configuration tab.
   - Show the Basic Required fields near the top.
   - Hide or crop passwords, Telegram token, Telegram chat ID and MQTT password.

2. `web-ui-status-monitoring-health.png`
   - Pace BMS web UI Status tab.
   - Include Overall Status, Monitoring Health and Setup Checklist.
   - This is the best first screenshot for support.

3. `web-ui-test-full-monitoring.png`
   - Status tab after pressing Test Full Monitoring.
   - Show the result message.
   - This confirms MQTT, Telegram configuration and thresholds without BMS writes.

4. `web-ui-dashboard-pack-comparison.png`
   - Dashboard tab with detected packs and pack comparison cards.
   - Include Monitoring Snapshot when possible.

5. `telegram-example-alert.png`
   - Example Telegram alert.
   - Hide chat/user details if sharing publicly.

Screenshot safety:

- Never expose the full Telegram bot token.
- Never expose the Telegram chat ID if the screenshot is public.
- Never expose the MQTT password.
- The add-on serial path is normally safe to show and helps troubleshooting.

