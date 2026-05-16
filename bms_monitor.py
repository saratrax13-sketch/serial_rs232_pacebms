# =============================================================================
# bms_monitor.py — Pace BMS to MQTT Bridge
# Version : 2.2.0
# Changed : 2026-05-16
# Changes :
#   - Full notification engine via bms_notify.py
#   - Direct Telegram for all alerts — no HA automation dependency
#   - SOC low alerts (configurable thresholds)
#   - SOC high alert (configurable, resets on drop)
#   - BMS warning flags (new warnings only, suppresses known noise)
#   - FET off unexpectedly
#   - SOH degradation threshold alert
#   - Disconnect alert after configurable retry count
#   - Recovery notification
#   - Startup/shutdown notifications
#   - Daily 19:00 summary (kWh + worst cell deviation)
#   - Delta report at configurable time (worst spread in window)
#   - All notifications togglable via config
#   - Timestamp added to MQTT error payload to prevent stale retain
# =============================================================================
import paho.mqtt.client as mqtt
import socket
import time
import yaml
import os
import json
import serial
import atexit
import sys
import logging
import constants
import urllib.request
from bms_notify import NotifyState, telegram_send
from dataclasses import dataclass, field
from typing import Optional

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("bmspace")

# ─── Telegram direct notify (used before MQTT is available) ─────────────────

def telegram_notify(config: dict, message: str):
    """Legacy wrapper — delegates to bms_notify.telegram_send."""
    telegram_send(config, message)

# ─── Serial number sanitizer ─────────────────────────────────────────────────
def sanitize_id(s: str) -> str:
    """Strip characters invalid in MQTT topics and HA identifiers."""
    import re
    s = s.replace('\x00', '').strip()          # remove null bytes
    s = re.sub(r'[^A-Za-z0-9_\-]', '', s)      # keep only safe chars
    return s or "unknown"

def clean_version(s: str) -> str:
    """Remove null bytes and extra whitespace from version string."""
    return s.replace('\x00', '').strip()

# ─── Protocol constants  (no more magic numbers) ─────────────────────────────

SOI_BYTE        = 0x7E
MAX_UINT16      = 65535
UINT16_MID      = 32768        # values >= this are negative current
KELVIN_OFFSET   = 2730         # BMS temp encoding: (raw - 2730) / 10 = °C
SOCKET_BUF      = 4096
SOCKET_TIMEOUT  = 3.0          # seconds before recv loop gives up
FRAME_END       = 13           # \r  (0x0D)
DISCOVERY_TTL   = 3600         # republish HA discovery every hour

# ─── Config ───────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if os.path.exists('/data/options.json'):
        log.info("Loading options.json")
        with open('/data/options.json') as f:
            return json.load(f)
    elif os.path.exists('pace-bms-dev\\config.yaml'):
        log.info("Loading config.yaml")
        with open('pace-bms-dev\\config.yaml') as f:
            return yaml.load(f, Loader=yaml.FullLoader)['options']
    sys.exit("No config file found")

# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class PackData:
    pack_number: int
    cells: int
    temps: int
    v_cells: list[int]   = field(default_factory=list)
    t_cells: list[float] = field(default_factory=list)
    i_pack: float        = 0.0
    v_pack: float        = 0.0
    i_remain_cap: int    = 0
    i_full_cap: int      = 0
    i_design_cap: int    = 0
    cycles: int          = 0
    soc: float           = 0.0
    soh: float           = 0.0
    cell_max_diff: int   = 0

@dataclass
class AnalogData:
    packs: int
    pack_data: list[PackData] = field(default_factory=list)

@dataclass
class PackCapacity:
    remain_cap: int
    full_cap: int
    design_cap: int
    soc: float
    soh: float

@dataclass
class WarnData:
    pack_number: int
    warnings: str
    balancing1: str
    balancing2: str
    prot_short_circuit: int
    prot_discharge_current: int
    prot_charge_current: int
    fully: int
    current_limit: int
    charge_fet: int
    discharge_fet: int
    pack_indicate: int
    reverse: int
    ac_in: int
    heart: int

# ─── Checksum helpers ─────────────────────────────────────────────────────────

def chksum_calc(data: bytes) -> Optional[str]:
    try:
        chksum = sum(data[1:]) % (MAX_UINT16 + 1)
        bits    = f'{chksum:016b}'
        flipped = ''.join('1' if b == '0' else '0' for b in bits)
        return format(int(flipped, 2) + 1, 'X')
    except Exception as e:
        log.error("CHKSUM calc error: %s", e)
        return None

def lchksum_calc(lenid: bytes) -> Optional[str]:
    try:
        chksum  = sum(int(chr(b), 16) for b in lenid) % 16
        bits    = f'{chksum:04b}'
        flipped = ''.join('1' if b == '0' else '0' for b in bits)
        result  = int(flipped, 2) + 1
        if result > 15:
            result = 0
        return format(result, 'X')
    except Exception as e:
        log.error("LCHKSUM calc error: %s", e)
        return None

# ─── BMS transport ────────────────────────────────────────────────────────────

