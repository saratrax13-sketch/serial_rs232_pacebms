# =============================================================================
# constants.py — Pace BMS Protocol Constants
# Version : 1.0.0
# Changed : 2026-05-16
# Changes :
#   - Initial version with CID2 command codes and warning/protection state maps
# =============================================================================
cid2PackNumber          = b"\x39\x30"       # 0x90
cid2PackAnalogData      = b"\x34\x32"       # 0x42
cid2SoftwareVersion     = b"\x43\x31"       # 0xC1
cid2SerialNumber        = b"\x43\x32"       # 0xC2
cid2PackCapacity        = b"\x41\x36"       # 0xA6
cid2WarnInfo            = b"\x34\x34"       # 0x44


# ─── Warning states ───────────────────────────────────────────────────────────
# Codes 0x00–0x02 are standard. 0x80–0xEF are user-defined (BMS firmware).
# 0xF0 covers other faults. Any code not listed here will be logged as
# Unknown(0xNN) by warn_lookup() in bms_monitor.py — not a crash.
warningStates = {
    b'00': "Normal",
    b'01': "Below lower limit",
    b'02': "Above upper limit",
    b'F0': "Other fault",
    # User-defined range 0x80–0xEF — add entries here if your BMS firmware
    # defines specific codes, e.g.:
    # b'80': "Custom fault A",
}

# ─── Protection state byte 1 (bit flags, LSB first) ──────────────────────────
protectState1 = {
    1: "Above cell volt protect",
    2: "Lower cell volt protect",
    3: "Above total volt protect",
    4: "Lower total volt protect",
    5: "Charge current protect",
    6: "Discharge current protect",
    7: "Short circuit",
    8: "Undefined",
}

# ─── Protection state byte 2 (bit flags, LSB first) ──────────────────────────
protectState2 = {
    1: "Above charge temp protect",
    2: "Above discharge temp protect",
    3: "Lower charge temp protect",
    4: "Lower discharge temp protect",
    5: "Above MOS temp protect",
    6: "Above Env temp protect",
    7: "Lower Env temp protect",
    8: "Fully charged",
}

# ─── Instruction / FET state byte (bit flags, LSB first) ─────────────────────
# Used for documentation — bits are read directly in bms_monitor.py:
#   bit 0: current_limit,  bit 1: charge_fet,   bit 2: discharge_fet
#   bit 3: pack_indicate,  bit 4: reverse,       bit 5: ac_in
#   bit 7: heart
instructionState = {
    1: "Current limit ON",
    2: "Charge FET ON",
    3: "Discharge FET ON",
    4: "Pack indicate ON",
    5: "Reverse indicate ON",
    6: "AC in ON",
    7: "Undefined",
    8: "Heart indicate ON",
}

# ─── Control state byte (bit flags, LSB first) ───────────────────────────────
controlState = {
    1: "Buzzer warn function enabled",
    2: "Undefined",
    3: "Undefined",
    4: "Current limit gear => low gear",
    5: "Current limit function disabled",
    6: "LED warn function disabled",
    7: "Undefined",
    8: "Undefined",
}

# ─── Fault state byte (bit flags, LSB first) ─────────────────────────────────
faultState = {
    1: "Charge MOS fault",
    2: "Discharge MOS fault",
    3: "NTC fault",
    4: "Undefined",
    5: "Cell fault",
    6: "Sample fault",
    7: "Undefined",
    8: "Undefined",
}

# ─── Warning state byte 1 (bit flags, LSB first) ─────────────────────────────
warnState1 = {
    1: "Above cell volt warn",
    2: "Lower cell volt warn",
    3: "Above total volt warn",
    4: "Lower total volt warn",
    5: "Charge current warn",
    6: "Discharge current warn",
    7: "Undefined",
    8: "Undefined",
}

# ─── Warning state byte 2 (bit flags, LSB first) ─────────────────────────────
warnState2 = {
    1: "Above charge temp warn",
    2: "Above discharge temp warn",
    3: "Low charge temp warn",
    4: "Low discharge temp warn",
    5: "High env temp warn",
    6: "Low env temp warn",
    7: "High MOS temp warn",
    8: "Low power warn",
}
