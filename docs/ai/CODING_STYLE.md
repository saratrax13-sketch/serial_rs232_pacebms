# Coding Style

Agents working on this project should behave like cautious coding partners.

The add-on handles real battery monitoring and alerting data, including BMS alarms, SOC, SOH, cell voltage, pack voltage, current, capacity, Telegram notifications, Home Assistant integration and add-on deployment. Code should be understandable, defensive and easy to support.

## Prefer

- readable code over clever code
- clear function names
- small, focused changes
- defensive parsing for BMS frames, MQTT payloads, retained-state values and config inputs
- centralized constants for thresholds, defaults and repeated labels
- explicit validation for user-provided config
- useful comments for non-obvious protocol, safety or alerting behavior
- tests for warning logic, config save/load behavior and UI routes
- version numbers, changelog entries and release notes for release work

## Avoid

- magic numbers scattered through the code
- silent exception swallowing
- fake defaults that make missing BMS data look real
- broad rewrites without a clear safety reason
- changing unrelated files
- renaming MQTT topics, Home Assistant discovery IDs or config keys without explicit approval
- introducing BMS write/control behavior

## Error Handling

Do not hide failures that affect battery monitoring, alerting, config saves, MQTT publishing or Telegram delivery.

If a value is missing or not reported by the BMS, show `Unknown`, `Not reported`, or a clear equivalent instead of inventing a value.

If a parser must tolerate malformed input, keep the fallback narrow and log enough context for support without exposing secrets.

