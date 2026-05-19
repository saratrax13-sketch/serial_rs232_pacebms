# =============================================================================
# bms_monitor.py — Pace BMS to MQTT Bridge
# Version : 2.6.32
# Changed : 2026-05-17
# Changes :
#   - Hardened P16S / 16-cell multi-pack warning-frame alignment
#   - Fixed false Pack 2 warning/protection/FET states caused by inter-pack trailer bytes
#   - Hardened P16S / 16-cell multi-pack analog parsing
#   - Added analog frame bounds checks and full candidate validation
#   - Prevented isolated analog parse errors from causing false disconnect alerts
#   - Made BMS warning repeat cooldown configurable in the web UI
#   - Added BMS warning deduplication and repeat cooldown
#   - Stable release documentation cleanup
#   - Fixed Restart Add-on route for Home Assistant Ingress
#   - Fixed compact header Restart Add-on button route
#   - Moved Config bottom actions into compact header
#   - Compacted Config tab header and backup controls
#   - Fixed visible Config card Required/Optional badges
#   - Removed Config base polling note and kept card badges
#   - Added Config required/optional badges and reordered cards
#   - Redacted Telegram chat ID in Home Assistant add-on options schema
#   - Fixed Report Schedule field validation
#   - Hardened Config validation regex imports
#   - Fixed Config save validation runtime import
#   - Restored original Config help system and added missing section entries
#   - Cleaned up Config and Diagnostics web UI layout
#   - Added web config field validation
#   - Fixed Config section help popups for new option groups
#   - Completed Config tab help text for all option groups
#   - Added full web Config tab option coverage
#   - Added web UI Warning Intelligence section
#   - Documented serial debug probe and slave serial limitation
#   - Added debug-only serial-number frame probe for slave serial investigation
#   - Fixed MQTT availability staying offline while monitor is running
#   - Publishes availability online after successful startup/read/recovery
#   - Added persistent last-events history for web UI
#   - Logs startup, shutdown, disconnect, recovery, stale and fresh events
#   - Added stale data detection for analog and warning reads
#   - Added retained MQTT stale status topics for web UI
#   - Added optional Telegram stale-data and recovery alerts
#   - Fixed monitor status helper scope for web UI MQTT status topics
#   - Added retained MQTT monitor status topics and last read timestamps
#   - Fixed warning-frame parser alignment for Pace frames with prefix byte + pack count
#   - Corrected false Unknown(0x0D), false FET OFF, and false Undefined fault states
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
import time
import yaml
import os
import json
import re
import serial
import atexit
import signal
import sys
import logging
from logging.handlers import RotatingFileHandler
import constants
from bms_notify import NotifyState, telegram_send
from battery_profiles import effective_warning_references
from bms_live import build_live_snapshot, write_live_snapshot
from bms_history import HistoryWriter, bool_option, int_option
from dataclasses import dataclass, field
from typing import Optional

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("bmspace")
MONITOR_LOG_PATH = "/data/pacebms-monitor.log"


def configure_monitor_file_logging():
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] [monitor] %(message)s")
    root_logger = logging.getLogger()
    if any(getattr(handler, "baseFilename", None) == MONITOR_LOG_PATH for handler in root_logger.handlers):
        return
    try:
        handler = RotatingFileHandler(MONITOR_LOG_PATH, maxBytes=1_000_000, backupCount=3)
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    except Exception:
        pass

# ─── Web UI event history ────────────────────────────────────────────────
EVENT_LOG_PATH = "/data/events.json"
MONITOR_HEALTH_PATH = "/data/monitor_health.json"
WARNING_NOTIFY_STATE_PATH = "/data/warning_notify_state.json"
WARNING_NOTIFY_CLEAR_FLAG_PATH = "/data/clear_warning_notify_state.flag"
MAX_EVENT_LOG_ENTRIES = 50

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


def get_debug_output(config: dict) -> int:
    """Return the supported debug level as an integer from 0 to 3."""
    try:
        value = int(str((config or {}).get('debug_output', 0)).strip())
    except Exception:
        return 0
    return min(3, max(0, value))


def write_monitor_health(config: dict, state: str, detail: str = "", **extra):
    """Write monitor heartbeat for the web UI and Supervisor watchdog health check."""
    try:
        scan_interval = float(config.get('scan_interval', 30) or 30)
    except Exception:
        scan_interval = 30.0

    payload = {
        "updated_at": int(time.time()),
        "state": str(state),
        "detail": str(detail or ""),
        "scan_interval": scan_interval,
        "health_timeout_seconds": int(max(60, scan_interval * 6)),
    }
    payload.update(extra)

    tmp_path = f"{MONITOR_HEALTH_PATH}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp_path, MONITOR_HEALTH_PATH)
    except Exception as exc:
        log.debug("Could not write monitor health heartbeat: %s", exc)

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
    """Open serial connection to BMS. Returns (comms, connected)."""
    connection_mode = str(config.get("bms_connection_mode", config.get("connection_type", ""))).strip().lower()
    legacy_connection_type = str(config.get("connection_type", "")).strip().lower()
    if connection_mode != "serial" or legacy_connection_type != "serial":
        log.error(
            "Unsupported BMS connection mode: bms_connection_mode=%s connection_type=%s",
            config.get("bms_connection_mode"),
            config.get("connection_type"),
        )
        return None, False

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

def bms_send(comms, request: bytes) -> bool:
    if not request:
        return False
    try:
        comms.write(request)
        time.sleep(0.25)
        return True
    except Exception as e:
        log.error("BMS send error: %s", e)
        return False

def bms_recv(comms, debug: int = 0) -> Optional[bytes]:
    """Read one complete frame from the serial BMS connection."""
    try:
        data = comms.readline()
        if not data:
            log.error("BMS serial recv: no data received before timeout")
            return None
        return data

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
    debug = get_debug_output(config)

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

    if not bms_send(bms, request):
        return False, "Send failed"

    inc_data = bms_recv(bms, debug)
    if inc_data is None:
        return False, "Receive failed"

    if debug > 2:
        log.debug("<- %s", inc_data)

    return bms_parse_response(inc_data, debug)

# ─── BMS data fetchers ────────────────────────────────────────────────────────

def decode_serial_debug_info(info: bytes) -> dict:
    """Decode raw C2 serial response info for diagnostic logging.

    This is intentionally read-only and diagnostic-only. It does not change
    normal serial parsing; it only helps determine whether the response contains
    more than one serial-like value.
    """
    result = {
        "info_ascii": "",
        "decoded_ascii": "",
        "serial_candidates": [],
    }

    try:
        info_ascii = info.decode("ascii", errors="replace")
        result["info_ascii"] = info_ascii

        decoded = bytes.fromhex(info_ascii).decode("ASCII", errors="replace")
        decoded_clean = decoded.replace("\x00", " ")
        result["decoded_ascii"] = decoded_clean

        candidates = []
        seen = set()

        for pattern in [
            r"HL\d{8,14}",
            r"[A-Z]{1,4}\d{6,16}",
            r"[A-Z0-9]{8,20}",
        ]:
            for match in re.finditer(pattern, decoded_clean.replace("*", " ")):
                candidate = match.group(0).strip()
                if candidate and candidate not in seen:
                    seen.add(candidate)
                    candidates.append({
                        "candidate": candidate,
                        "start": match.start(),
                        "end": match.end(),
                    })

        result["serial_candidates"] = candidates
        return result
    except Exception as exc:
        result["error"] = str(exc)
        return result


def log_serial_debug_probe(info: bytes, config: dict):
    """Log raw serial response details when debug_output >= 3."""
    debug = get_debug_output(config)
    if debug < 3:
        return

    details = decode_serial_debug_info(info)

    log.debug("Serial probe: raw C2 info ASCII-hex length=%s", len(details.get("info_ascii", "")))
    log.debug("Serial probe: raw C2 info ASCII-hex=%s", details.get("info_ascii", ""))
    log.debug("Serial probe: decoded printable text=%r", details.get("decoded_ascii", ""))

    candidates = details.get("serial_candidates", [])
    if candidates:
        log.debug("Serial probe: %d serial-like candidate(s) found", len(candidates))
        for idx, item in enumerate(candidates, start=1):
            log.debug(
                "Serial probe candidate %d: %s at decoded positions %s-%s",
                idx,
                item.get("candidate"),
                item.get("start"),
                item.get("end"),
            )
    else:
        log.debug("Serial probe: no additional serial-like candidates found in C2 response")

    if details.get("error"):
        log.debug("Serial probe decode error: %s", details.get("error"))


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
        # Debug-only probe for investigating whether slave pack serials are present
        # anywhere inside the C2 serial-number response.
        log_serial_debug_probe(info, config)

        bms_sn  = bytes.fromhex(info[0:30].decode("ascii")).decode("ASCII").replace(" ", "")
        pack_sn = bytes.fromhex(info[40:68].decode("ascii")).decode("ASCII").replace(" ", "")
        log.info("BMS SN: %s | Pack SN: %s", bms_sn, pack_sn)

        debug = get_debug_output(config)
        if debug >= 3:
            details = decode_serial_debug_info(info)
            candidates = [item.get("candidate") for item in details.get("serial_candidates", [])]
            log.debug("Serial probe summary: parsed_bms_sn=%s parsed_pack_sn=%s candidates=%s", bms_sn, pack_sn, candidates)
            if len(set(candidates)) <= 1:
                log.debug("Serial probe conclusion: current C2 response appears to expose one unique serial only")
            else:
                log.debug("Serial probe conclusion: multiple unique serial-like values found; review positions for possible slave serial")

        return True, bms_sn, pack_sn
    except Exception as e:
        return False, f"Serial parse error: {e}", None

