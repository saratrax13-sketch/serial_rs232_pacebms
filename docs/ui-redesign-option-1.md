# PACE BMS Monitor UI Redesign - Option 1

This redesign keeps the current Home Assistant add-on UI intact and adds a separate light operations dashboard first.

## Design Direction

Use a neat, sleek, tidy operations dashboard.

The app should feel like a professional battery monitoring tool for:

- normal users
- installers
- technicians

Avoid:

- bulky layouts
- oversized cards
- full dark dashboards
- unnecessary animations
- hiding stale, invalid or unavailable values

## Implementation Direction For This Repository

This repository currently uses Flask and Jinja templates, not React.

Use:

- `templates/index_option1.html`
- `static/option1.css`
- `static/option1.js` only if needed
- existing Flask data from `web_config.py`

Do not introduce React, Vite, shadcn/ui or a new frontend build system unless the maintainer explicitly decides to migrate later.

The new UI must be accessible separately from the existing UI:

- `/option1`
- `/?ui=option1`

The current UI must remain available.

## Required Tabs

- Overview
- Packs
- Cells
- Warnings
- Diagnostics
- Raw Data
- Settings

## Core Visual Principles

- light background
- white cards
- soft borders
- small rounded cards
- compact spacing
- clear typography
- no oversized panels
- no unnecessary animations
- warnings visible but not alarming unless critical
- stale or invalid data shown clearly

## Data Display Rules

The UI must never hide bad data.

- valid value: show the value
- null or undefined: show `No data`
- NaN: show `Invalid`
- stale timestamp: show `Stale`
- unavailable backend value: show a visible warning

## Main Data Fields

### Combined / Bank

- combined SOC
- combined average pack voltage
- combined remaining capacity
- combined full capacity
- combined design capacity
- combined highest cell voltage
- combined lowest cell voltage
- combined cell delta
- combined projected runtime or charge time

### Pack Data

For each detected pack:

- pack label
- role: Master or Slave
- status: Normal, Warning, Critical or Offline
- SOC
- SOH
- voltage
- current
- power
- remaining capacity Ah
- full capacity Ah
- design capacity Ah
- temperature
- highest cell number and voltage
- lowest cell number and voltage
- cell delta mV
- runtime
- charging time
- last packet time
- warnings

### Cell Data

For each detected pack:

- detected cell voltages
- highest cell highlighted
- lowest cell indicated
- cell delta
- high-cell reference threshold

Do not hardcode 13 cells. Render the detected cell count so both 13S and 16S packs work.

### Warning Logic

If the BMS reports `Above cell voltage` but the highest cell is below the configured high-cell reference, show this as:

`Watch condition`

Do not show it as emergency shutdown unless BMS protection/fault severity or measured values justify critical status.

### Diagnostics

Show:

- MQTT status
- backend/API status
- polling interval
- last packet
- stale data handling
- NaN filtering
- unavailable handling
- master/slave aggregation
- cell count

### Settings Display

Show the most important monitoring/configuration values:

- high cell reference
- cell delta watch
- low SOC warning
- critical SOC
- stale data timeout
- Telegram notifications
- repeated warning protection
- back online notification
- warning explanation text

These are Home Assistant add-on settings only. They must not write to the BMS.