def bms_connect(config: dict):
    """Open serial or TCP connection to BMS. Returns (comms, connected)."""
    if config['connection_type'] == "Serial":
        try:
            s = serial.Serial(
                port     = config['bms_serial'],
                baudrate = config.get('bms_baudrate', 9600),
                bytesize = serial.EIGHTBITS,
                parity   = serial.PARITY_NONE,
                stopbits = serial.STOPBITS_ONE,
                timeout  = 1,
            )
            log.info("BMS serial connected on %s", config['bms_serial'])
            return s, True
        except IOError as e:
            log.error("BMS serial error: %s", e)
            return None, False
    else:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((config['bms_ip'], config['bms_port']))
            log.info("BMS TCP connected to %s:%s", config['bms_ip'], config['bms_port'])
            return s, True
        except OSError as e:
            log.error("BMS TCP error: %s", e)
            return None, False

def bms_send(comms, request: bytes, connection_type: str) -> bool:
    if not request:
        return False
    try:
        if connection_type == "Serial":
            comms.write(request)
        else:
            comms.send(request)
        time.sleep(0.25)
        return True
    except Exception as e:
        log.error("BMS send error: %s", e)
        return False

def bms_recv(comms, connection_type: str, debug: int = 0) -> Optional[bytes]:
    """Read one complete frame from BMS. Includes timeout guard on TCP."""
    try:
        if connection_type == "Serial":
            return comms.readline()

        # TCP: accumulate until \r, but give up after SOCKET_TIMEOUT seconds
        temp       = b''
        deadline   = time.time() + SOCKET_TIMEOUT
        while time.time() < deadline:
            chunk = comms.recv(SOCKET_BUF)
            if not chunk:
                break
            temp += chunk
            if temp.endswith(b'\r'):
                break

        if not temp:
            log.error("BMS recv: no data received within %.1fs", SOCKET_TIMEOUT)
            return None

        parts = temp.split(b'\r')
        if len(parts) > 2 and debug > 0:
            log.debug("Multiple EOIs in frame: %s", temp.hex(' '))

        for part in parts:
            if part and part[0] == SOI_BYTE:
                return part + b'\r'

        log.error("BMS recv: no valid SOI found in frame")
        return None

    except Exception as e:
        log.error("BMS recv error: %s", e)
        return None

# ─── Protocol layer ───────────────────────────────────────────────────────────

_RTN_ERRORS = {
    b'01': "RTN Error 01: Undefined RTN error",
    b'02': "RTN Error 02: CHKSUM error",
    b'03': "RTN Error 03: LCHKSUM error",
    b'04': "RTN Error 04: CID2 undefined",
    b'05': "RTN Error 05: Undefined error",
    b'06': "RTN Error 06: Undefined error",
    b'09': "RTN Error 09: Operation or write error",
}

def cid2_rtn(rtn: bytes) -> tuple[bool, Optional[str]]:
    msg = _RTN_ERRORS.get(rtn)
    return (True, msg) if msg else (False, None)

def bms_parse_response(inc_data: bytes, debug: int = 0) -> tuple[bool, any]:
    if not inc_data:
        return False, "Empty response"
    try:
        if inc_data[0] != SOI_BYTE:
            return False, f"Bad SOI: 0x{inc_data[0]:02X}"

        error, msg = cid2_rtn(inc_data[7:9])
        if error:
            return False, msg

        lchksum_byte = inc_data[9]
        lenid_bytes  = inc_data[10:13]
        lenid        = int(lenid_bytes, 16)

        calc_lchksum = lchksum_calc(lenid_bytes)
        if calc_lchksum is None:
            return False, "LCHKSUM calculation failed"
        if lchksum_byte != ord(calc_lchksum):
            return False, f"LCHKSUM mismatch: got {lchksum_byte}, expected {ord(calc_lchksum)}"

        info_data   = inc_data[13:13 + lenid]
        chksum_recv = inc_data[13 + lenid:13 + lenid + 4]
        calc_chksum = chksum_calc(inc_data[:len(inc_data) - 5])

        if calc_chksum is None:
            return False, "CHKSUM calculation failed"
        if chksum_recv.decode("ASCII") != calc_chksum:
            if debug > 0:
                log.debug("CHKSUM mismatch. Raw: %s", inc_data.hex(' '))
            return False, "Checksum error"

        return True, info_data

    except Exception as e:
        return False, f"Parse error: {e}"

def bms_request(
    bms, config: dict,
    ver  = b"\x32\x35",
    adr  = b"\x30\x31",
    cid1 = b"\x34\x36",
    cid2 = b"\x43\x31",
    info = b"",
    lenid_override: Optional[bytes] = None,
) -> tuple[bool, any]:
    connection_type = config['connection_type']
    debug           = config.get('debug_output', 0)

    request = b'\x7e' + ver + adr + cid1 + cid2
    lenid   = lenid_override or bytes(format(len(info), '03X'), "ASCII")
    lchksum = '0' if lenid == b'000' else lchksum_calc(lenid)
    if lchksum is None:
        return False, "LCHKSUM failed"

    request += bytes(lchksum, "ASCII") + lenid + info
    chksum   = chksum_calc(request)
    if chksum is None:
        return False, "CHKSUM failed"

    request += bytes(chksum, "ASCII") + b'\x0d'

    if debug > 2:
        log.debug("-> %s", request)

    if not bms_send(bms, request, connection_type):
        return False, "Send failed"

    inc_data = bms_recv(bms, connection_type, debug)
    if inc_data is None:
        return False, "Receive failed"

    if debug > 2:
        log.debug("<- %s", inc_data)

    return bms_parse_response(inc_data, debug)