def bms_get_analog_data(bms, config: dict, bat_number: int = 255) -> tuple[bool, any]:
    battery        = bytes(format(bat_number, '02X'), 'ASCII')
    success, inc   = bms_request(bms, config, cid2=constants.cid2PackAnalogData, info=battery)
    if not success:
        return False, inc

    try:
        if not inc:
            return False, "Analog parse error: empty analog payload"
        if len(inc) % 2 != 0:
            return False, f"Analog parse error: odd-length analog payload len={len(inc)}"

        def read_hex_at(pos: int, width: int, label: str) -> int:
            part = inc[pos:pos + width]
            if len(part) != width:
                raise ValueError(
                    f"Analog frame ended while reading {label}: "
                    f"idx={pos}, need={width}, got={len(part)}, frame_len={len(inc)}"
                )
            return int(part, 16)

        def is_plausible_pack_count(value: Optional[int]) -> bool:
            return value is not None and 1 <= value <= 16

        def is_plausible_cell_count(value: Optional[int]) -> bool:
            return value is not None and 4 <= value <= 32

        def is_plausible_temp_count(value: Optional[int]) -> bool:
            return value is not None and 0 <= value <= 16

        def peek_hex_at(pos: int, width: int = 2) -> Optional[int]:
            if pos < 0 or pos + width > len(inc):
                return None
            return int(inc[pos:pos + width], 16)

        b0 = peek_hex_at(0)
        b1 = peek_hex_at(2)
        b2 = peek_hex_at(4)

        if b0 == 0 and is_plausible_pack_count(b1) and is_plausible_cell_count(b2):
            idx = 2
            num_packs = read_hex_at(idx, 2, "pack count")
            idx += 2
        elif is_plausible_pack_count(b0) and is_plausible_cell_count(b1):
            idx = 0
            num_packs = read_hex_at(idx, 2, "pack count")
            idx += 2
        else:
            idx = 2
            num_packs = read_hex_at(idx, 2, "pack count")
            idx += 2

        if not is_plausible_pack_count(num_packs):
            return False, f"Analog parse error: unexpected pack count {num_packs}"

        debug = get_debug_output(config)
        if debug > 1:
            log.debug("Analog frame len=%d payload=%s", len(inc), inc)
            log.debug("Analog parser: num_packs=%d first_pack_idx=%d", num_packs, idx)

        def parse_pack_at(start_pos: int, pack_no: int, expected_cells: Optional[int] = None) -> tuple[PackData, int]:
            """Parse one full analog pack candidate and validate alignment."""
            pos = start_pos
            cells = read_hex_at(pos, 2, f"pack {pack_no} cell count")
            pos += 2

            if not is_plausible_cell_count(cells):
                raise ValueError(f"Unexpected analog cell count {cells} at pack {pack_no} candidate idx={start_pos}")
            if expected_cells is not None and cells != expected_cells and not bool(config.get('allow_mixed_pack_cell_counts', False)):
                raise ValueError(
                    f"Unexpected analog cell count {cells} at pack {pack_no} candidate idx={start_pos}, expected={expected_cells}"
                )

            v_cells = []
            for c in range(1, cells + 1):
                mv = read_hex_at(pos, 4, f"pack {pack_no} cell {c} voltage")
                pos += 4
                # Broad parser sanity range only. Alarm thresholds remain configurable elsewhere.
                if mv < 1000 or mv > 5000:
                    raise ValueError(f"Implausible cell voltage {mv}mV at pack {pack_no} cell {c} candidate idx={start_pos}")
                v_cells.append(mv)
            cell_max_diff = max(v_cells) - min(v_cells) if v_cells else 0

            num_temps = read_hex_at(pos, 2, f"pack {pack_no} temperature count")
            pos += 2
            if not is_plausible_temp_count(num_temps):
                raise ValueError(f"Unexpected analog temperature count {num_temps} at pack {pack_no} candidate idx={start_pos}")

            t_cells = []
            for t in range(1, num_temps + 1):
                raw_temp = read_hex_at(pos, 4, f"pack {pack_no} temperature {t}")
                pos += 4
                temp_c = round((raw_temp - KELVIN_OFFSET) / 10, 1)
                if temp_c < -50 or temp_c > 120:
                    raise ValueError(f"Implausible temperature {temp_c}C at pack {pack_no} temp {t} candidate idx={start_pos}")
                t_cells.append(temp_c)

            i_pack_raw = read_hex_at(pos, 4, f"pack {pack_no} current")
            pos += 4
            if i_pack_raw >= UINT16_MID:
                i_pack_raw -= (MAX_UINT16 + 1)
            i_pack = i_pack_raw / 100

            v_pack_raw = read_hex_at(pos, 4, f"pack {pack_no} voltage")
            pos += 4
            v_pack = v_pack_raw / 1000
            if v_pack < 5 or v_pack > 120:
                raise ValueError(f"Implausible pack voltage {v_pack:.3f}V at pack {pack_no} candidate idx={start_pos}")

            cell_sum_mv = sum(v_cells)
            if cell_sum_mv and abs(v_pack_raw - cell_sum_mv) > max(3000, cells * 250):
                raise ValueError(
                    f"Pack voltage/cell-sum mismatch at pack {pack_no} candidate idx={start_pos}: "
                    f"pack={v_pack_raw}mV cells_sum={cell_sum_mv}mV"
                )

            i_remain_cap = read_hex_at(pos, 4, f"pack {pack_no} remaining capacity") * 10
            pos += 4
            define_number = read_hex_at(pos, 2, f"pack {pack_no} define-number")
            pos += 2
            i_full_cap = read_hex_at(pos, 4, f"pack {pack_no} full capacity") * 10
            pos += 4
            cycles = read_hex_at(pos, 4, f"pack {pack_no} cycles")
            pos += 4
            i_design_cap = read_hex_at(pos, 4, f"pack {pack_no} design capacity") * 10
            pos += 4

            if i_full_cap <= 0 or i_design_cap <= 0:
                raise ValueError(f"Invalid capacity values at pack {pack_no} candidate idx={start_pos}")
            if i_full_cap > 1000000 or i_design_cap > 1000000 or i_remain_cap > 1000000:
                raise ValueError(f"Implausible capacity values at pack {pack_no} candidate idx={start_pos}")
            if cycles < 0 or cycles > 50000:
                raise ValueError(f"Implausible cycle count {cycles} at pack {pack_no} candidate idx={start_pos}")

            soc = round(i_remain_cap / i_full_cap * 100, 2) if i_full_cap else 0.0
            soh = min(round(i_full_cap / i_design_cap * 100, 2), 100.0) if i_design_cap else 0.0
            if soc < 0 or soc > 150:
                raise ValueError(f"Implausible SOC {soc}% at pack {pack_no} candidate idx={start_pos}")

            if debug > 1:
                log.debug(
                    "Analog candidate accepted: pack=%d idx=%d next=%d cells=%d temps=%d V=%.3f I=%.2f define=0x%02X SOC=%.2f",
                    pack_no, start_pos, pos, cells, num_temps, v_pack, i_pack, define_number, soc,
                )

            return PackData(
                pack_number=pack_no, cells=cells, temps=num_temps,
                v_cells=v_cells, t_cells=t_cells,
                i_pack=i_pack, v_pack=v_pack,
                i_remain_cap=i_remain_cap, i_full_cap=i_full_cap,
                i_design_cap=i_design_cap, cycles=cycles,
                soc=soc, soh=soh, cell_max_diff=cell_max_diff,
            ), pos

        def find_next_pack(start_pos: int, pack_no: int, expected_cells: Optional[int]) -> tuple[PackData, int, int]:
            """Find and parse the next pack using full candidate validation."""
            if pack_no == 1:
                pack, next_pos = parse_pack_at(start_pos, pack_no, expected_cells)
                return pack, next_pos, 0

            candidates = []
            allow_mixed = bool(config.get('allow_mixed_pack_cell_counts', False))
            max_scan_bytes = int(config.get('analog_interpack_max_scan_bytes', 160) or 160)
            scan_end = min(len(inc) - 2, start_pos + (max_scan_bytes * 2))

            for candidate_pos in range(start_pos, scan_end + 1, 2):
                candidate_cell_count = peek_hex_at(candidate_pos)
                if expected_cells is not None and candidate_cell_count != expected_cells and not allow_mixed:
                    continue
                if not is_plausible_cell_count(candidate_cell_count):
                    continue
                try:
                    pack, next_pos = parse_pack_at(candidate_pos, pack_no, expected_cells)
                    candidates.append((candidate_pos, pack, next_pos))
                except Exception as exc:
                    if debug > 2:
                        log.debug("Analog candidate rejected: pack=%d idx=%d reason=%s", pack_no, candidate_pos, exc)
                    continue

            if not candidates:
                first = peek_hex_at(start_pos)
                raise ValueError(
                    f"Could not align analog pack {pack_no}: first_byte={first}, start_idx={start_pos}, "
                    f"expected_cells={expected_cells}, frame_len={len(inc)}"
                )

            candidate_pos, pack, next_pos = candidates[0]
            skipped = candidate_pos - start_pos
            if skipped and debug > 0:
                log.debug(
                    "Analog parser: skipped %d hex chars (%d byte/s) before pack %d block at idx=%d",
                    skipped, skipped // 2, pack_no, candidate_pos,
                )
            return pack, next_pos, skipped

        pack_list = []
        prev_cells = None

        for p in range(1, num_packs + 1):
            pack, idx, skipped = find_next_pack(idx, p, prev_cells)
            prev_cells = pack.cells
            pack_list.append(pack)

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
    """Read and parse BMS warning/status information.

    Pace warning frames may include a response prefix before the first pack
    block and a small trailer/status block between pack warning blocks. The
    parser validates candidate pack blocks instead of assuming the next byte is
    always the next pack cell count.
    """
    success, inc = bms_request(bms, config, cid2=constants.cid2WarnInfo, info=b'FF')
    if not success:
        return False, inc

    try:
        pairs = [int(inc[i:i + 2], 16) for i in range(0, len(inc), 2)]

        def is_plausible_cell_count(value: int) -> bool:
            return 4 <= value <= 32

        def is_plausible_temp_count(value: int) -> bool:
            return 0 <= value <= 16

        def warn_lookup(code: int) -> str:
            key = f"{code:02X}".encode("ascii")
            return constants.warningStates.get(key, f"Unknown(0x{code:02X})")

        def bit_names(state_map: dict, value: int, ignore_names: set[str] | None = None) -> list[str]:
            ignore_names = ignore_names or set()
            names = []
            for bit in range(8):
                if value & (1 << bit):
                    name = state_map.get(bit + 1, "Undefined")
                    if name not in ignore_names and name != "Undefined":
                        names.append(name)
            return names

        def parse_pack_at(start_idx: int, pack_num: int, expected_cells: Optional[int] = None) -> tuple[WarnData, int, int]:
            """Parse one candidate warning block and return data, next index and cell count."""
            pos = start_idx

            def need(count: int, label: str):
                if pos + count > len(pairs):
                    raise ValueError(f"Warning frame ended while reading {label} at idx={pos}")

            def read_byte_local(label: str) -> int:
                nonlocal pos
                need(1, label)
                val = pairs[pos]
                pos += 1
                return val

            warnings = ""

            cells_w = read_byte_local(f"pack {pack_num} cell count")
            if not is_plausible_cell_count(cells_w):
                raise ValueError(f"Unexpected warning cell count {cells_w} at pack {pack_num}")
            if expected_cells is not None and cells_w != expected_cells:
                raise ValueError(f"Warning cell count {cells_w} at pack {pack_num} does not match expected {expected_cells}")

            need(cells_w, f"pack {pack_num} cell warnings")
            for c in range(1, cells_w + 1):
                code = read_byte_local(f"pack {pack_num} cell {c} warning")
                if code != 0x00:
                    warnings += f"cell {c} {warn_lookup(code)}, "

            temps_w = read_byte_local(f"pack {pack_num} temp count")
            if not is_plausible_temp_count(temps_w):
                raise ValueError(f"Unexpected warning temp count {temps_w} at pack {pack_num}")

            need(temps_w, f"pack {pack_num} temperature warnings")
            for t in range(1, temps_w + 1):
                code = read_byte_local(f"pack {pack_num} temp {t} warning")
                if code != 0x00:
                    warnings += f"temp {t} {warn_lookup(code)}, "

            for label in ("charge current", "total voltage", "discharge current"):
                code = read_byte_local(f"pack {pack_num} {label} warning")
                if code != 0x00:
                    warnings += f"{label} {warn_lookup(code)}, "

            ps1 = read_byte_local(f"pack {pack_num} protection state 1")
            ps1_bits = bit_names(constants.protectState1, ps1)
            if ps1_bits:
                warnings += f"Protection State 1: {' | '.join(ps1_bits)}, "

            ps2 = read_byte_local(f"pack {pack_num} protection state 2")
            ps2_bits = bit_names(constants.protectState2, ps2, ignore_names={"Fully charged"})
            if ps2_bits:
                warnings += f"Protection State 2: {' | '.join(ps2_bits)}, "

            inst = read_byte_local(f"pack {pack_num} instruction/status")

            ctrl = read_byte_local(f"pack {pack_num} control state")
            ctrl_bits = bit_names(
                constants.controlState,
                ctrl,
                ignore_names={"Buzzer warn function enabled"}
            )
            if ctrl_bits:
                warnings += f"Control State: {' | '.join(ctrl_bits)}, "

            fault = read_byte_local(f"pack {pack_num} fault state")
            fault_bits = bit_names(constants.faultState, fault)
            if fault_bits:
                warnings += f"Fault State: {' | '.join(fault_bits)}, "

            bal1 = f'{read_byte_local(f"pack {pack_num} balancing1"):08b}'
            bal2 = f'{read_byte_local(f"pack {pack_num} balancing2"):08b}'

            ws1 = read_byte_local(f"pack {pack_num} warning state 1")
            ws1_bits = bit_names(constants.warnState1, ws1)
            if ws1_bits:
                warnings += f"Warning State 1: {' | '.join(ws1_bits)}, "

            ws2 = read_byte_local(f"pack {pack_num} warning state 2")
            ws2_bits = bit_names(constants.warnState2, ws2)
            if ws2_bits:
                warnings += f"Warning State 2: {' | '.join(ws2_bits)}, "

            return WarnData(
                pack_number            = pack_num,
                warnings               = warnings.rstrip(", "),
                balancing1             = bal1,
                balancing2             = bal2,
                prot_short_circuit     = ps1 >> 6 & 1,
                prot_discharge_current = ps1 >> 5 & 1,
                prot_charge_current    = ps1 >> 4 & 1,
                fully                  = ps2 >> 7 & 1,
                current_limit          = inst >> 0 & 1,
                charge_fet             = inst >> 1 & 1,
                discharge_fet          = inst >> 2 & 1,
                pack_indicate          = inst >> 3 & 1,
                reverse                = inst >> 4 & 1,
                ac_in                  = inst >> 5 & 1,
                heart                  = inst >> 7 & 1,
            ), pos, cells_w

        if (
            len(pairs) >= 3
            and pairs[1] == packs
            and is_plausible_cell_count(pairs[2])
        ):
            idx = 2
        elif (
            len(pairs) >= 2
            and pairs[0] == packs
            and is_plausible_cell_count(pairs[1])
        ):
            idx = 1
        else:
            idx = 0

        debug = get_debug_output(config)
        if debug > 1:
            log.debug("Warn frame byte pairs: %s", " ".join(f"{b:02X}" for b in pairs))
            log.debug("Warn parser start index: %d", idx)

        warn_list = []
        expected_cells = None

        for p in range(1, packs + 1):
            if p == 1:
                pack_warn, next_idx, cells_w = parse_pack_at(idx, p, expected_cells)
            else:
                last_error = None
                found = None
                max_scan_bytes = int(config.get('warn_interpack_scan_bytes', 24) or 24)
                max_scan = max(0, max_scan_bytes)

                for candidate_idx in range(idx, min(len(pairs), idx + max_scan + 1)):
                    try:
                        candidate_pack, candidate_next_idx, candidate_cells = parse_pack_at(candidate_idx, p, expected_cells)
                        found = (candidate_pack, candidate_next_idx, candidate_cells, candidate_idx)
                        break
                    except Exception as exc:
                        last_error = exc
                        continue

                if found is None:
                    raise ValueError(f"Could not align warning block for pack {p} from idx={idx}: {last_error}")

                pack_warn, next_idx, cells_w, candidate_idx = found
                if candidate_idx != idx and debug > 0:
                    skipped = candidate_idx - idx
                    skipped_bytes = " ".join(f"{b:02X}" for b in pairs[idx:candidate_idx])
                    log.debug(
                        "Warn parser: skipped %d inter-pack byte(s) before pack %d block at idx=%d: %s",
                        skipped,
                        p,
                        candidate_idx,
                        skipped_bytes,
                    )

            warn_list.append(pack_warn)
            idx = next_idx
            if expected_cells is None:
                expected_cells = cells_w

        if debug > 1 and idx < len(pairs):
            trailer = " ".join(f"{b:02X}" for b in pairs[idx:])
            log.debug("Warn parser: ignored trailing byte(s) after final pack: %s", trailer)

        return True, warn_list

    except Exception as e:
        log.error("Warn info parse error: %s", e)
        return False, f"Warn info parse error: {e}"


