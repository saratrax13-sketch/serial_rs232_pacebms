"""Read-only battery profile reference helpers for PaceBMS monitoring.

These values are used only for UI and notification interpretation. They never
write BMS settings or change BMS thresholds.
"""

PROFILE_AUTO = "auto"
PROFILE_CUSTOM = "custom"
PROFILE_P13S_AM2 = "p13s_hubble_am2"
PROFILE_P16S_MANA = "p16s_eenovance_mana"

BATTERY_PROFILE_CHOICES = {
    PROFILE_AUTO: "Auto detect from cell count",
    PROFILE_P13S_AM2: "P13S / Hubble AM2 51V",
    PROFILE_P16S_MANA: "P16S / Eenovance MANA LFP 51.2V",
    PROFILE_CUSTOM: "Custom references",
}

BATTERY_PROFILE_DEFAULTS = {
    PROFILE_P13S_AM2: {
        "label": BATTERY_PROFILE_CHOICES[PROFILE_P13S_AM2],
        "cell_count": 13,
        "cell_high": 4.20,
        "cell_low": 3.00,
        "delta_mv": 100,
        "temp_high": 55,
        "temp_low": 0,
        "note": "13S 51V profile. Pack high reference is 13 x 4.20 V = 54.60 V.",
    },
    PROFILE_P16S_MANA: {
        "label": BATTERY_PROFILE_CHOICES[PROFILE_P16S_MANA],
        "cell_count": 16,
        "cell_high": 3.51,
        "cell_low": 2.80,
        "delta_mv": 50,
        "temp_high": 55,
        "temp_low": 0,
        "note": "16S LFP profile based on 44.8-56.16 V operating range.",
    },
}


def normalize_profile(value):
    profile = str(value or PROFILE_AUTO).strip().lower()
    aliases = {
        "p13s": PROFILE_P13S_AM2,
        "hubble": PROFILE_P13S_AM2,
        "hubble_am2": PROFILE_P13S_AM2,
        "p16s": PROFILE_P16S_MANA,
        "eenovance": PROFILE_P16S_MANA,
        "mana": PROFILE_P16S_MANA,
        "lfp": PROFILE_P16S_MANA,
    }
    profile = aliases.get(profile, profile)
    return profile if profile in BATTERY_PROFILE_CHOICES else PROFILE_AUTO


def detect_profile(cell_count):
    try:
        cells = int(cell_count or 0)
    except Exception:
        cells = 0
    if cells >= 15:
        return PROFILE_P16S_MANA
    if cells == 13:
        return PROFILE_P13S_AM2
    return PROFILE_CUSTOM


def _as_float(value, default):
    try:
        return float(value)
    except Exception:
        return float(default)


def effective_warning_references(config, cell_count=None):
    """Return read-only references for warning explanations.

    Auto mode selects a known profile from detected cell count. Custom mode uses
    the user-configured reference values directly.
    """
    config = config or {}
    requested = normalize_profile(config.get("battery_profile", PROFILE_AUTO))
    detected = detect_profile(cell_count)
    effective = detected if requested == PROFILE_AUTO else requested

    configured_high = _as_float(config.get("notify_cell_high_warn_voltage", 4.20), 4.20)
    configured_low = _as_float(config.get("notify_cell_low_warn_voltage", 3.00), 3.00)
    configured_delta = _as_float(config.get("notify_cell_delta_warn_mv", 100), 100)
    configured_temp_high = _as_float(config.get("notify_temp_high_warn_c", 55), 55)
    configured_temp_low = _as_float(config.get("notify_temp_low_warn_c", 0), 0)

    if effective in BATTERY_PROFILE_DEFAULTS:
        profile = BATTERY_PROFILE_DEFAULTS[effective]
        cell_high = float(profile["cell_high"])
        cell_low = float(profile["cell_low"])
        delta_mv = float(profile["delta_mv"])
        temp_high = float(profile["temp_high"])
        temp_low = float(profile["temp_low"])
        source = "profile"
        label = str(profile["label"])
        note = str(profile["note"])
    else:
        cell_high = configured_high
        cell_low = configured_low
        delta_mv = configured_delta
        temp_high = configured_temp_high
        temp_low = configured_temp_low
        source = "custom"
        label = BATTERY_PROFILE_CHOICES[PROFILE_CUSTOM]
        note = "Custom user-configured warning references."

    try:
        cells = int(cell_count or 0)
    except Exception:
        cells = 0

    return {
        "requested_profile": requested,
        "detected_profile": detected,
        "effective_profile": effective,
        "profile_label": label,
        "source": source,
        "note": note,
        "cell_high": cell_high,
        "cell_low": cell_low,
        "pack_high": cell_high * cells if cells else None,
        "pack_low": cell_low * cells if cells else None,
        "delta_mv": delta_mv,
        "temp_high": temp_high,
        "temp_low": temp_low,
        "cell_count": cells,
        "uses_configured_values": source == "custom",
    }