# ─── BMS data fetchers ────────────────────────────────────────────────────────

def bms_get_version(bms, config: dict) -> tuple[bool, Optional[str]]:
    success, info = bms_request(bms, config, cid2=constants.cid2SoftwareVersion)
    if not success:
        return False, info
    try:
        version = bytes.fromhex(info.decode("ascii")).decode("ASCII")
        log.info("BMS Version: %s", version)
        return True, version
    except Exception as e:
        return False, f"Version parse error: {e}"

def bms_get_serial(bms, config: dict) -> tuple[bool, Optional[str], Optional[str]]:
    success, info = bms_request(bms, config, cid2=constants.cid2SerialNumber)
    if not success:
        return False, info, None
    try:
        bms_sn  = bytes.fromhex(info[0:30].decode("ascii")).decode("ASCII").replace(" ", "")
        pack_sn = bytes.fromhex(info[40:68].decode("ascii")).decode("ASCII").replace(" ", "")
        log.info("BMS SN: %s | Pack SN: %s", bms_sn, pack_sn)
        return True, bms_sn, pack_sn
    except Exception as e:
        return False, f"Serial parse error: {e}", None

def bms_get_analog_data(bms, config: dict, bat_number: int = 255) -> tuple[bool, any]:
    battery        = bytes(format(bat_number, '02X'), 'ASCII')
    success, inc   = bms_request(bms, config, cid2=constants.cid2PackAnalogData, info=battery)
    if not success:
        return False, inc

    try:
        idx        = 2
        num_packs  = int(inc[idx:idx + 2], 16)
        idx       += 2
        pack_list  = []
        prev_cells = None

        for p in range(1, num_packs + 1):
            cells = int(inc[idx:idx + 2], 16)
            if prev_cells is not None and cells != prev_cells:
                idx  += 2
                cells = int(inc[idx:idx + 2], 16)
                if cells != prev_cells:
                    return False, "Cell count mismatch across packs"
            idx       += 2
            prev_cells = cells

            v_cells = []
            for _ in range(cells):
                v_cells.append(int(inc[idx:idx + 4], 16))
                idx += 4
            cell_max_diff = max(v_cells) - min(v_cells) if v_cells else 0

            num_temps = int(inc[idx:idx + 2], 16)
            idx      += 2
            t_cells   = []
            for _ in range(num_temps):
                t_cells.append(round((int(inc[idx:idx + 4], 16) - KELVIN_OFFSET) / 10, 1))
                idx += 4

            i_pack_raw = int(inc[idx:idx + 4], 16)
            idx       += 4
            if i_pack_raw >= UINT16_MID:
                # Pace BMS current is signed 16-bit, scaled by 0.01A.
                # Example: 0xFFFF = -0.01A, 0xFF9C = -1.00A
                i_pack_raw -= (MAX_UINT16 + 1)
            i_pack = i_pack_raw / 100

            v_pack       = int(inc[idx:idx + 4], 16) / 1000;  idx += 4
            i_remain_cap = int(inc[idx:idx + 4], 16) * 10;    idx += 4
            idx          += 2   # skip define-number P
            i_full_cap   = int(inc[idx:idx + 4], 16) * 10;    idx += 4
            soc          = round(i_remain_cap / i_full_cap * 100, 2) if i_full_cap else 0.0
            cycles       = int(inc[idx:idx + 4], 16);          idx += 4
            i_design_cap = int(inc[idx:idx + 4], 16) * 10;    idx += 4
            soh          = min(round(i_full_cap / i_design_cap * 100, 2), 100.0) if i_design_cap else 0.0

            # Skip INFOFLAG between packs — scan forward until we find the
            # next pack header (matching cell count). The old force_pack_offset
            # config is no longer needed; this loop handles any trailing bytes
            # automatically. Log skipped bytes so misalignment is easy to diagnose.
            if p < num_packs:
                skipped = 0
                while idx < len(inc) and int(inc[idx:idx + 2], 16) != cells:
                    idx     += 2
                    skipped += 2
                if skipped and config.get('debug_output', 0) > 0:
                    log.debug("Pack %d: skipped %d bytes locating next pack header", p, skipped)

            pack_list.append(PackData(
                pack_number=p, cells=cells, temps=num_temps,
                v_cells=v_cells, t_cells=t_cells,
                i_pack=i_pack, v_pack=v_pack,
                i_remain_cap=i_remain_cap, i_full_cap=i_full_cap,
                i_design_cap=i_design_cap, cycles=cycles,
                soc=soc, soh=soh, cell_max_diff=cell_max_diff,
            ))

        return True, AnalogData(packs=num_packs, pack_data=pack_list)

    except Exception as e:
        log.error("Analog data parse error: %s", e)
        return False, f"Analog parse error: {e}"

def bms_get_pack_capacity(bms, config: dict) -> tuple[bool, any]:
    success, inc = bms_request(bms, config, cid2=constants.cid2PackCapacity)
    if not success:
        return False, inc
    try:
        idx    = 0
        remain = int(inc[idx:idx + 4], 16) * 10; idx += 4
        full   = int(inc[idx:idx + 4], 16) * 10; idx += 4
        design = int(inc[idx:idx + 4], 16) * 10; idx += 4
        soc    = round(remain / full   * 100, 2) if full   else 0.0
        soh    = min(round(full   / design * 100, 2), 100.0) if design else 0.0
        return True, PackCapacity(remain, full, design, soc, soh)
    except Exception as e:
        log.error("Pack capacity parse error: %s", e)
        return False, f"Pack capacity parse error: {e}"