# ─── Warning notification deduplication helpers ───────────────────────────────

def normalize_warning_family(warnings: str) -> str:
    """Normalize BMS warning text into a stable warning family.

    Some Pace warning frames alternate between specific text such as
    "cell 8 Above upper limit" and generic text such as "Above cell voltage".
    Telegram should not spam when those represent the same ongoing condition.
    """
    text = str(warnings or "").strip()
    if not text or text.lower() in {"normal", "none", "no warnings"}:
        return "Normal"

    # Split on comma/newline and remove known non-alarm/noise states.
    ignore = {
        "control state: buzzer warn function enabled",
        "fault state: undefined",
    }
    raw_parts = re.split(r"[,\n|]+", text)
    parts = []
    for part in raw_parts:
        clean = re.sub(r"\s+", " ", part.strip())
        if not clean:
            continue
        if clean.lower() in ignore:
            continue
        parts.append(clean)

    if not parts:
        return "Normal"

    family = set()
    for part in parts:
        low = part.lower()

        # Collapse cell-specific upper limit wording and generic wording into
        # the same family.
        if (
            ("above cell" in low and "volt" in low)
            or ("above upper limit" in low and "cell" in low)
            or ("cell" in low and "volt protect" in low and "above" in low)
        ):
            family.add("High cell voltage")
            continue

        if (
            (("lower cell" in low or "below cell" in low) and "volt" in low)
            or ("below lower limit" in low and "cell" in low)
            or ("cell" in low and "volt protect" in low and ("lower" in low or "below" in low))
        ):
            family.add("Low cell voltage")
            continue

        if "temp" in low and ("high" in low or "above" in low or "upper" in low):
            family.add("High temperature")
            continue

        if "temp" in low and ("low" in low or "below" in low or "lower" in low):
            family.add("Low temperature")
            continue

        if "charge current" in low:
            family.add("Charge current warning")
            continue

        if "discharge current" in low:
            family.add("Discharge current warning")
            continue

        if ("above total" in low and "volt" in low) or ("total voltage" in low and ("above" in low or "upper" in low)):
            family.add("High pack voltage")
            continue

        if ("lower total" in low and "volt" in low) or ("total voltage" in low and ("below" in low or "lower" in low)):
            family.add("Low pack voltage")
            continue

        if "protection state" in low:
            family.add("BMS protection active")
            continue

        if "fault state" in low:
            family.add("BMS fault active")
            continue

        family.add(re.sub(r"\s+", " ", part))

    return " | ".join(sorted(family)) if family else "Normal"


