# UI Rules

The Web UI should be organized by audience and task.

Classic UI is the active UI. Do not replace it or reintroduce alternate UI experiments unless the maintainer explicitly asks.

## Main Views

### Dashboard

User confidence view. Show simple combined battery health:

- operating state
- SOC
- combined SOH
- battery power
- runtime or charge-time estimate
- voltage/current
- remaining and full/design capacity
- temperature
- active warnings
- last updated

### Tech Status

Technician live view. Show:

- overall live status
- warning intelligence
- quick metrics
- per-pack identity
- capacity
- electrical values
- cell balance
- reference limits
- FET state
- comparison charts

Avoid setup/test buttons here.

### Setup

First-run and confidence checks:

- setup checklist
- MQTT test
- Telegram test
- Full Monitoring dry test

### Config

Grouped add-on options. Keep cards purpose-based and avoid duplicates.

### Diagnostics

Support proof:

- health overview
- battery identity
- detailed cell data
- support report downloads

### Logs

Simple support log viewer:

- Show: Important, Battery reads, Everything
- Search
- Refresh
- Download
- latest 400 captured lines
- oldest/newest timestamps
- 15-second refresh while open

Do not reintroduce a complex View Detail plus Category model.

## Visual Preferences

- Keep buttons compact and aligned.
- Prefer one clear action row over scattered buttons.
- Avoid duplicate cards and repeated fields.
- Avoid user-facing explanatory clutter in daily-use views.
- Place detailed help behind info buttons/details panels.
- Keep Battery Profile & References wide enough to avoid horizontal scrolling.