def bms_get_warn_info(bms, config: dict, packs: int) -> tuple[bool, any]:
    success, inc = bms_request(bms, config, cid2=constants.cid2WarnInfo, info=b'FF')
    if not success:
        return False, inc

    try:
        idx       = 2   # skip pack count byte (2 chars), read cell count fresh each pack
        warn_list = []

        for p in range(1, packs + 1):
            warnings = ""
            cells_w  = int(inc[idx:idx + 2], 16)
            idx      += 2

            def warn_lookup(code: bytes) -> str:
                return constants.warningStates.get(code, f"Unknown(0x{code.decode('ascii')})")

            for c in range(1, cells_w + 1):
                code = inc[idx:idx + 2]
                if code != b'00':
                    warnings += f"cell {c} {warn_lookup(code)}, "
                idx += 2

            temps_w = int(inc[idx:idx + 2], 16); idx += 2
            for t in range(1, temps_w + 1):
                code = inc[idx:idx + 2]
                if code != b'00':
                    warnings += f"temp {t} {warn_lookup(code)}, "
                idx += 2

            for label in ("charge current", "total voltage", "discharge current"):
                code = inc[idx:idx + 2]
                if code != b'00':
                    warnings += f"{label} {warn_lookup(code)}, "
                idx += 2

            def read_byte() -> int:
                nonlocal idx
                val  = ord(bytes.fromhex(inc[idx:idx + 2].decode('ascii')))
                idx += 2
                return val

            ps1 = read_byte()
            if ps1:
                bits      = " | ".join(constants.protectState1[x + 1] for x in range(8) if ps1 & (1 << x))
                warnings += f"Protection State 1: {bits}, "

            ps2 = read_byte()
            if ps2:
                bits      = " | ".join(constants.protectState2[x + 1] for x in range(8) if ps2 & (1 << x))
                warnings += f"Protection State 2: {bits}, "

            inst = read_byte()

            ctrl = read_byte()
            if ctrl:
                bits      = " | ".join(constants.controlState[x + 1] for x in range(8) if ctrl & (1 << x))
                warnings += f"Control State: {bits}, "

            fault = read_byte()
            if fault:
                bits      = " | ".join(constants.faultState[x + 1] for x in range(8) if fault & (1 << x))
                warnings += f"Fault State: {bits}, "

            bal1 = f'{int(inc[idx:idx + 2], 16):08b}'; idx += 2
            bal2 = f'{int(inc[idx:idx + 2], 16):08b}'; idx += 2

            ws1 = read_byte()
            if ws1:
                bits      = " | ".join(constants.warnState1[x + 1] for x in range(8) if ws1 & (1 << x))
                warnings += f"Warning State 1: {bits}, "

            ws2 = read_byte()
            if ws2:
                bits      = " | ".join(constants.warnState2[x + 1] for x in range(8) if ws2 & (1 << x))
                warnings += f"Warning State 2: {bits}, "

            # Skip INFOFLAG between packs
            if idx < len(inc) and cells_w != int(inc[idx:idx + 2], 16):
                idx += 2

            warn_list.append(WarnData(
                pack_number           = p,
                warnings              = warnings.rstrip(", "),
                balancing1            = bal1,
                balancing2            = bal2,
                prot_short_circuit    = ps1 >> 6 & 1,
                prot_discharge_current= ps1 >> 5 & 1,
                prot_charge_current   = ps1 >> 4 & 1,
                fully                 = ps2 >> 7 & 1,
                current_limit         = inst >> 0 & 1,
                charge_fet            = inst >> 1 & 1,
                discharge_fet         = inst >> 2 & 1,
                pack_indicate         = inst >> 3 & 1,
                reverse               = inst >> 4 & 1,
                ac_in                 = inst >> 5 & 1,
                heart                 = inst >> 7 & 1,
            ))

        return True, warn_list

    except Exception as e:
        log.error("Warn info parse error: %s", e)
        return False, f"Warn info parse error: {e}"

# ─── MQTT publishing with change-detection cache ──────────────────────────────

_publish_cache: dict[str, str] = {}

def mqtt_publish(client, topic: str, value: str, qos: int = 0, retain: bool = False, force: bool = False):
    """Publish only if value changed unless force=True.

    Individual MQTT topic logging is DEBUG only. INFO logging is handled by
    compact summary lines so the add-on does not become slow from thousands
    of INFO log writes.
    """
    value = str(value)
    if not force and _publish_cache.get(topic) == value:
        return

    client.publish(topic, value, qos=qos, retain=retain)
    _publish_cache[topic] = value

    if topic.endswith("/config"):
        log.debug("MQTT discovery ▶ %s", topic)
    else:
        log.debug("MQTT state ▶ %s = %s", topic, value)