_WARNING_SEVERITY_RANK = {
    "normal": 0,
    "caution": 1,
    "warning": 2,
    "critical": 3,
}


def classify_warning_severity(warnings: str, pack_detail, config: dict) -> tuple[str, list[str]]:
    """Classify a BMS warning for Telegram repeat/noise handling.

    This is notification-side risk classification only. It does not write to or
    configure the BMS.
    """
    text = str(warnings or "")
    low = text.lower()
    if not text.strip() or text.strip().lower() in {"normal", "none", "no warnings"}:
        return "normal", []

    reasons = []
    severity = "caution"

    def raise_to(level: str, reason: str):
        nonlocal severity
        if _WARNING_SEVERITY_RANK[level] > _WARNING_SEVERITY_RANK[severity]:
            severity = level
        if reason and reason not in reasons:
            reasons.append(reason)

    if "protect" in low or "short circuit" in low:
        raise_to("critical", "BMS protection state is active")
    if "fault state" in low and "undefined" not in low:
        raise_to("critical", "BMS fault state is active")
    if "current protect" in low:
        raise_to("critical", "BMS current protection is active")

    try:
        delta_thr = float(config.get('notify_cell_delta_warn_mv', 100))
        temp_high = float(config.get('notify_temp_high_warn_c', 55))
        temp_low = float(config.get('notify_temp_low_warn_c', 0))
    except Exception:
        delta_thr, temp_high, temp_low = 100.0, 55.0, 0.0

    if pack_detail is not None:
        cells_v = [float(v) / 1000.0 for v in (getattr(pack_detail, 'v_cells', []) or []) if v is not None and float(v) > 0]
        temps = [float(t) for t in (getattr(pack_detail, 't_cells', []) or []) if t is not None]
        pack_v = float(getattr(pack_detail, 'v_pack', 0.0) or 0.0)
        cell_count = int(getattr(pack_detail, 'cells', len(cells_v)) or len(cells_v))
        delta_mv = float(getattr(pack_detail, 'cell_max_diff', 0.0) or 0.0)
        refs = effective_warning_references(config, cell_count)
        cell_high = refs["cell_high"]
        cell_low = refs["cell_low"]

        if cells_v:
            highest = max(cells_v)
            lowest = min(cells_v)
            if highest >= cell_high:
                raise_to("critical", f"Highest cell {highest:.3f} V is at/above {cell_high:.2f} V reference")
            elif highest >= cell_high - 0.03 and "above" in low and "cell" in low:
                raise_to("warning", f"Highest cell {highest:.3f} V is near {cell_high:.2f} V reference")

            if lowest <= cell_low:
                raise_to("critical", f"Lowest cell {lowest:.3f} V is at/below {cell_low:.2f} V reference")
            elif lowest <= cell_low + 0.05 and ("lower" in low or "below" in low):
                raise_to("warning", f"Lowest cell {lowest:.3f} V is near {cell_low:.2f} V reference")

        if cell_count:
            pack_high = refs["pack_high"]
            pack_low = refs["pack_low"]
            if pack_v >= pack_high:
                raise_to("critical", f"Pack voltage {pack_v:.3f} V is at/above {pack_high:.2f} V reference")
            elif pack_v >= pack_high - 0.50 and ("above total" in low or "total voltage" in low):
                raise_to("warning", f"Pack voltage {pack_v:.3f} V is near {pack_high:.2f} V reference")
            if pack_v and pack_v <= pack_low:
                raise_to("critical", f"Pack voltage {pack_v:.3f} V is at/below {pack_low:.2f} V reference")

        if delta_mv >= delta_thr:
            raise_to("warning", f"Cell delta {delta_mv:.0f} mV is at/above {delta_thr:.0f} mV reference")

        if temps and ("temp" in low):
            high_temp = max(temps)
            low_temp = min(temps)
            if high_temp >= temp_high:
                raise_to("critical", f"Temperature {high_temp:.1f} C is at/above {temp_high:.0f} C reference")
            if low_temp <= temp_low:
                raise_to("critical", f"Temperature {low_temp:.1f} C is at/below {temp_low:.0f} C reference")

    return severity, reasons


def warning_repeat_seconds_for_severity(config: dict, severity: str) -> float:
    defaults = {
        "caution": 21600,
        "warning": 3600,
        "critical": 900,
    }
    keys = {
        "caution": "notify_warning_repeat_caution_seconds",
        "warning": "notify_warning_repeat_warning_seconds",
        "critical": "notify_warning_repeat_critical_seconds",
    }
    fallback = float(config.get('notify_warning_repeat_seconds', defaults.get(severity, 1800)))
    return max(60, float(config.get(keys.get(severity, ""), fallback)))


WARNING_TELEGRAM_POLICIES = {
    "all_bms_warnings",
    "user_reference_or_critical",
    "user_reference_only",
}


def warning_telegram_policy(config: dict) -> str:
    policy = str(config.get("notify_bms_warning_policy", "user_reference_or_critical") or "").strip()
    return policy if policy in WARNING_TELEGRAM_POLICIES else "user_reference_or_critical"


def _config_bool(config: dict, key: str, default: bool = True) -> bool:
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "off", "no", ""}


def _warning_text_matches(text: str, *needles: str) -> bool:
    low = str(text or "").lower()
    return any(needle in low for needle in needles)


def _pack_warning_measurements(pack_detail, config: dict) -> dict:
    if pack_detail is None:
        return {}

    cells_v = []
    for raw in (getattr(pack_detail, "v_cells", []) or []):
        try:
            value = float(raw)
        except Exception:
            continue
        if value > 0:
            cells_v.append(value / 1000.0)

    temps = []
    for raw in (getattr(pack_detail, "t_cells", []) or []):
        try:
            temps.append(float(raw))
        except Exception:
            continue
    cell_count = int(getattr(pack_detail, "cells", len(cells_v)) or len(cells_v))
    refs = effective_warning_references(config, cell_count)
    return {
        "cells_v": cells_v,
        "temps": temps,
        "cell_count": cell_count,
        "refs": refs,
        "pack_v": float(getattr(pack_detail, "v_pack", 0.0) or 0.0),
        "delta_mv": float(getattr(pack_detail, "cell_max_diff", 0.0) or 0.0),
    }


