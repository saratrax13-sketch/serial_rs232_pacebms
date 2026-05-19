# Alert Rules

Telegram alerts are for user confidence and fault awareness. They should be clear, not noisy.

## Alert Types

The add-on may send:

- startup notification
- stopped/disconnect notification
- stale-data alert
- stale-data recovery alert
- SOC low alert
- SOC high / fully charged alert
- SOH alert
- BMS warning alert
- BMS warning reminder
- BMS warning cleared alert
- FET alert
- daily summary
- cell delta report

## Warning Severity

Warning severity is used to control Telegram repeat noise:

- Caution: BMS warning is active but measured values are still inside configured references.
- Warning: measured values are near or outside normal references, but not a protection/fault condition.
- Critical: protection/fault states, FET disabled by protection, or measured values beyond configured critical references.

Keep severity behavior conservative. If uncertain, alert with explanation rather than hide risk.

## Warning Detail Content

BMS Warning messages and Warning Intelligence should include:

- Quick Metrics:
  - Highest Cell
  - Lowest Cell
  - Delta
  - Pack Voltage
  - SOC
  - SOH
  - Cycles
- BMS Warning Details:
  - cells reported above/below limit by the BMS
  - each relevant measured cell value
  - reference value
  - margin to reference
  - status such as Not exceeded, At reference or Exceeded
  - pack voltage reference comparison where relevant
- Reference Check
- Interpretation
- Suggested Action

The detail should make it clear when the BMS warning is active below the configured UI/Telegram reference.

## Deduplication

Do not spam Telegram for the same ongoing warning family.

Send when:

- a warning first appears
- warning family changes
- repeat cooldown expires
- severity changes enough to matter
- warning clears

Suppress duplicates silently during normal operation.

Duplicate-suppressed debug lines should not appear in normal logs. Show them only at deeper debug levels or in the Logs Everything view if they were captured.

## Logs Important View

Logs Important must include warning-related lines, including:

- `Warn read OK`
- active `warnings=...` summaries
- warning sent/cleared/reminder lines
- protection/fault/stale/recovery lines
- duplicate suppressed warning lines when present in captured logs