def _zpad(config: dict, key: str) -> int:
    """Return the effective zfill width for a pad config key.

    Packs normally stay pack_1, pack_2.
    Cells should be cell_01..cell_16 for Pace P16S systems.
    If zero_pad_number_cells is 0 or missing, default to 2 to avoid
    Home Assistant discovery/state topic mismatches.
    """
    raw = config.get(key, None)

    if key == 'zero_pad_number_cells':
        try:
            return max(2, int(raw or 2))
        except (TypeError, ValueError):
            return 2

    try:
        return max(1, int(raw or 1))
    except (TypeError, ValueError):
        return 1


def _state_retain(config: dict) -> bool:
    """Retain MQTT state topics by default so HA has values after restarts."""
    return bool(config.get('mqtt_retain_state', True))


def mah_to_ah_whole(value_mah: int) -> int:
    """Convert mAh to whole Ah for cleaner dashboard display.

    Example: 207550 mAh -> 208 Ah.
    Python's normal round() uses bankers rounding, so use +0.5 for
    conventional rounding to the nearest whole Ah.
    """
    try:
        return int((float(value_mah) / 1000.0) + 0.5)
    except (TypeError, ValueError):
        return 0


def log_analog_summary(data: AnalogData):
    parts = []
    for pack in data.pack_data:
        parts.append(
            f"pack_{pack.pack_number}: cells={pack.cells}, "
            f"V={pack.v_pack:.3f}V, I={pack.i_pack:.2f}A, SOC={pack.soc:.2f}%"
        )
    log.info("Analog read OK: packs=%d | %s", data.packs, " | ".join(parts))


def log_warn_summary(warn_list: list[WarnData]):
    parts = []
    for w in warn_list:
        warning_text = w.warnings if w.warnings else "no warnings"
        parts.append(
            f"pack_{w.pack_number}: fully={'ON' if w.fully else 'OFF'}, "
            f"charge_fet={'ON' if w.charge_fet else 'OFF'}, "
            f"discharge_fet={'ON' if w.discharge_fet else 'OFF'}, "
            f"warnings={warning_text}"
        )
    log.info("Warn read OK: %s", " | ".join(parts))



def publish_analog_data(client, config: dict, data: AnalogData, force: bool = False):
    base = config['mqtt_base_topic']
    zp   = _zpad(config, 'zero_pad_number_packs')
    zc   = _zpad(config, 'zero_pad_number_cells')

    for pack in data.pack_data:
        p      = str(pack.pack_number).zfill(zp)
        prefix = f"{base}/pack_{p}"

        retain = _state_retain(config)

        for i, v in enumerate(pack.v_cells):
            mqtt_publish(client, f"{prefix}/v_cells/cell_{str(i+1).zfill(zc)}", str(v), retain=retain, force=force)
        for i, t in enumerate(pack.t_cells):
            mqtt_publish(client, f"{prefix}/temps/temp_{i+1}", str(t), retain=retain, force=force)

        mqtt_publish(client, f"{prefix}/cells_max_diff_calc", str(pack.cell_max_diff), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/i_pack",              str(pack.i_pack), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/v_pack",              str(pack.v_pack), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/i_remain_cap",        str(mah_to_ah_whole(pack.i_remain_cap)), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/i_full_cap",          str(mah_to_ah_whole(pack.i_full_cap)), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/i_design_cap",        str(mah_to_ah_whole(pack.i_design_cap)), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/cycles",              str(pack.cycles), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/soc",                 str(pack.soc), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/soh",                 str(min(pack.soh, 100.0)), retain=retain, force=force)

def publish_pack_capacity(client, config: dict, cap: PackCapacity, force: bool = False):
    base = config['mqtt_base_topic']
    retain = _state_retain(config)
    mqtt_publish(client, f"{base}/pack_remain_cap", str(mah_to_ah_whole(cap.remain_cap)), retain=retain, force=force)
    mqtt_publish(client, f"{base}/pack_full_cap",   str(mah_to_ah_whole(cap.full_cap)), retain=retain, force=force)
    mqtt_publish(client, f"{base}/pack_design_cap", str(mah_to_ah_whole(cap.design_cap)), retain=retain, force=force)
    mqtt_publish(client, f"{base}/pack_soc",        str(cap.soc), retain=retain, force=force)
    mqtt_publish(client, f"{base}/pack_soh",        str(min(cap.soh, 100.0)), retain=retain, force=force)

def publish_warn_data(client, config: dict, warn_list: list[WarnData], force: bool = False):
    base = config['mqtt_base_topic']
    zp   = _zpad(config, 'zero_pad_number_packs')

    def onoff(val: int) -> str:
        return "ON" if val else "OFF"   # HA binary_sensor prefers ON/OFF

    for w in warn_list:
        p      = str(w.pack_number).zfill(zp)
        prefix = f"{base}/pack_{p}"
        retain = _state_retain(config)

        mqtt_publish(client, f"{prefix}/warnings",               w.warnings, retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/balancing1",             w.balancing1, retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/balancing2",             w.balancing2, retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/prot_short_circuit",     onoff(w.prot_short_circuit), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/prot_discharge_current", onoff(w.prot_discharge_current), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/prot_charge_current",    onoff(w.prot_charge_current), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/fully",                  onoff(w.fully), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/current_limit",          onoff(w.current_limit), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/charge_fet",             onoff(w.charge_fet), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/discharge_fet",          onoff(w.discharge_fet), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/pack_indicate",          onoff(w.pack_indicate), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/reverse",                onoff(w.reverse), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/ac_in",                  onoff(w.ac_in), retain=retain, force=force)
        mqtt_publish(client, f"{prefix}/heart",                  onoff(w.heart), retain=retain, force=force)