def warning_reference_alert_matches(config: dict, warnings: str, pack_detail) -> tuple[bool, list[str]]:
    """Return whether measured values cross enabled user Telegram references.

    This is Telegram policy only. It does not clear, hide, or alter BMS warning
    state, and it never writes settings to the BMS.
    """
    data = _pack_warning_measurements(pack_detail, config)
    if not data:
        return False, []

    text = str(warnings or "")
    refs = data["refs"]
    cells_v = data["cells_v"]
    temps = data["temps"]
    pack_v = data["pack_v"]
    delta_mv = data["delta_mv"]
    matches = []

    if cells_v:
        highest = max(cells_v)
        lowest = min(cells_v)
        if (
            _config_bool(config, "notify_alert_cell_high_voltage", True)
            and _warning_text_matches(text, "above cell", "above upper limit")
            and highest >= refs["cell_high"]
        ):
            matches.append(f"high cell {highest:.3f} V >= {refs['cell_high']:.2f} V")
        if (
            _config_bool(config, "notify_alert_cell_low_voltage", True)
            and _warning_text_matches(text, "lower cell", "low cell", "below lower limit")
            and lowest <= refs["cell_low"]
        ):
            matches.append(f"low cell {lowest:.3f} V <= {refs['cell_low']:.2f} V")

    if (
        _config_bool(config, "notify_alert_cell_delta", True)
        and delta_mv >= float(refs["delta_mv"])
    ):
        matches.append(f"cell delta {delta_mv:.0f} mV >= {float(refs['delta_mv']):.0f} mV")

    pack_high = refs.get("pack_high")
    pack_low = refs.get("pack_low")
    if (
        pack_high is not None
        and _config_bool(config, "notify_alert_pack_high_voltage", True)
        and _warning_text_matches(text, "above total", "total voltage above", "pack voltage above")
        and pack_v >= float(pack_high)
    ):
        matches.append(f"pack voltage {pack_v:.3f} V >= {float(pack_high):.2f} V")
    if (
        pack_low is not None
        and _config_bool(config, "notify_alert_pack_low_voltage", True)
        and _warning_text_matches(text, "lower total", "low total", "total voltage below", "pack voltage below")
        and pack_v > 0
        and pack_v <= float(pack_low)
    ):
        matches.append(f"pack voltage {pack_v:.3f} V <= {float(pack_low):.2f} V")

    if temps and _warning_text_matches(text, "temp"):
        high_temp = max(temps)
        low_temp = min(temps)
        if _config_bool(config, "notify_alert_temp_high", True) and high_temp >= float(refs["temp_high"]):
            matches.append(f"temperature {high_temp:.1f} C >= {float(refs['temp_high']):.0f} C")
        if _config_bool(config, "notify_alert_temp_low", True) and low_temp <= float(refs["temp_low"]):
            matches.append(f"temperature {low_temp:.1f} C <= {float(refs['temp_low']):.0f} C")

    return bool(matches), matches


def warning_has_bms_critical_text(warnings: str) -> bool:
    low = str(warnings or "").lower()
    return (
        "protect" in low
        or "short circuit" in low
        or ("fault state" in low and "undefined" not in low)
        or "current protect" in low
    )


def warning_text_has_enabled_reference_alert(config: dict, warnings: str) -> bool:
    """Return True when warning text maps to at least one enabled reference row."""
    text = str(warnings or "")
    checks = []
    if _warning_text_matches(text, "above cell", "above upper limit"):
        checks.append(_config_bool(config, "notify_alert_cell_high_voltage", True))
    if _warning_text_matches(text, "lower cell", "low cell", "below lower limit"):
        checks.append(_config_bool(config, "notify_alert_cell_low_voltage", True))
    if _warning_text_matches(text, "above total", "total voltage above", "pack voltage above"):
        checks.append(_config_bool(config, "notify_alert_pack_high_voltage", True))
    if _warning_text_matches(text, "lower total", "low total", "total voltage below", "pack voltage below"):
        checks.append(_config_bool(config, "notify_alert_pack_low_voltage", True))
    if _warning_text_matches(text, "delta", "diff"):
        checks.append(_config_bool(config, "notify_alert_cell_delta", True))
    if _warning_text_matches(text, "temp"):
        checks.append(
            _config_bool(config, "notify_alert_temp_high", True)
            or _config_bool(config, "notify_alert_temp_low", True)
        )
    return any(checks) if checks else True


def warning_telegram_allowed(config: dict, warnings: str, pack_detail, severity: str) -> tuple[bool, str]:
    """Decide whether an active BMS warning should send Telegram."""
    policy = warning_telegram_policy(config)
    reference_match, match_reasons = warning_reference_alert_matches(config, warnings, pack_detail)

    if policy == "all_bms_warnings":
        if warning_text_has_enabled_reference_alert(config, warnings):
            return True, "all BMS warnings policy"
        return False, "all BMS warnings policy: matching reference alert row is disabled"

    if reference_match:
        return True, "; ".join(match_reasons)

    if policy == "user_reference_or_critical" and str(severity or "").lower() == "critical" and warning_has_bms_critical_text(warnings):
        return True, "BMS critical/protection warning"

    return False, f"policy {policy}: no enabled user reference exceeded"


