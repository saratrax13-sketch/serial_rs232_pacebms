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

HUBBLE_AM2_OCV_REFERENCE = [
    {
        "voltage": "> 4.20",
        "soc": "Over",
        "status": "Overvoltage",
        "risk": "Danger",
        "class": "danger",
        "note": "Above BMS high protection; cell damage risk.",
    },
    {
        "voltage": "4.18",
        "soc": "100%",
        "status": "At limit",
        "risk": "Caution",
        "class": "caution",
        "note": "Absolute full charge; only at end of charge current taper.",
    },
    {
        "voltage": "4.15",
        "soc": "99%",
        "status": "Very high",
        "risk": "Caution",
        "class": "caution",
        "note": "Prolonged time here stresses cells.",
    },
    {
        "voltage": "4.13",
        "soc": "98%",
        "status": "High",
        "risk": "Caution",
        "class": "caution",
        "note": "Top of charge range after full cycle.",
    },
    {
        "voltage": "4.10",
        "soc": "97%",
        "status": "Normal",
        "risk": "Normal",
        "class": "normal",
        "note": "Top of practical charge range.",
    },
    {"voltage": "4.05", "soc": "95%", "status": "Normal", "risk": "Normal", "class": "normal", "note": "Healthy full-charge point."},
    {"voltage": "4.00", "soc": "92%", "status": "Normal", "risk": "Normal", "class": "normal", "note": ""},
    {"voltage": "3.95", "soc": "88%", "status": "Normal", "risk": "Normal", "class": "normal", "note": ""},
    {"voltage": "3.90", "soc": "83%", "status": "Normal", "risk": "Normal", "class": "normal", "note": ""},
    {"voltage": "3.85", "soc": "77%", "status": "Normal", "risk": "Normal", "class": "normal", "note": ""},
    {"voltage": "3.80", "soc": "70%", "status": "Normal", "risk": "Normal", "class": "normal", "note": ""},
    {"voltage": "3.75", "soc": "62%", "status": "Normal", "risk": "Normal", "class": "normal", "note": ""},
    {"voltage": "3.70", "soc": "53%", "status": "Normal", "risk": "Normal", "class": "normal", "note": "Nominal voltage."},
    {"voltage": "3.65", "soc": "45%", "status": "Normal", "risk": "Normal", "class": "normal", "note": "Flat plateau region."},
    {"voltage": "3.60", "soc": "37%", "status": "Normal", "risk": "Normal", "class": "normal", "note": ""},
    {"voltage": "3.50", "soc": "25%", "status": "Normal", "risk": "Normal", "class": "normal", "note": ""},
    {
        "voltage": "3.40",
        "soc": "15%",
        "status": "Caution",
        "risk": "Caution",
        "class": "caution",
        "note": "Approaching cutoff territory.",
    },
    {
        "voltage": "3.30",
        "soc": "10%",
        "status": "Warning",
        "risk": "Warning",
        "class": "warning",
        "note": "BMS low-voltage warning zone.",
    },
    {"voltage": "3.20", "soc": "6%", "status": "Critical", "risk": "Critical", "class": "critical", "note": ""},
    {
        "voltage": "3.00",
        "soc": "2-3%",
        "status": "Protection",
        "risk": "Protection",
        "class": "protection",
        "note": "BMS discharge FET cutoff.",
    },
    {"voltage": "2.92", "soc": "0%", "status": "Danger", "risk": "Danger", "class": "danger", "note": "Irreversible damage zone."},
    {"voltage": "< 2.50", "soc": "Dead", "status": "Dead cell", "risk": "Dead", "class": "dead", "note": "Below absolute minimum."},
]

_HUBBLE_AM2_OCV_POINTS = [
    (4.18, "100%", "At limit", "caution"),
    (4.15, "99%", "Very high", "caution"),
    (4.13, "98%", "High", "caution"),
    (4.10, "97%", "Normal", "normal"),
    (4.05, "95%", "Normal", "normal"),
    (4.00, "92%", "Normal", "normal"),
    (3.95, "88%", "Normal", "normal"),
    (3.90, "83%", "Normal", "normal"),
    (3.85, "77%", "Normal", "normal"),
    (3.80, "70%", "Normal", "normal"),
    (3.75, "62%", "Normal", "normal"),
    (3.70, "53%", "Normal", "normal"),
    (3.65, "45%", "Normal", "normal"),
    (3.60, "37%", "Normal", "normal"),
    (3.50, "25%", "Normal", "normal"),
    (3.40, "15%", "Caution", "caution"),
    (3.30, "10%", "Warning", "warning"),
    (3.20, "6%", "Critical", "critical"),
    (3.00, "2-3%", "Protection", "protection"),
    (2.92, "0%", "Danger", "danger"),
]


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


def hubble_am2_ocv_reference_table():
    """Return read-only Hubble AM2 voltage/SOC reference rows for UI help."""
    return [dict(row) for row in HUBBLE_AM2_OCV_REFERENCE]