# ─── HA Discovery ─────────────────────────────────────────────────────────────

# Maps unit → (device_class, state_class) for Home Assistant.
# Ah is capacity, not HA energy (Wh/kWh), so it intentionally has no device_class.
_HA_SENSOR_META: dict[str, tuple[Optional[str], str]] = {
    "V":   ("voltage",     "measurement"),
    "mV":  ("voltage",     "measurement"),
    "A":   ("current",     "measurement"),
    "Ah":  (None,          "measurement"),
    "%":   ("battery",     "measurement"),
    "°C":  ("temperature", "measurement"),
}

def publish_ha_discovery(client, config: dict, bms_sn: str, bms_version: str, analog_data: AnalogData):
    bms_sn      = sanitize_id(bms_sn)
    bms_version = clean_version(bms_version)
    if not config.get('mqtt_ha_discovery'):
        log.info("HA Discovery disabled")
        return

    log.info("Publishing HA Discovery topics...")
    base      = config['mqtt_base_topic']
    disc_base = config['mqtt_ha_discovery_topic']
    zp        = _zpad(config, 'zero_pad_number_packs')
    zc        = _zpad(config, 'zero_pad_number_cells')

    device = {
        'manufacturer': "BMS Pace",
        'model':        "AM-x",
        'identifiers':  f"bmspace_{bms_sn}",
        'name':         "Generic Lithium",
        'sw_version':   bms_version,
    }

    def pub_sensor(name: str, unique_id: str, state_topic: str, unit: Optional[str] = None):
        payload = {
            'name':               name,
            'unique_id':          unique_id,
            'state_topic':        state_topic,
            'availability_topic': f"{base}/availability",
            'device':             device,
            'state_class':        'measurement',
        }
        if unit is not None:
            payload['unit_of_measurement'] = unit
            meta = _HA_SENSOR_META.get(unit)
            if meta:
                device_class, state_class = meta
                if device_class:
                    payload['device_class'] = device_class
                payload['state_class'] = state_class
        topic = f"{disc_base}/sensor/BMS-{bms_sn}/{name.replace(' ', '_')}/config"
        mqtt_publish(client, topic, json.dumps(payload), qos=1, retain=True, force=True)

    def pub_binary(name: str, unique_id: str, state_topic: str):
        payload = {
            'name':               name,
            'unique_id':          unique_id,
            'state_topic':        state_topic,
            'availability_topic': f"{base}/availability",
            'device':             device,
            'payload_on':         "ON",
            'payload_off':        "OFF",
        }
        topic = f"{disc_base}/binary_sensor/BMS-{bms_sn}/{name.replace(' ', '_')}/config"
        mqtt_publish(client, topic, json.dumps(payload), qos=1, retain=True, force=True)

    for pack in analog_data.pack_data:
        p      = str(pack.pack_number).zfill(zp)
        prefix = f"{base}/pack_{p}"
        uid_p  = f"bmspace_{bms_sn}_pack_{p}"

        for i in range(pack.cells):
            c = str(i + 1).zfill(zc)
            pub_sensor(f"Pack {p} Cell {c} Voltage", f"{uid_p}_v_cell_{c}", f"{prefix}/v_cells/cell_{c}", "mV")

        for i in range(pack.temps):
            pub_sensor(f"Pack {p} Temperature {i+1}", f"{uid_p}_temp_{i+1}", f"{prefix}/temps/temp_{i+1}", "°C")

        pack_sensors = [
            ("Current",            "i_pack",              "i_pack",              "A"),
            ("Voltage",            "v_pack",              "v_pack",              "V"),
            ("Remaining Capacity", "i_remain_cap",        "i_remain_cap",        "Ah"),
            ("Full Capacity",      "i_full_cap",          "i_full_cap",          "Ah"),
            ("Design Capacity",    "i_design_cap",        "i_design_cap",        "Ah"),
            ("State of Charge",    "soc",                 "soc",                 "%"),
            ("State of Health",    "soh",                 "soh",                 "%"),
            ("Cycles",             "cycles",              "cycles",              None),
            ("Cell Max Volt Diff", "cells_max_diff_calc", "cells_max_diff_calc", "mV"),
        ]
        for label, uid_sfx, topic_sfx, unit in pack_sensors:
            pub_sensor(f"Pack {p} {label}", f"{uid_p}_{uid_sfx}", f"{prefix}/{topic_sfx}", unit)

        text_sensors = [
            ("Warnings",   "warnings"),
            ("Balancing1", "balancing1"),
            ("Balancing2", "balancing2"),
        ]
        for label, sfx in text_sensors:
            pub_sensor(f"Pack {p} {label}", f"{uid_p}_{sfx}", f"{prefix}/{sfx}")

        binary_sensors = [
            ("Protection Short Circuit",    "prot_short_circuit"),
            ("Protection Discharge Current","prot_discharge_current"),
            ("Protection Charge Current",   "prot_charge_current"),
            ("Fully Charged",               "fully"),
            ("Current Limit",               "current_limit"),
            ("Charge FET",                  "charge_fet"),
            ("Discharge FET",               "discharge_fet"),
            ("Pack Indicate",               "pack_indicate"),
            ("Reverse",                     "reverse"),
            ("AC In",                       "ac_in"),
            ("Heart",                       "heart"),
        ]
        for label, sfx in binary_sensors:
            pub_binary(f"Pack {p} {label}", f"{uid_p}_{sfx}", f"{prefix}/{sfx}")

    agg_sensors = [
        ("Pack Remaining Capacity", "pack_i_remain_cap", "pack_remain_cap", "Ah"),
        ("Pack Full Capacity",      "pack_i_full_cap",   "pack_full_cap",   "Ah"),
        ("Pack Design Capacity",    "pack_i_design_cap", "pack_design_cap", "Ah"),
        ("Pack State of Charge",    "pack_soc",          "pack_soc",        "%"),
        ("Pack State of Health",    "pack_soh",          "pack_soh",        "%"),
    ]
    for label, uid_sfx, topic_sfx, unit in agg_sensors:
        pub_sensor(label, f"bmspace_{bms_sn}_{uid_sfx}", f"{base}/{topic_sfx}", unit)