def load_warning_notify_state() -> dict:
    try:
        if not os.path.exists(WARNING_NOTIFY_STATE_PATH):
            return {}
        with open(WARNING_NOTIFY_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        log.debug("Could not load warning notification state: %s", exc)
        return {}


def save_warning_notify_state(state: dict):
    try:
        tmp_path = f"{WARNING_NOTIFY_STATE_PATH}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_path, WARNING_NOTIFY_STATE_PATH)
    except Exception as exc:
        log.debug("Could not save warning notification state: %s", exc)


def consume_warning_notify_clear_request() -> bool:
    """Clear notification cooldown state when the web UI requests it."""
    if not os.path.exists(WARNING_NOTIFY_CLEAR_FLAG_PATH):
        return False
    try:
        os.remove(WARNING_NOTIFY_CLEAR_FLAG_PATH)
    except Exception:
        pass
    try:
        if os.path.exists(WARNING_NOTIFY_STATE_PATH):
            os.remove(WARNING_NOTIFY_STATE_PATH)
    except Exception as exc:
        log.debug("Could not remove warning notification state: %s", exc)
    return True


def warning_severity_rank(severity: str) -> int:
    return _WARNING_SEVERITY_RANK.get(str(severity or "").lower(), 0)


def call_warning_notify(notify, pack_num: int, warnings: str, pack_detail=None, force: bool = False, severity: str = None, repeat: bool = False):
    """Call NotifyState warning handler with compatibility for older signatures."""
    if force and hasattr(notify, "last_warnings"):
        try:
            notify.last_warnings[pack_num] = "Normal"
        except Exception:
            pass

    try:
        return notify.on_warnings_update(pack_num, warnings, pack_detail, severity=severity, repeat=repeat)
    except TypeError:
        try:
            return notify.on_warnings_update(pack_num, warnings, pack_detail)
        except TypeError:
            return notify.on_warnings_update(pack_num, warnings)



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
        return False

    try:
        if hasattr(client, "is_connected") and not client.is_connected():
            log.debug("MQTT publish skipped while disconnected: %s", topic)
            return False
    except Exception:
        pass

    client.publish(topic, value, qos=qos, retain=retain)
    _publish_cache[topic] = value

    if topic.endswith("/config"):
        log.debug("MQTT discovery ▶ %s", topic)
    else:
        log.debug("MQTT state ▶ %s = %s", topic, value)
    return True


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

class NullMqttClient:
    """No-op MQTT client used when MQTT is disabled."""

    def publish(self, *args, **kwargs):
        return None

    def is_connected(self):
        return False

    def loop_start(self):
        return None

    def loop_stop(self):
        return None

    def loop(self, timeout=1.0):
        return None

    def connect(self, *args, **kwargs):
        return None


def setup_mqtt(config: dict, bms_sn: str) -> mqtt.Client:
    if not bool_option(config, "mqtt_enabled", True):
        log.info("MQTT disabled; serial monitor, web UI, history and Telegram can continue without MQTT.")
        return NullMqttClient()

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
    try:
        client.connect(config['mqtt_host'], config['mqtt_port'], 60)
        client.loop_start()
        time.sleep(2)
    except Exception as exc:
        log.warning("MQTT initial connection failed; monitor will keep running and retry: %s", exc)
    return client


def initialize_bms_identity(config: dict, retry_seconds: float = 5.0, max_attempts: Optional[int] = None):
    """Connect to the BMS and read identity, retrying without exiting.

    Startup must remain alive when the serial cable is unplugged or the BMS is
    still booting. This helper does not publish MQTT and does not write to the
    BMS; it only performs the existing read-only version/serial requests.
    """
    attempts = 0
    last_reason = "Not attempted"

    while max_attempts is None or attempts < max_attempts:
        attempts += 1
        log.info("Connecting to BMS...")
        bms, bms_connected = bms_connect(config)

        if not bms_connected or bms is None:
            last_reason = "Serial connection failed"
            write_monitor_health(config, "disconnected", last_reason, retry_count=attempts)
        else:
            success, bms_version = bms_get_version(bms, config)
            if not success:
                version_error = bms_version
                bms_version = "unknown"
                log.warning("Could not retrieve BMS version: %s", version_error)

            time.sleep(0.1)

            success, bms_sn, pack_sn = bms_get_serial(bms, config)
            if success and bms_sn:
                return bms, bms_version, bms_sn, pack_sn or "unknown"

            last_reason = str(bms_sn or "Cannot retrieve BMS serial")
            log.warning("Cannot retrieve BMS serial; retrying startup identity read: %s", last_reason)
            write_monitor_health(config, "disconnected", last_reason, retry_count=attempts)
            try:
                bms.close()
            except Exception:
                pass

        if max_attempts is None or attempts < max_attempts:
            time.sleep(retry_seconds)

    return None, None, None, None

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    config = load_config()
    configure_monitor_file_logging()
    log.info("Starting up...")
    write_monitor_health(config, "starting", "Monitor process started")

    # ── Wire debug_output → Python log level ─────────────────────────────────
    # 0 = INFO (default), 1+ = DEBUG (verbose protocol tracing)
    debug_level = get_debug_output(config)
    if debug_level >= 1:
        logging.getLogger().setLevel(logging.DEBUG)
        log.debug("debug_output=%d → log level set to DEBUG", debug_level)
    else:
        logging.getLogger().setLevel(logging.INFO)

    # ── Initial BMS connection (needed for serial number before MQTT setup) ──
    bms, bms_version, bms_sn, pack_sn = initialize_bms_identity(config)
    bms_connected = bms is not None


    # ── MQTT (client ID uses bms_sn; will set before connect) ────────────────
    mqtt_enabled = bool_option(config, "mqtt_enabled", True)
    client = setup_mqtt(config, bms_sn)

    base = config['mqtt_base_topic']

    def publish_monitor_status(key: str, value):
        """Publish retained monitor status values for the web UI.

        This is MQTT-only status telemetry. It does not write to the BMS.
        """
        try:
            client.publish(f"{base}/monitor/{key}", str(value), qos=1, retain=True)
        except Exception as e:
            log.debug("Monitor status publish failed for %s: %s", key, e)

    def publish_availability(value: str):
        """Publish retained MQTT availability for Home Assistant and web UI.

        This is MQTT-only status telemetry. It does not write to the BMS.
        """
        try:
            client.publish(f"{base}/availability", value, qos=1, retain=True)
        except Exception as e:
            log.debug("Availability publish failed: %s", e)

    publish_monitor_status("state", "starting")
    publish_monitor_status("started_at", int(time.time()))
    write_monitor_health(config, "starting", "MQTT setup complete" if mqtt_enabled else "MQTT disabled; serial monitor starting")

    def append_event(event_type: str, title: str, detail: str = "", level: str = "info"):
        """Append a small event to /data/events.json for the web UI.

        This is local add-on status history only. It does not write to the BMS.
        """
        try:
            event = {
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "ts": int(time.time()),
                "type": str(event_type),
                "level": str(level),
                "title": str(title),
                "detail": str(detail or ""),
            }

            events = []
            if os.path.exists(EVENT_LOG_PATH):
                with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
                    try:
                        events = json.load(f)
                    except Exception:
                        events = []

            if not isinstance(events, list):
                events = []

            events.insert(0, event)
            events = events[:MAX_EVENT_LOG_ENTRIES]

            with open(EVENT_LOG_PATH, "w", encoding="utf-8") as f:
                json.dump(events, f, indent=2)
        except Exception as e:
            log.debug("Could not append web UI event: %s", e)

    append_event("startup", "Monitor starting", f"SN: {bms_sn}", "info")

    publish_availability("offline")
    client.publish(f"{base}/bms_version",  bms_version, qos=1, retain=True)
    client.publish(f"{base}/bms_sn",       bms_sn, qos=1, retain=True)
    client.publish(f"{base}/pack_sn",      pack_sn, qos=1, retain=True)

    # ── Startup notification ──────────────────────────────────────────────────
    startup_payload = json.dumps({
        "status":      "startup",
        "bms_sn":      bms_sn,
        "bms_version": bms_version,
    })
    client.publish(f"{base}/bms_status", startup_payload, qos=1, retain=True)
    log.info("Startup notification published")
    publish_monitor_status("state", "running")
    publish_availability("online")
    append_event("startup", "Monitor started", f"SN: {bms_sn}", "ok")
    write_monitor_health(config, "running", "Monitor startup complete", bms_sn=bms_sn)

    scan_interval      = float(config.get('scan_interval', 30))

    # ── Notification engine ──────────────────────────────────────────────────
    notify = NotifyState(config)
    notify.on_startup(bms_sn, bms_version)

    # ── Warning notification deduplication ───────────────────────────────────
    warning_notify_state = load_warning_notify_state()  # {pack_num: {"family": str, "active": bool, "last_sent": epoch, "severity": str}}

    history_writer = HistoryWriter(config)
    history_writer.start()
    history_sample_seconds = max(1, int_option(config, "history_sample_seconds", 10))
    history_cell_sample_seconds = max(1, int_option(config, "history_cell_sample_seconds", 30))
    last_history_sample = 0.0
    last_cell_history_sample = 0.0
    latest_capacity = None
    latest_warn_list = []

    # ── Clean shutdown handling ──────────────────────────────────────────────
    shutdown_sent = False

    def clean_shutdown(signum=None, frame=None):
        nonlocal shutdown_sent
        if shutdown_sent:
            return
        shutdown_sent = True
        log.info("Script exiting — publishing shutdown notification")
        try:
            shutdown_payload = json.dumps({"status": "shutdown", "bms_sn": bms_sn, "timestamp": int(time.time())})
            client.publish(f"{base}/bms_status", shutdown_payload, qos=1, retain=True)
            publish_availability("offline")
            publish_monitor_status("state", "stopped")
            write_monitor_health(config, "stopped", "Monitor shutdown requested", bms_sn=bms_sn)
            append_event("shutdown", "Monitor stopped", f"SN: {bms_sn}", "warn")
            client.loop(timeout=1.0)
            notify.on_shutdown(bms_sn)
            history_writer.stop()
            time.sleep(0.5)
        except Exception as e:
            log.warning("Shutdown notification failed: %s", e)
        if signum is not None:
            raise SystemExit(0)

    atexit.register(clean_shutdown)
    signal.signal(signal.SIGTERM, clean_shutdown)
    signal.signal(signal.SIGINT, clean_shutdown)

    last_discovery     = 0.0   # use time.time() for reliable hourly republish
    last_state_force   = 0.0
    last_warn_force    = 0.0
    state_force_seconds = float(config.get('state_force_republish_seconds', 300))
    warn_force_seconds  = float(config.get('warn_force_republish_seconds', 300))
    analog_data        = None
    first_analog_ready = False  # guard: discovery must not fire before first analog read

    # ── BMS disconnect tracking ───────────────────────────────────────────────
    bms_retry_count    = 0
    bms_disconnect_time = None
    bms_error_published = False

    # ── Stale-data tracking ──────────────────────────────────────────────────
    stale_enabled = bool(config.get('notify_stale_data', True))
    stale_recovery_enabled = bool(config.get('notify_stale_recovery', True))
    stale_seconds = max(30, float(config.get('notify_stale_data_seconds', 120)))
    stale_repeat_seconds = max(300, float(config.get('notify_stale_data_repeat_seconds', 1800)))

    now_start = time.time()
    last_analog_success = now_start
    last_warn_success = now_start
    stale_notified = False
    last_stale_notify = 0.0

    publish_monitor_status("stale", "OFF")
    publish_monitor_status("stale_reason", "Fresh")
    publish_monitor_status("stale_threshold_seconds", int(stale_seconds))

    def update_serial_live_snapshot(include_history: bool = False, include_cells: bool = False):
        """Write monitor-owned live snapshot and queue history without polling BMS."""
        nonlocal last_history_sample, last_cell_history_sample
        if analog_data is None:
            return None

        snapshot = build_live_snapshot(
            config,
            analog_data,
            latest_capacity,
            latest_warn_list,
            bms_sn=bms_sn,
            pack_sn=pack_sn,
            bms_version=bms_version,
            monitor_state="disconnected" if bms_error_published else "running",
            availability="offline" if bms_error_published else "online",
            stale="ON" if stale_notified else "OFF",
            stale_reason="Stale" if stale_notified else "Fresh",
            last_analog_success=last_analog_success,
            last_warn_success=last_warn_success,
        )

        try:
            write_live_snapshot(snapshot)
        except Exception as exc:
            log.debug("Could not write live serial snapshot: %s", exc)

        now = time.time()
        should_write_pack = include_history or (now - last_history_sample >= history_sample_seconds)
        should_write_cells = include_cells or (now - last_cell_history_sample >= history_cell_sample_seconds)
        if should_write_pack:
            history_writer.record_snapshot(snapshot, include_cells=should_write_cells)
            last_history_sample = now
            if should_write_cells:
                last_cell_history_sample = now
        return snapshot

    def check_stale_data():
        """Check whether analog or warning data is stale.

        This is a monitor-side safety check only. It publishes MQTT status and
        can send Telegram alerts. It does not write to the BMS.
        """
        nonlocal stale_notified, last_stale_notify

        now = time.time()
        analog_age = int(now - last_analog_success)
        warn_age = int(now - last_warn_success)

        publish_monitor_status("analog_age_seconds", analog_age)
        publish_monitor_status("warn_age_seconds", warn_age)

        stale_reasons = []
        if analog_age > stale_seconds:
            stale_reasons.append(f"analog data age {analog_age}s")
        if warn_age > stale_seconds:
            stale_reasons.append(f"warning data age {warn_age}s")

        if stale_reasons:
            reason = "; ".join(stale_reasons)
            publish_monitor_status("stale", "ON")
            publish_monitor_status("stale_reason", reason)

            # Avoid duplicate alerts while the normal disconnect alert is active.
            if stale_enabled and not bms_error_published:
                should_send = (not stale_notified) or ((now - last_stale_notify) >= stale_repeat_seconds)
                if should_send:
                    stale_notified = True
                    last_stale_notify = now
                    append_event("stale", "BMS data stale", reason, "warn")
                    telegram_send(config,
                        "BMS Data Stale\n"
                        f"Reason: {reason}\n"
                        f"Threshold: {int(stale_seconds)}s\n"
                        f"Last analog read: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_analog_success))}\n"
                        f"Last warning read: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_warn_success))}\n"
                        f"Time: {time.strftime('%H:%M:%S')}")
            update_serial_live_snapshot()
            return

        publish_monitor_status("stale", "OFF")
        publish_monitor_status("stale_reason", "Fresh")

        if stale_notified:
            stale_notified = False
            if stale_recovery_enabled:
                append_event("fresh", "BMS data fresh again", f"Analog age: {analog_age}s; warning age: {warn_age}s", "ok")
                telegram_send(config,
                    "BMS Data Fresh Again\n"
                    f"Analog age: {analog_age}s\n"
                    f"Warning age: {warn_age}s\n"
                    f"Time: {time.strftime('%H:%M:%S')}")
        update_serial_live_snapshot()

    def mark_bms_disconnected(reason: str):
        """Mark the BMS offline based on failed communication, not just serial port state."""
        nonlocal bms_retry_count, bms_disconnect_time, bms_error_published, bms_connected, bms

        if bms_disconnect_time is None:
            bms_disconnect_time = time.time()

        bms_retry_count += 1
        offline_secs = int(time.time() - bms_disconnect_time)
        offline_mins = offline_secs // 60
        offline_str = f"{offline_mins}m {offline_secs % 60}s" if offline_mins else f"{offline_secs}s"

        log.warning("BMS communication failed — retry %d, offline %s, reason: %s",
                    bms_retry_count, offline_str, reason)

        publish_availability("offline")
        publish_monitor_status("state", "disconnected")
        append_event("disconnect", "BMS disconnected", reason, "danger")

        error_payload = json.dumps({
            "status": "disconnected",
            "reason": reason,
            "retry_count": bms_retry_count,
            "offline_time": offline_str,
            "offline_secs": offline_secs,
            "timestamp": int(time.time()),
        })
        client.publish(f"{base}/bms_error", error_payload, qos=1, retain=True)
        bms_error_published = True
        write_monitor_health(
            config,
            "disconnected",
            reason,
            retry_count=bms_retry_count,
            offline_secs=offline_secs,
            bms_sn=bms_sn,
        )

        notify.on_disconnect(bms_retry_count, offline_str)
        update_serial_live_snapshot()

        try:
            if bms:
                bms.close()
        except Exception:
            pass

        bms_connected = False

    while True:
        try:
            # ── Reconnect BMS if needed ───────────────────────────────────────
            if not bms_connected:
                time.sleep(5)
                bms, bms_connected = bms_connect(config)
                last_discovery     = 0.0
                first_analog_ready = False
                continue

            # ── Reconnect MQTT if needed ──────────────────────────────────────
            if mqtt_enabled and not client.is_connected():
                log.warning("MQTT disconnected - retrying while BMS polling continues...")
                try:
                    client.loop_stop()
                except Exception:
                    pass
                try:
                    client.connect(config['mqtt_host'], config['mqtt_port'], 60)
                    client.loop_start()
                    _publish_cache.clear()
                    last_discovery = 0.0
                    log.info("MQTT reconnect attempt started")
                except Exception as exc:
                    log.warning("MQTT reconnect failed; continuing BMS polling: %s", exc)

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
                    publish_monitor_status("state", "running")
                    publish_availability("online")
                    publish_monitor_status("last_recovery_epoch", int(time.time()))
                    append_event("recovery", "BMS reconnected", f"Offline: {offline_str}; retries: {bms_retry_count}", "ok")
                    write_monitor_health(
                        config,
                        "running",
                        "BMS communication recovered",
                        last_analog_success=int(last_analog_success),
                        last_warn_success=int(last_warn_success),
                        bms_sn=bms_sn,
                    )
                    bms_error_published  = False
                    bms_retry_count      = 0
                    bms_disconnect_time  = None

                elif bms_retry_count > 0:
                    # Clear isolated transient read/parse failures after a good analog read.
                    log.info("BMS communication retry counter cleared after successful analog read (%d retries)", bms_retry_count)
                    bms_retry_count      = 0
                    bms_disconnect_time  = None
                    publish_monitor_status("state", "running")

                analog_data        = result
                first_analog_ready = True

                last_analog_success = time.time()
                publish_monitor_status("last_analog_read_epoch", int(last_analog_success))
                publish_monitor_status("last_analog_read", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_analog_success)))
                publish_availability("online")
                write_monitor_health(
                    config,
                    "running",
                    "Analog read OK",
                    last_analog_success=int(last_analog_success),
                    last_warn_success=int(last_warn_success),
                    bms_sn=bms_sn,
                )

                now = time.time()
                force_state = (now - last_state_force) >= state_force_seconds
                publish_analog_data(client, config, analog_data, force=force_state)
                if force_state:
                    last_state_force = now

                # ── Notification engine — per-pack updates ────────────────────
                for pack in analog_data.pack_data:
                    p = pack.pack_number
                    notify.on_soc_update(p, pack.soc)
                    notify.on_soh_update(p, pack.soh)
                    notify.on_energy_update(p, pack.v_pack, pack.i_pack, scan_interval)
                    cells_v = [c / 1000.0 for c in pack.v_cells]
                    notify.on_cell_update(p, cells_v)
                    delta_mv = pack.cell_max_diff
                    notify.on_delta_update(p, delta_mv)

                # ── Scheduled reports check ───────────────────────────────────
                notify.check_scheduled(analog_data.packs)

                log_analog_summary(analog_data)

                # ── HA Discovery: publish only after first successful analog
                # read so cell/pack counts are known; also guards the startup race
                update_serial_live_snapshot(include_history=True)

                if mqtt_enabled and first_analog_ready and time.time() - last_discovery > DISCOVERY_TTL:
                    publish_ha_discovery(client, config, bms_sn, bms_version, analog_data)
                    publish_availability("online")
                    last_discovery = time.time()
            else:
                log.error("Analog data error: %s", result)
                result_text = str(result)
                if result_text.startswith("Analog parse error") or "Unexpected analog" in result_text or "unexpected analog" in result_text:
                    if bms_disconnect_time is None:
                        bms_disconnect_time = time.time()

                    bms_retry_count += 1
                    parse_retry_threshold = max(
                        3,
                        int(config.get(
                            "analog_parse_retry_threshold",
                            config.get("notify_retry_count", 3),
                        ) or 3),
                    )
                    offline_secs = int(time.time() - bms_disconnect_time)

                    log.warning(
                        "Analog parse failed — retry %d/%d without reconnecting serial, offline %ss, reason: %s",
                        bms_retry_count,
                        parse_retry_threshold,
                        offline_secs,
                        result_text,
                    )
                    publish_monitor_status("state", "analog_parse_error")
                    publish_monitor_status("last_analog_error", result_text)
                    publish_monitor_status("analog_parse_retry_count", bms_retry_count)
                    write_monitor_health(
                        config,
                        "analog_parse_error",
                        result_text,
                        retry_count=bms_retry_count,
                        retry_threshold=parse_retry_threshold,
                        offline_secs=offline_secs,
                        bms_sn=bms_sn,
                    )

                    if bms_retry_count >= parse_retry_threshold:
                        mark_bms_disconnected(result_text)
                        time.sleep(5)
                        bms, bms_connected = bms_connect(config)
                        last_discovery     = 0.0
                        first_analog_ready = False

                    time.sleep(max(1.0, scan_interval / 3))
                    continue

                mark_bms_disconnected(result_text)
                time.sleep(5)
                bms, bms_connected = bms_connect(config)
                last_discovery     = 0.0
                first_analog_ready = False
                continue
            time.sleep(scan_interval / 3)

            success, result = bms_get_pack_capacity(bms, config)
            if success:
                latest_capacity = result
                publish_pack_capacity(client, config, result, force=(time.time() - last_state_force) >= state_force_seconds)
                update_serial_live_snapshot()
            else:
                log.error("Pack capacity error: %s", result)
            time.sleep(scan_interval / 3)

            packs           = analog_data.packs if analog_data else 1
            success, result = bms_get_warn_info(bms, config, packs)
            if success:
                latest_warn_list = result
                last_warn_success = time.time()
                publish_monitor_status("last_warn_read_epoch", int(last_warn_success))
                publish_monitor_status("last_warn_read", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_warn_success)))
                write_monitor_health(
                    config,
                    "running",
                    "Warning read OK",
                    last_analog_success=int(last_analog_success),
                    last_warn_success=int(last_warn_success),
                    bms_sn=bms_sn,
                )
                now = time.time()
                force_warn = (now - last_warn_force) >= warn_force_seconds
                publish_warn_data(client, config, result, force=force_warn)
                if force_warn:
                    last_warn_force = now
                # ── Warning and FET notifications ─────────────────────────────
                if consume_warning_notify_clear_request():
                    warning_notify_state = {}
                    save_warning_notify_state(warning_notify_state)
                    if hasattr(notify, "last_warnings"):
                        notify.last_warnings = {}
                    log.info("Warning notification suppression state cleared by web UI request")

                pack_by_number = {pack.pack_number: pack for pack in (analog_data.pack_data if analog_data else [])}
                for pack_warn in result:
                    p = pack_warn.pack_number
                    if hasattr(notify, "on_daily_warning_observed"):
                        notify.on_daily_warning_observed(p, pack_warn.warnings)
                    pack_detail = pack_by_number.get(p)
                    warning_family = normalize_warning_family(pack_warn.warnings)
                    severity, severity_reasons = classify_warning_severity(pack_warn.warnings, pack_detail, config)
                    state_key = str(p)
                    previous_warning_state = warning_notify_state.get(state_key, {
                        "family": "Normal",
                        "active": False,
                        "last_sent": 0.0,
                        "severity": "normal",
                        "telegram_sent_active": False,
                    })

                    warning_now = time.time()
                    if warning_family == "Normal":
                        if previous_warning_state.get("active"):
                            previous_sent = bool(previous_warning_state.get(
                                "telegram_sent_active",
                                float(previous_warning_state.get("last_sent", 0.0) or 0.0) > 0,
                            ))
                            if previous_sent:
                                call_warning_notify(notify, p, "Normal", pack_detail)
                            log.info("BMS warning cleared for Pack %02d (previous family: %s)", p, previous_warning_state.get("family", "Unknown"))
                            history_writer.record_warning_event(None, f"{p:02d}", "normal", "BMS warning cleared", str(previous_warning_state.get("family", "Unknown")))
                        warning_notify_state[state_key] = {
                            "family": "Normal",
                            "active": False,
                            "last_sent": previous_warning_state.get("last_sent", 0.0),
                            "severity": "normal",
                            "telegram_sent_active": False,
                        }
                        save_warning_notify_state(warning_notify_state)
                    else:
                        same_family = (
                            previous_warning_state.get("active")
                            and previous_warning_state.get("family") == warning_family
                        )
                        elapsed = warning_now - float(previous_warning_state.get("last_sent", 0.0) or 0.0)
                        previous_severity = str(previous_warning_state.get("severity", "normal"))
                        previous_sent = bool(previous_warning_state.get(
                            "telegram_sent_active",
                            float(previous_warning_state.get("last_sent", 0.0) or 0.0) > 0,
                        ))
                        escalated = warning_severity_rank(severity) > warning_severity_rank(previous_severity)
                        repeat_seconds = warning_repeat_seconds_for_severity(config, severity)
                        telegram_allowed, telegram_policy_reason = warning_telegram_allowed(config, pack_warn.warnings, pack_detail, severity)

                        if not telegram_allowed:
                            warning_notify_state[state_key] = {
                                "family": warning_family,
                                "active": True,
                                "last_sent": previous_warning_state.get("last_sent", 0.0),
                                "severity": severity,
                                "reasons": severity_reasons,
                                "telegram_sent_active": previous_sent,
                                "telegram_suppressed_reason": telegram_policy_reason,
                            }
                            save_warning_notify_state(warning_notify_state)
                            if (not same_family) or escalated:
                                log.info(
                                    "BMS %s warning Telegram suppressed for Pack %02d by policy: %s (%s)",
                                    severity,
                                    p,
                                    telegram_policy_reason,
                                    warning_family,
                                )
                                history_writer.record_warning_event(None, f"{p:02d}", severity, "BMS warning active - Telegram suppressed", f"{warning_family}; {telegram_policy_reason}")
                            elif get_debug_output(config) >= 2:
                                log.debug(
                                    "BMS %s warning Telegram still suppressed for Pack %02d by policy: %s (%s)",
                                    severity,
                                    p,
                                    telegram_policy_reason,
                                    warning_family,
                                )
                        elif (not same_family) or (not previous_sent) or escalated or elapsed >= repeat_seconds:
                            repeat = previous_sent and same_family and not escalated and elapsed >= repeat_seconds
                            call_warning_notify(
                                notify,
                                p,
                                pack_warn.warnings,
                                pack_detail,
                                force=repeat or escalated,
                                severity=severity,
                                repeat=repeat,
                            )
                            warning_notify_state[state_key] = {
                                "family": warning_family,
                                "active": True,
                                "last_sent": warning_now,
                                "severity": severity,
                                "reasons": severity_reasons,
                                "telegram_sent_active": True,
                                "telegram_policy_reason": telegram_policy_reason,
                            }
                            save_warning_notify_state(warning_notify_state)
                            if repeat:
                                log.info(
                                    "BMS %s warning reminder sent for Pack %02d after %.0fs cooldown: %s",
                                    severity,
                                    p,
                                    elapsed,
                                    warning_family,
                                )
                                history_writer.record_warning_event(None, f"{p:02d}", severity, "BMS warning reminder sent", warning_family)
                            elif escalated:
                                log.info(
                                    "BMS warning escalated for Pack %02d: %s -> %s (%s)",
                                    p,
                                    previous_severity,
                                    severity,
                                    warning_family,
                                )
                                history_writer.record_warning_event(None, f"{p:02d}", severity, "BMS warning escalated", warning_family)
                            else:
                                log.info("BMS %s warning notification sent for Pack %02d: %s", severity, p, warning_family)
                                history_writer.record_warning_event(None, f"{p:02d}", severity, "BMS warning notification sent", warning_family)
                        else:
                            if hasattr(notify, "last_warnings"):
                                try:
                                    notify.last_warnings[p] = pack_warn.warnings
                                except Exception:
                                    pass
                            warning_notify_state[state_key] = {
                                "family": warning_family,
                                "active": True,
                                "last_sent": previous_warning_state.get("last_sent", warning_now),
                                "severity": previous_severity,
                                "reasons": previous_warning_state.get("reasons", severity_reasons),
                                "telegram_sent_active": previous_sent,
                                "telegram_policy_reason": previous_warning_state.get("telegram_policy_reason", telegram_policy_reason),
                            }
                            save_warning_notify_state(warning_notify_state)
                            if get_debug_output(config) >= 2:
                                log.debug(
                                    "BMS %s warning duplicate suppressed for Pack %02d: %s (%.0fs since last send, cooldown %.0fs)",
                                    severity,
                                    p,
                                    warning_family,
                                    elapsed,
                                    repeat_seconds,
                                )

                    notify.on_fet_update(p,
                        'ON' if pack_warn.charge_fet    else 'OFF',
                        'ON' if pack_warn.discharge_fet else 'OFF',
                        bool(pack_warn.fully))
                log_warn_summary(result)
                update_serial_live_snapshot(include_history=True)
            else:
                log.error("Warn info error: %s", result)

            check_stale_data()
            time.sleep(scan_interval / 3)

        except Exception as e:
            log.exception("Unhandled error in main loop: %s", e)
            write_monitor_health(config, "error", str(e), bms_sn=bms_sn)
            try:
                check_stale_data()
            except Exception:
                pass
            time.sleep(scan_interval)


if __name__ == "__main__":
    main()