def cell_ocv_reference(voltage, profile):
    """Return a Hubble AM2 OCV reference band for display only.

    This is not live pack SOC and never changes BMS behavior, alerts or
    existing cell status labels.
    """
    if normalize_profile(profile) != PROFILE_P13S_AM2:
        return {
            "label": "N/A",
            "status": "No profile table",
            "class": "unknown",
            "note": "No OCV reference table is configured for this battery profile.",
        }

    try:
        value = float(voltage)
    except Exception:
        return {
            "label": "Unknown",
            "status": "Unknown",
            "class": "unknown",
            "note": "Cell voltage is unavailable.",
        }

    if value > 4.20:
        return {"label": "Over", "status": "Overvoltage", "class": "danger", "note": "Above Hubble AM2 OCV reference table."}
    if value > 4.18:
        return {"label": "100%", "status": "At limit", "class": "caution", "note": "Between 4.18 V and 4.20 V OCV reference rows."}
    if value < 2.50:
        return {"label": "Dead", "status": "Dead cell", "class": "dead", "note": "Below Hubble AM2 OCV reference table."}
    if value < 2.92:
        return {"label": "0%", "status": "Danger", "class": "danger", "note": "Below the 2.92 V reference row."}

    points = _HUBBLE_AM2_OCV_POINTS
    for point_v, point_soc, point_status, point_class in points:
        if abs(value - point_v) < 0.0005:
            return {
                "label": point_soc,
                "status": point_status,
                "class": point_class,
                "note": f"Matches {point_v:.2f} V OCV reference row.",
            }

    for index in range(len(points) - 1):
        upper_v, upper_soc, upper_status, upper_class = points[index]
        lower_v, lower_soc, lower_status, lower_class = points[index + 1]
        if upper_v > value > lower_v:
            label = f"{lower_soc}-{upper_soc}"
            risk_order = {"normal": 0, "caution": 1, "warning": 2, "critical": 3, "protection": 4, "danger": 5, "dead": 6}
            band_class = upper_class if risk_order.get(upper_class, 0) >= risk_order.get(lower_class, 0) else lower_class
            if band_class == "normal":
                status = "Normal"
            elif band_class == "caution":
                status = "Caution"
            elif band_class == "warning":
                status = "Warning"
            elif band_class == "critical":
                status = "Critical"
            elif band_class == "protection":
                status = "Protection"
            else:
                status = "Danger"
            return {
                "label": label,
                "status": status,
                "class": band_class,
                "note": f"Between {lower_v:.2f} V and {upper_v:.2f} V OCV reference rows.",
            }

    return {"label": "Unknown", "status": "Unknown", "class": "unknown", "note": "Outside known OCV reference rows."}


def effective_warning_references(config, cell_count=None):
    """Return read-only references for warning explanations.

    Battery profiles provide recommended/profile reference values for context,
    and active alert/reference math uses profile values until a user edits a
    reference field. This keeps profile auto-detect useful for 16S LFP defaults
    while ensuring user-defined values shown in Config are the values used by
    Warning Intelligence and Telegram after restart.
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
        profile_cell_high = float(profile["cell_high"])
        profile_cell_low = float(profile["cell_low"])
        profile_delta_mv = float(profile["delta_mv"])
        profile_temp_high = float(profile["temp_high"])
        profile_temp_low = float(profile["temp_low"])
        label = str(profile["label"])
        note = str(profile["note"])
    else:
        profile_cell_high = configured_high
        profile_cell_low = configured_low
        profile_delta_mv = configured_delta
        profile_temp_high = configured_temp_high
        profile_temp_low = configured_temp_low
        label = BATTERY_PROFILE_CHOICES[PROFILE_CUSTOM]
        note = "Custom user-configured warning references."

    try:
        cells = int(cell_count or 0)
    except Exception:
        cells = 0

    force_configured = effective == PROFILE_CUSTOM

    def active_reference(configured, default, profile_value):
        if force_configured:
            return configured, True
        if abs(float(configured) - float(default)) > 1e-9:
            return configured, True
        return profile_value, False

    cell_high, high_is_user = active_reference(configured_high, 4.20, profile_cell_high)
    cell_low, low_is_user = active_reference(configured_low, 3.00, profile_cell_low)
    delta_mv, delta_is_user = active_reference(configured_delta, 100, profile_delta_mv)
    temp_high, temp_high_is_user = active_reference(configured_temp_high, 55, profile_temp_high)
    temp_low, temp_low_is_user = active_reference(configured_temp_low, 0, profile_temp_low)
    uses_configured = any((high_is_user, low_is_user, delta_is_user, temp_high_is_user, temp_low_is_user))

    return {
        "requested_profile": requested,
        "detected_profile": detected,
        "effective_profile": effective,
        "profile_label": label,
        "source": "user_configured" if uses_configured else "profile",
        "note": note,
        "cell_high": cell_high,
        "cell_low": cell_low,
        "pack_high": cell_high * cells if cells else None,
        "pack_low": cell_low * cells if cells else None,
        "delta_mv": delta_mv,
        "temp_high": temp_high,
        "temp_low": temp_low,
        "profile_cell_high": profile_cell_high,
        "profile_cell_low": profile_cell_low,
        "profile_pack_high": profile_cell_high * cells if cells else None,
        "profile_pack_low": profile_cell_low * cells if cells else None,
        "profile_delta_mv": profile_delta_mv,
        "profile_temp_high": profile_temp_high,
        "profile_temp_low": profile_temp_low,
        "cell_count": cells,
        "uses_configured_values": uses_configured,
    }