# ─── MQTT setup ───────────────────────────────────────────────────────────────

def setup_mqtt(config: dict, bms_sn: str) -> mqtt.Client:
    # Use unique client ID to avoid collisions
    client_id = f"bmspace-{bms_sn}"
    client    = mqtt.Client(client_id)

    # ⚠ Will MUST be set before connect()
    client.will_set(
        f"{config['mqtt_base_topic']}/availability",
        payload = "offline",
        qos     = 1,
        retain  = True,
    )

    client.on_connect    = lambda c, u, f, rc: log.info("MQTT connected (rc=%s)", rc)
    client.on_disconnect = lambda c, u, rc:    log.warning("MQTT disconnected (rc=%s)", rc)

    client.username_pw_set(config['mqtt_user'], config['mqtt_password'])
    client.connect(config['mqtt_host'], config['mqtt_port'], 60)
    client.loop_start()
    time.sleep(2)
    return client

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    log.info("Starting up...")
    config = load_config()

    # ── Wire debug_output → Python log level ─────────────────────────────────
    # 0 = INFO (default), 1+ = DEBUG (verbose protocol tracing)
    debug_level = config.get('debug_output', 0)
    if debug_level >= 1:
        logging.getLogger().setLevel(logging.DEBUG)
        log.debug("debug_output=%d → log level set to DEBUG", debug_level)
    else:
        logging.getLogger().setLevel(logging.INFO)

    # ── Initial BMS connection (needed for serial number before MQTT setup) ──
    log.info("Connecting to BMS...")
    bms, bms_connected = bms_connect(config)

    success, bms_version = bms_get_version(bms, config)
    bms_version = bms_version if success else "unknown"
    if not success:
        log.warning("Could not retrieve BMS version")
        telegram_notify(config, "WARNING: Could not retrieve BMS version. BMS may be starting up.")

    time.sleep(0.1)

    success, bms_sn, pack_sn = bms_get_serial(bms, config)
    if not success:
        telegram_notify(config, "ERROR: Cannot retrieve BMS serial. Monitor exiting.")
        sys.exit("Cannot retrieve BMS serial — required for HA Discovery. Exiting.")

    # ── MQTT (client ID uses bms_sn; will set before connect) ────────────────
    client = setup_mqtt(config, bms_sn)

    base = config['mqtt_base_topic']
    client.publish(f"{base}/availability", "offline", qos=1, retain=True)
    client.publish(f"{base}/bms_version",  bms_version)
    client.publish(f"{base}/bms_sn",       bms_sn)
    client.publish(f"{base}/pack_sn",      pack_sn)

    # ── Startup notification ──────────────────────────────────────────────────
    startup_payload = json.dumps({
        "status":      "startup",
        "bms_sn":      bms_sn,
        "bms_version": bms_version,
    })
    client.publish(f"{base}/bms_status", startup_payload, qos=1, retain=True)
    log.info("Startup notification published")

    # ── Shutdown notification via atexit ──────────────────────────────────────
    def on_exit():
        log.info("Script exiting — publishing shutdown notification")
        shutdown_payload = json.dumps({"status": "shutdown", "bms_sn": bms_sn})
        client.publish(f"{base}/bms_status", shutdown_payload, qos=1, retain=True)
        time.sleep(0.5)
        client.publish(f"{base}/availability", "offline", qos=1, retain=True)
        notify.on_shutdown(bms_sn)

    atexit.register(on_exit)

    scan_interval      = float(config.get('scan_interval', 30))
    last_discovery     = 0.0   # use time.time() for reliable hourly republish
    last_state_force   = 0.0
    last_warn_force    = 0.0
    state_force_seconds = float(config.get('state_force_republish_seconds', 300))
    warn_force_seconds  = float(config.get('warn_force_republish_seconds', 300))
    analog_data        = None
    first_analog_ready = False  # guard: discovery must not fire before first analog read

    # ── Notification engine ──────────────────────────────────────────────────
    notify = NotifyState(config)
    notify.on_startup(bms_sn, bms_version)

    # ── BMS disconnect tracking ───────────────────────────────────────────────
    bms_retry_count    = 0
    bms_disconnect_time = None
    bms_error_published = False

    while True:
        try:
            # ── Reconnect BMS if needed ───────────────────────────────────────
            if not bms_connected:
                if bms_disconnect_time is None:
                    bms_disconnect_time = time.time()

                bms_retry_count += 1
                offline_secs     = int(time.time() - bms_disconnect_time)
                offline_mins     = offline_secs // 60
                offline_str      = f"{offline_mins}m {offline_secs % 60}s" if offline_mins else f"{offline_secs}s"

                log.warning("BMS disconnected — retry %d, offline %s, retrying in 5s...",
                            bms_retry_count, offline_str)

                client.publish(f"{base}/availability", "offline", qos=1, retain=True)

                # Publish error details to MQTT for HA automation
                error_payload = json.dumps({
                    "status":       "disconnected",
                    "retry_count":  bms_retry_count,
                    "offline_time": offline_str,
                    "offline_secs": offline_secs,
                    "timestamp":    int(time.time()),
                })
                client.publish(f"{base}/bms_error", error_payload, qos=1, retain=True)
                bms_error_published = True

                # Direct Telegram notification
                notify.on_disconnect(bms_retry_count, offline_str)

                time.sleep(5)
                bms, bms_connected = bms_connect(config)
                last_discovery     = 0.0
                first_analog_ready = False
                continue

            # ── Reconnect MQTT if needed ──────────────────────────────────────
            if not client.is_connected():
                log.warning("MQTT disconnected — retrying in 5s...")
                client.loop_stop()
                client.connect(config['mqtt_host'], config['mqtt_port'], 60)
                client.loop_start()
                time.sleep(5)
                last_discovery = 0.0
                continue

            # ── Poll BMS ──────────────────────────────────────────────────────
            success, result = bms_get_analog_data(bms, config)
            if success:
                # ── BMS recovered — clear error state ────────────────────────
                if bms_error_published:
                    offline_secs = int(time.time() - bms_disconnect_time) if bms_disconnect_time else 0
                    offline_mins = offline_secs // 60
                    offline_str  = f"{offline_mins}m {offline_secs % 60}s" if offline_mins else f"{offline_secs}s"
                    recovery_payload = json.dumps({
                        "status":        "recovered",
                        "retry_count":   bms_retry_count,
                        "offline_time":  offline_str,
                        "offline_secs":  offline_secs,
                        "timestamp":     int(time.time()),
                    })
                    client.publish(f"{base}/bms_error", recovery_payload, qos=1, retain=True)
                    notify.on_recovery(bms_retry_count, offline_str)
                    log.info("BMS recovered after %s (%d retries)", offline_str, bms_retry_count)
                    bms_error_published  = False
                    bms_retry_count      = 0
                    bms_disconnect_time  = None

                analog_data        = result
                first_analog_ready = True

                now = time.time()
                force_state = (now - last_state_force) >= state_force_seconds
                publish_analog_data(client, config, analog_data, force=force_state)
                if force_state:
                    last_state_force = now

                # ── Notification engine — per-pack updates ────────────────────
                for pack in analog_data.packs:
                    p = pack.pack_number
                    notify.on_soc_update(p, pack.soc)
                    notify.on_soh_update(p, pack.soh)
                    notify.on_energy_update(p, pack.voltage, pack.current, scan_interval)
                    cells_v = [c / 1000.0 for c in pack.cell_voltages]
                    notify.on_cell_update(p, cells_v)
                    delta_mv = pack.cells_max_diff_calc
                    notify.on_delta_update(p, delta_mv)

                # ── Scheduled reports check ───────────────────────────────────
                notify.check_scheduled(len(analog_data.packs))

                log_analog_summary(analog_data)

                # ── HA Discovery: publish only after first successful analog
                # read so cell/pack counts are known; also guards the startup race
                if first_analog_ready and time.time() - last_discovery > DISCOVERY_TTL:
                    publish_ha_discovery(client, config, bms_sn, bms_version, analog_data)
                    client.publish(f"{base}/availability", "online", qos=1, retain=True)
                    last_discovery = time.time()
            else:
                log.error("Analog data error: %s", result)
                bms_connected = False
            time.sleep(scan_interval / 3)

            success, result = bms_get_pack_capacity(bms, config)
            if success:
                publish_pack_capacity(client, config, result, force=(time.time() - last_state_force) >= state_force_seconds)
            else:
                log.error("Pack capacity error: %s", result)
            time.sleep(scan_interval / 3)

            packs           = analog_data.packs if analog_data else 1
            success, result = bms_get_warn_info(bms, config, packs)
            if success:
                now = time.time()
                force_warn = (now - last_warn_force) >= warn_force_seconds
                publish_warn_data(client, config, result, force=force_warn)
                if force_warn:
                    last_warn_force = now
                # ── Warning and FET notifications ─────────────────────────────
                for pack_warn in result.packs:
                    p = pack_warn.pack_number
                    notify.on_warnings_update(p, pack_warn.warnings)
                    notify.on_fet_update(p,
                        'ON' if pack_warn.charge_fet    else 'OFF',
                        'ON' if pack_warn.discharge_fet else 'OFF')
                log_warn_summary(result)
            else:
                log.error("Warn info error: %s", result)
            time.sleep(scan_interval / 3)

        except Exception as e:
            log.exception("Unhandled error in main loop: %s", e)
            time.sleep(scan_interval)


if __name__ == "__main__":
    main()