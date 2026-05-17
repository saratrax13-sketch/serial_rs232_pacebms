import csv
import io
import json
import os
from pathlib import Path
import time
import zipfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from flask import Flask, Response, jsonify, render_template, request, send_file, redirect

import paho.mqtt.client as mqtt

app = Flask(__name__)

OPTIONS_PATH = "/data/options.json"
EVENT_LOG_PATH = "/data/events.json"
CONFIG_BACKUP_DIR = "/data/config_backups"
MAX_CONFIG_BACKUPS = 10
MAX_EVENT_LOG_ENTRIES = 50
DEPRECATED_OPTION_KEYS = {"bms_ip", "bms_port"}

GROUPS = {
    "Telegram": [
        "notify_enabled",
        "telegram_bot_token",
        "telegram_chat_id",
        "notify_startup",
        "notify_disconnect",
        "notify_stale_data",
        "notify_stale_recovery",
    ],
    "Notifications": [
        "notify_soc_low",
        "notify_soc_high",
        "notify_soc_high_on_startup",
        "notify_soh",
        "notify_soh_on_startup",
        "notify_warnings",
        "notify_fet",
        "notify_daily_summary",
        "notify_delta_report",
        "notify_ignore_charge_fet_off_when_full",
        "notify_alert_discharge_fet_off",
    ],
    "Notification Thresholds": [
        "notify_soc_low_thresholds",
        "notify_soc_high_threshold",
        "notify_soc_high_reset",
        "notify_soh_threshold",
        "notify_retry_count",
        "notify_stale_data_seconds",
        "notify_stale_data_repeat_seconds",
    ],
    "Warning Detail": [
        "notify_warning_detail_enabled",
        "notify_cell_high_warn_voltage",
        "notify_cell_low_warn_voltage",
        "notify_cell_delta_warn_mv",
        "notify_temp_high_warn_c",
        "notify_temp_low_warn_c",
        "notify_include_all_cells_above_threshold",
        "notify_include_all_cells_below_threshold",
        "notify_include_highest_and_lowest_cell",
        "notify_include_pack_voltage",
        "notify_include_soc_soh",
    ],
    "Report Schedules": [
        "notify_daily_summary_time",
        "notify_delta_report_time",
        "notify_delta_window_start",
        "notify_delta_window_end",
    ],
    "MQTT": [
        "mqtt_host",
        "mqtt_port",
        "mqtt_user",
        "mqtt_password",
        "mqtt_base_topic",
        "mqtt_ha_discovery",
        "mqtt_ha_discovery_topic",
        "mqtt_retain_state",
        "state_force_republish_seconds",
        "warn_force_republish_seconds",
    ],
    "BMS Connection": [
        "connection_type",
        "bms_serial",
        "bms_baudrate",
        "scan_interval",
    ],
    "Advanced": [
        "debug_output",
        "zero_pad_number_cells",
        "zero_pad_number_packs",
    ],
}

SENSITIVE_KEYS = {
    "telegram_bot_token",
    "telegram_chat_id",
    "mqtt_password",
}


def load_options():
    if not os.path.exists(OPTIONS_PATH):
        return {}, "No /data/options.json file found yet."
    try:
        with open(OPTIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f), None
    except Exception as exc:
        return {}, f"Could not read /data/options.json: {exc}"


def load_events():
    try:
        if not os.path.exists(EVENT_LOG_PATH):
            return []
        with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
            events = json.load(f)
        if not isinstance(events, list):
            return []
        return events[:MAX_EVENT_LOG_ENTRIES]
    except Exception:
        return []


def save_events(events):
    try:
        if not isinstance(events, list):
            events = []
        events = events[:MAX_EVENT_LOG_ENTRIES]
        with open(EVENT_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2)
        return True
    except Exception:
        return False


def clear_events():
    return save_events([])


def ensure_config_backup_dir():
    os.makedirs(CONFIG_BACKUP_DIR, exist_ok=True)


def list_config_backups():
    try:
        ensure_config_backup_dir()
        items = []
        for path in Path(CONFIG_BACKUP_DIR).glob("options-backup-*.json"):
            try:
                stat = path.stat()
                name = path.name

                reason = "Unknown"
                if name.endswith("-manual.json"):
                    reason = "Manual Backup"
                elif name.endswith("-before-save.json"):
                    reason = "Automatic Backup Before Save"
                elif name.endswith("-before-restore.json"):
                    reason = "Automatic Backup Before Restore"

                items.append({
                    "filename": name,
                    "path": str(path),
                    "size": stat.st_size,
                    "created_ts": int(stat.st_mtime),
                    "created": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "created_short": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "reason": reason,
                })
            except Exception:
                pass

        items.sort(key=lambda item: item["created_ts"], reverse=True)
        return items[:MAX_CONFIG_BACKUPS]
    except Exception:
        return []


def create_config_backup(reason="manual"):
    """Create a local backup of /data/options.json before config changes."""
    try:
        ensure_config_backup_dir()

        if not os.path.exists(OPTIONS_PATH):
            return False, "No options.json found to back up.", ""

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_reason = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in str(reason).lower())
        filename = f"options-backup-{timestamp}-{safe_reason}.json"
        backup_path = os.path.join(CONFIG_BACKUP_DIR, filename)

        with open(OPTIONS_PATH, "r", encoding="utf-8") as src:
            current = json.load(src)

        with open(backup_path, "w", encoding="utf-8") as dst:
            json.dump(current, dst, indent=2)

        rotate_config_backups()
        return True, f"Configuration backup created: {filename}", filename
    except Exception as exc:
        return False, f"Could not create configuration backup: {exc}", ""


def rotate_config_backups():
    try:
        ensure_config_backup_dir()
        backups = []
        for path in Path(CONFIG_BACKUP_DIR).glob("options-backup-*.json"):
            try:
                backups.append((path.stat().st_mtime, path))
            except Exception:
                pass

        backups.sort(reverse=True)
        for _, path in backups[MAX_CONFIG_BACKUPS:]:
            try:
                path.unlink()
            except Exception:
                pass
    except Exception:
        pass


def safe_backup_path(filename):
    """Return a safe backup path inside CONFIG_BACKUP_DIR or None."""
    name = os.path.basename(str(filename or ""))
    if not name.startswith("options-backup-") or not name.endswith(".json"):
        return None

    path = os.path.abspath(os.path.join(CONFIG_BACKUP_DIR, name))
    root = os.path.abspath(CONFIG_BACKUP_DIR)
    if not path.startswith(root + os.sep):
        return None

    if not os.path.exists(path):
        return None

    return path


def load_config_backup(filename):
    path = safe_backup_path(filename)
    if not path:
        return None, "Backup file not found or invalid."

    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return None, "Backup file is not a valid options object."
        return payload, "OK"
    except Exception as exc:
        return None, f"Could not read backup: {exc}"


def config_backup_summary():
    backups = list_config_backups()
    if not backups:
        return {
            "count": 0,
            "keep_count": MAX_CONFIG_BACKUPS,
            "latest": "None",
            "oldest": "None",
            "folder": CONFIG_BACKUP_DIR,
        }

    return {
        "count": len(backups),
        "keep_count": MAX_CONFIG_BACKUPS,
        "latest": backups[0].get("created", "Unknown"),
        "oldest": backups[-1].get("created", "Unknown"),
        "folder": CONFIG_BACKUP_DIR,
    }


def sanitize_compare_value(key, value):
    if key in SENSITIVE_KEYS:
        if value in (None, ""):
            return "Blank / not set"
        return "••••••••"
    return value


def compare_options(current_options, backup_options):
    keys = sorted(set(current_options.keys()) | set(backup_options.keys()))
    changes = []

    for key in keys:
        current_value = current_options.get(key, "<missing>")
        backup_value = backup_options.get(key, "<missing>")

        if current_value != backup_value:
            changes.append({
                "key": key,
                "current": sanitize_compare_value(key, current_value),
                "backup": sanitize_compare_value(key, backup_value),
            })

    return changes


def delete_config_backup(filename):
    path = safe_backup_path(filename)
    if not path:
        return False, "Backup file not found or invalid."

    try:
        os.remove(path)
        return True, f"Deleted backup: {filename}"
    except Exception as exc:
        return False, f"Could not delete backup: {exc}"


def append_event(event_type: str, title: str, detail: str = "", level: str = "info"):
    try:
        event = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ts": int(time.time()),
            "type": str(event_type),
            "level": str(level),
            "title": str(title),
            "detail": str(detail or ""),
        }

        events = load_events()
        events.insert(0, event)
        save_events(events)
    except Exception:
        pass


def safe_value(key, value):
    if key in SENSITIVE_KEYS:
        if value in (None, "", "YOUR_TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_CHAT_ID", "YOUR_MQTT_PASSWORD"):
            return "Not configured"
        return "••••••••"
    if isinstance(value, bool):
        return "Enabled" if value else "Disabled"
    if value is None or value == "":
        return "Not set"
    return str(value)


def status_class(key, value):
    if isinstance(value, bool):
        return "ok" if value else "off"
    if key in SENSITIVE_KEYS:
        return "ok" if value and not str(value).startswith("YOUR_") else "warn"
    return ""


def parse_json_or_raw(raw):
    if not raw:
        return "Not available"
    try:
        return json.loads(raw)
    except Exception:
        return raw


def test_telegram(options):
    if not options.get("notify_enabled", True):
        return False, "Notifications are disabled."

    token = options.get("telegram_bot_token", "")
    chat_id = options.get("telegram_chat_id", "")

    if not token or not chat_id:
        return False, "Telegram bot token or chat ID is not configured."

    message = (
        "Pace BMS Test Message\n"
        "Telegram is working from the Home Assistant add-on web UI.\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": message}).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=8)
        return True, "Telegram test sent successfully."
    except Exception as exc:
        return False, f"Telegram test failed: {exc}"


def test_mqtt(options):
    host = options.get("mqtt_host")
    port = int(options.get("mqtt_port", 1883) or 1883)
    user = options.get("mqtt_user", "")
    password = options.get("mqtt_password", "")

    if not host:
        return False, "MQTT host is not configured."

    client_id = f"pacebms-web-test-{int(time.time() * 1000)}"
    client = mqtt.Client(client_id=client_id)

    if user or password:
        client.username_pw_set(user, password)

    try:
        client.connect(host, port, keepalive=10)
        client.disconnect()
        return True, f"MQTT connection test passed: {host}:{port}"
    except Exception as exc:
        return False, f"MQTT connection test failed: {exc}"


def _to_float(value, default=None):
    try:
        return float(value)
    except Exception:
        return default


def classify_warning_severity(warnings: str, availability: str = "online", stale: str = "OFF"):
    """Return a severity class and label for warning/status display."""
    warning_text = str(warnings or "Normal")
    lower = warning_text.lower()

    if str(availability).lower() == "offline":
        return "offline", "Offline"

    if str(stale).upper() == "ON":
        return "stale", "Stale"

    if warning_text == "Normal" or not warning_text.strip():
        return "healthy", "Normal"

    if "fault state" in lower:
        return "fault", "Fault"

    if "protection state" in lower or "short circuit" in lower:
        return "protection", "Protection"

    if "above cell volt" in lower or "above total volt" in lower:
        return "voltage", "Voltage Warning"

    if "temp" in lower:
        return "temperature", "Temperature Warning"

    if "fet" in lower:
        return "fet", "FET Warning"

    return "warning", "Warning"


def fetch_mqtt_snapshot(options, timeout=0.45):
    """Read retained MQTT values for a live status overview.

    This connects briefly to the configured MQTT broker and subscribes to the
    add-on base topic. It only reads retained/current MQTT states. It does not
    publish anything and it does not communicate with the BMS directly.
    """
    host = options.get("mqtt_host")
    port = int(options.get("mqtt_port", 1883) or 1883)
    user = options.get("mqtt_user", "")
    password = options.get("mqtt_password", "")
    base_topic = options.get("mqtt_base_topic", "pacebms").strip().strip("/")

    result = {
        "ok": False,
        "error": "",
        "base_topic": base_topic,
        "availability": "Unknown",
        "monitor_state": "Unknown",
        "last_analog_read": "Unknown",
        "last_warn_read": "Unknown",
        "stale": "Unknown",
        "stale_reason": "Unknown",
        "analog_age_seconds": "Unknown",
        "warn_age_seconds": "Unknown",
        "bms_status": "Not available",
        "bms_error": "Not available",
        "bms_version": "Unknown",
        "bms_sn": "Unknown",
        "pack_sn": "Unknown",
        "pack_count": 0,
        "total_cells": 0,
        "layout": "Unknown",
        "overall_status": "Unknown",
        "overall_class": "unknown",
        "warning_count": 0,
        "severity_summary": {},
        "cell_high_ref": options.get("notify_cell_high_warn_voltage", 4.20),
        "cell_low_ref": options.get("notify_cell_low_warn_voltage", 3.00),
        "packs": [],
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    if not host:
        result["error"] = "MQTT host is not configured."
        return result

    messages = {}

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(f"{base_topic}/#", qos=0)
        else:
            result["error"] = f"MQTT connection failed with rc={rc}"

    def on_message(client, userdata, msg):
        try:
            messages[msg.topic] = msg.payload.decode("utf-8", errors="replace")
        except Exception:
            messages[msg.topic] = str(msg.payload)

    client_id = f"pacebms-web-status-{int(time.time() * 1000)}"
    client = mqtt.Client(client_id=client_id)
    client.on_connect = on_connect
    client.on_message = on_message

    if user or password:
        client.username_pw_set(user, password)

    try:
        client.connect(host, port, keepalive=10)
        client.loop_start()
        time.sleep(timeout)
        client.loop_stop()
        client.disconnect()
    except Exception as exc:
        result["error"] = f"MQTT read failed: {exc}"
        return result

    result["ok"] = bool(messages)
    result["availability"] = messages.get(f"{base_topic}/availability", "Unknown")
    result["monitor_state"] = messages.get(f"{base_topic}/monitor/state", "Unknown")
    result["last_analog_read"] = messages.get(f"{base_topic}/monitor/last_analog_read", "Unknown")
    result["last_warn_read"] = messages.get(f"{base_topic}/monitor/last_warn_read", "Unknown")
    result["stale"] = messages.get(f"{base_topic}/monitor/stale", "Unknown")
    result["stale_reason"] = messages.get(f"{base_topic}/monitor/stale_reason", "Unknown")
    result["analog_age_seconds"] = messages.get(f"{base_topic}/monitor/analog_age_seconds", "Unknown")
    result["warn_age_seconds"] = messages.get(f"{base_topic}/monitor/warn_age_seconds", "Unknown")

    status_raw = messages.get(f"{base_topic}/bms_status", "")
    error_raw = messages.get(f"{base_topic}/bms_error", "")

    result["bms_status"] = parse_json_or_raw(status_raw)
    result["bms_error"] = parse_json_or_raw(error_raw)

    result["bms_version"] = messages.get(f"{base_topic}/bms_version", "Unknown")
    result["bms_sn"] = messages.get(f"{base_topic}/bms_sn", "Unknown")
    result["pack_sn"] = messages.get(f"{base_topic}/pack_sn", "Unknown")

    if isinstance(result["bms_status"], dict):
        if result["bms_sn"] == "Unknown":
            result["bms_sn"] = result["bms_status"].get("bms_sn", "Unknown")
        if result["bms_version"] == "Unknown":
            result["bms_version"] = result["bms_status"].get("bms_version", "Unknown")

    pack_ids = set()
    prefix = f"{base_topic}/pack_"

    for topic in messages:
        if topic.startswith(prefix):
            remainder = topic[len(prefix):]
            pack_id = remainder.split("/", 1)[0]
            if pack_id.isdigit():
                pack_ids.add(pack_id)

    packs = []
    warning_count = 0
    total_cells = 0
    severity_summary = {}

    for pack_id in sorted(pack_ids, key=lambda x: int(x)):
        pfx = f"{base_topic}/pack_{pack_id}"

        cell_prefix = f"{pfx}/v_cells/cell_"
        cell_numbers = []
        cell_values = []

        for topic, value in messages.items():
            if topic.startswith(cell_prefix):
                try:
                    cell_num = int(topic.rsplit("_", 1)[1])
                    cell_mv = _to_float(value)
                    if cell_mv is not None:
                        cell_numbers.append(cell_num)
                        cell_values.append((cell_num, cell_mv / 1000.0))
                except Exception:
                    pass

        cell_count = max(cell_numbers) if cell_numbers else 0
        total_cells += cell_count

        warnings = messages.get(f"{pfx}/warnings", "Normal") or "Normal"
        has_warning = warnings != "Normal"
        if has_warning:
            warning_count += 1

        severity_class, severity_label = classify_warning_severity(
            warnings,
            result["availability"],
            result["stale"],
        )
        severity_summary[severity_label] = severity_summary.get(severity_label, 0) + 1

        voltage = messages.get(f"{pfx}/v_pack", "Unknown")
        current = messages.get(f"{pfx}/i_pack", "Unknown")
        soc = messages.get(f"{pfx}/soc", "Unknown")
        soh = messages.get(f"{pfx}/soh", "Unknown")
        delta = messages.get(f"{pfx}/cells_max_diff_calc", "Unknown")

        cell_high_ref = _to_float(options.get("notify_cell_high_warn_voltage", 4.20), 4.20)
        cell_low_ref = _to_float(options.get("notify_cell_low_warn_voltage", 3.00), 3.00)

        highest_cell = {"number": "Unknown", "voltage": "Unknown"}
        lowest_cell = {"number": "Unknown", "voltage": "Unknown"}
        highest_cell_v = None
        lowest_cell_v = None

        detailed_cells = []
        if cell_values:
            high_num, highest_cell_v = max(cell_values, key=lambda item: item[1])
            low_num, lowest_cell_v = min(cell_values, key=lambda item: item[1])
            highest_cell = {"number": f"{high_num:02d}", "voltage": f"{highest_cell_v:.3f}"}
            lowest_cell = {"number": f"{low_num:02d}", "voltage": f"{lowest_cell_v:.3f}"}

            for cell_num, cell_v in sorted(cell_values, key=lambda item: item[0]):
                labels = []
                if cell_num == high_num:
                    labels.append("Highest")
                if cell_num == low_num:
                    labels.append("Lowest")
                if cell_v > cell_high_ref:
                    labels.append("Above high reference")
                if cell_v < cell_low_ref:
                    labels.append("Below low reference")

                detailed_cells.append({
                    "number": f"{cell_num:02d}",
                    "voltage": f"{cell_v:.3f}",
                    "labels": labels,
                    "class": "cell-alert" if ("Above high reference" in labels or "Below low reference" in labels) else ("cell-highlow" if labels else "cell-normal"),
                })

        pack_v = _to_float(voltage)
        pack_high_ref = cell_high_ref * cell_count if cell_count else None
        pack_low_ref = cell_low_ref * cell_count if cell_count else None

        high_cell_exceeded = bool(highest_cell_v is not None and highest_cell_v > cell_high_ref)
        low_cell_exceeded = bool(lowest_cell_v is not None and lowest_cell_v < cell_low_ref)
        high_pack_exceeded = bool(pack_v is not None and pack_high_ref is not None and pack_v > pack_high_ref)
        low_pack_exceeded = bool(pack_v is not None and pack_low_ref is not None and pack_v < pack_low_ref)

        reference_checks = []
        if "Above cell volt warn" in warnings:
            if high_cell_exceeded:
                reference_checks.append(f"Cell reference exceeded: highest cell is above {cell_high_ref:.2f} V")
            else:
                reference_checks.append(f"Cell reference not exceeded: no cell is above {cell_high_ref:.2f} V")

        if "Above total volt warn" in warnings:
            if high_pack_exceeded:
                reference_checks.append(f"Pack reference exceeded: pack voltage is above {pack_high_ref:.2f} V")
            elif pack_high_ref is not None:
                reference_checks.append(f"Pack reference not exceeded: pack voltage is not above {pack_high_ref:.2f} V")

        if "Lower cell volt warn" in warnings or "Below lower limit" in warnings:
            if low_cell_exceeded:
                reference_checks.append(f"Low cell reference exceeded: lowest cell is below {cell_low_ref:.2f} V")
            else:
                reference_checks.append(f"Low cell reference not exceeded: no cell is below {cell_low_ref:.2f} V")

        if "Lower total volt warn" in warnings:
            if low_pack_exceeded:
                reference_checks.append(f"Low pack reference exceeded: pack voltage is below {pack_low_ref:.2f} V")
            elif pack_low_ref is not None:
                reference_checks.append(f"Low pack reference not exceeded: pack voltage is not below {pack_low_ref:.2f} V")

        if has_warning and not reference_checks:
            reference_checks.append("BMS warning is active. No matching configured reference check was available.")

        if not has_warning:
            reference_checks.append("No active BMS warning.")

        packs.append({
            "id": pack_id,
            "cell_count": cell_count,
            "soc": soc,
            "soh": soh,
            "voltage": voltage,
            "current": current,
            "delta": delta,
            "warnings": warnings,
            "has_warning": has_warning,
            "severity_class": severity_class,
            "severity_label": severity_label,
            "highest_cell": highest_cell,
            "lowest_cell": lowest_cell,
            "cells": detailed_cells,
            "cell_high_ref": f"{cell_high_ref:.2f}",
            "cell_low_ref": f"{cell_low_ref:.2f}",
            "pack_high_ref": f"{pack_high_ref:.2f}" if pack_high_ref is not None else "Unknown",
            "pack_low_ref": f"{pack_low_ref:.2f}" if pack_low_ref is not None else "Unknown",
            "reference_checks": reference_checks,
            "charge_fet": messages.get(f"{pfx}/charge_fet", "Unknown"),
            "discharge_fet": messages.get(f"{pfx}/discharge_fet", "Unknown"),
            "fully": messages.get(f"{pfx}/fully", "Unknown"),
        })

    result["packs"] = packs
    result["pack_count"] = len(packs)
    result["total_cells"] = total_cells
    result["warning_count"] = warning_count
    result["severity_summary"] = severity_summary

    chart_data = []
    for pack in packs:
        highest_v = _to_float(pack.get("highest_cell", {}).get("voltage"))
        lowest_v = _to_float(pack.get("lowest_cell", {}).get("voltage"))
        chart_data.append({
            "pack": f"Pack {pack.get('id')}",
            "soc": _to_float(pack.get("soc"), 0),
            "soh": _to_float(pack.get("soh"), 0),
            "voltage": _to_float(pack.get("voltage"), 0),
            "delta": _to_float(pack.get("delta"), 0),
            "highest_cell": highest_v if highest_v is not None else 0,
            "lowest_cell": lowest_v if lowest_v is not None else 0,
        })
    result["chart_data"] = chart_data

    if packs:
        cell_layout = ", ".join(f"Pack {p['id']}: {p['cell_count']} cells" for p in packs)
        result["layout"] = f"{len(packs)} pack(s), {total_cells} cells total — {cell_layout}"

    availability = str(result["availability"]).lower()
    monitor_state = str(result["monitor_state"]).lower()
    stale = str(result["stale"]).upper()

    if availability == "offline" or monitor_state in {"disconnected", "stopped"}:
        result["overall_status"] = "Offline"
        result["overall_class"] = "offline"
    elif stale == "ON":
        result["overall_status"] = "Stale"
        result["overall_class"] = "stale"
    elif warning_count > 0:
        result["overall_status"] = "Warning"
        result["overall_class"] = "warning"
    elif result["ok"]:
        result["overall_status"] = "Healthy"
        result["overall_class"] = "healthy"
    else:
        result["overall_status"] = "Unknown"
        result["overall_class"] = "unknown"

    if not messages and not result["error"]:
        result["error"] = "No retained MQTT values were received. Check mqtt_retain_state and MQTT connection."

    return result


def input_type_for_value(key, value):
    if isinstance(value, bool):
        return "checkbox"
    if isinstance(value, int) and not isinstance(value, bool):
        return "number"
    if isinstance(value, float):
        return "number"
    if key in SENSITIVE_KEYS:
        return "password"
    return "text"


def redact_value_for_report(key, value):
    if key in SENSITIVE_KEYS:
        if value in (None, ""):
            return "not configured"
        return "redacted"
    return value


def clean_bms_serial(value):
    text = str(value or "Unknown").strip()
    if not text or text.lower() in {"unknown", "none", "not available"}:
        return "Unknown"

    # Serial values often arrive wrapped in asterisks from the BMS.
    cleaned = text.strip("*").strip()
    return cleaned or text


def clean_bms_version(value, serial=""):
    text = str(value or "Unknown").strip()
    if not text or text.lower() in {"unknown", "none", "not available"}:
        return "Unknown"

    serial_clean = clean_bms_serial(serial)
    # Remove repeated serial text and protocol padding from version string.
    cleaned = text.replace(f"*{serial_clean}*", "")
    cleaned = cleaned.replace(serial_clean, "")
    cleaned = cleaned.replace("*", " ")
    cleaned = " ".join(cleaned.split())
    return cleaned or text


def build_battery_topology(options, live):
    packs = live.get("packs", []) if isinstance(live, dict) else []
    pack_count = int(live.get("pack_count", len(packs)) or 0) if isinstance(live, dict) else len(packs)
    total_cells = int(live.get("total_cells", 0) or 0) if isinstance(live, dict) else 0

    bms_serial = clean_bms_serial(live.get("bms_sn", "Unknown") if isinstance(live, dict) else "Unknown")
    pack_serial = clean_bms_serial(live.get("pack_sn", "Unknown") if isinstance(live, dict) else "Unknown")
    bms_version = clean_bms_version(live.get("bms_version", "Unknown") if isinstance(live, dict) else "Unknown", bms_serial)

    if pack_count <= 0:
        configuration = "No packs detected"
    elif pack_count == 1:
        configuration = "Single Pack"
    else:
        configuration = "Master + Slave"

    rows = []
    for pack in packs:
        try:
            pack_num = int(str(pack.get("id", "0")))
        except Exception:
            pack_num = 0

        if pack_num == 1:
            role = "Master"
            serial_display = pack_serial if pack_serial != "Unknown" else bms_serial
            serial_note = "Reported by BMS" if serial_display != "Unknown" else "Not reported"
        else:
            role = "Slave"
            serial_display = "Not reported separately"
            serial_note = "Current BMS read does not expose a separate serial for this pack"

        warnings = pack.get("warnings", "Normal")
        status = "Normal" if warnings == "Normal" else pack.get("severity_label", "Warning")

        rows.append({
            "role": role,
            "pack": f"Pack {pack.get('id')}",
            "serial": serial_display,
            "serial_note": serial_note,
            "cells": pack.get("cell_count", "Unknown"),
            "soc": pack.get("soc", "Unknown"),
            "soh": pack.get("soh", "Unknown"),
            "voltage": pack.get("voltage", "Unknown"),
            "current": pack.get("current", "Unknown"),
            "delta": pack.get("delta", "Unknown"),
            "status": status,
            "warnings": warnings,
        })

    return {
        "connection_type": options.get("connection_type", "Unknown"),
        "bms_serial": bms_serial,
        "pack_serial": pack_serial,
        "bms_version": bms_version,
        "pack_count": pack_count,
        "total_cells": total_cells,
        "configuration": configuration,
        "master_pack": "Pack 01" if pack_count >= 1 else "None",
        "slave_packs": ", ".join(f"Pack {i:02d}" for i in range(2, pack_count + 1)) if pack_count > 1 else "None",
        "rows": rows,
    }


def build_diagnostics(options, live=None):
    """Build a redacted diagnostics summary for the web UI and support report."""
    backups = list_config_backups() if "list_config_backups" in globals() else []
    backup_summary = config_backup_summary() if "config_backup_summary" in globals() else {
        "count": len(backups),
        "keep_count": 0,
        "latest": "Unknown",
        "oldest": "Unknown",
        "folder": "Unknown",
    }

    if live is None and options:
        live = fetch_mqtt_snapshot(options)

    live = live or {}

    telegram_configured = bool(options.get("telegram_bot_token")) and bool(options.get("telegram_chat_id"))
    mqtt_configured = bool(options.get("mqtt_host"))
    discovery_enabled = bool(options.get("mqtt_ha_discovery", False))

    stale_state = str(live.get("stale", "Unknown")).upper()
    availability = str(live.get("availability", "Unknown")).lower()
    monitor_state = str(live.get("monitor_state", "Unknown")).lower()
    warning_count = int(live.get("warning_count", 0) or 0)

    mqtt_ok = bool(live.get("ok"))
    bms_fresh = stale_state == "OFF" and live.get("last_analog_read", "Unknown") not in ("Unknown", "Not available")
    monitor_ok = availability == "online" and monitor_state == "running"

    health_cards = [
        {
            "title": "MQTT Snapshot",
            "status": "OK" if mqtt_ok else "Check",
            "class": "healthy" if mqtt_ok else "warning",
            "detail": "Live MQTT retained values were received." if mqtt_ok else live.get("error", "No retained MQTT values received."),
        },
        {
            "title": "Monitor",
            "status": "Running" if monitor_ok else "Check",
            "class": "healthy" if monitor_ok else "warning",
            "detail": f"Availability: {live.get('availability', 'Unknown')} | State: {live.get('monitor_state', 'Unknown')}",
        },
        {
            "title": "BMS Reads",
            "status": "Fresh" if bms_fresh else "Stale/Unknown",
            "class": "healthy" if bms_fresh else "warning",
            "detail": f"Analog age: {live.get('analog_age_seconds', 'Unknown')}s | Warning age: {live.get('warn_age_seconds', 'Unknown')}s",
        },
        {
            "title": "Warnings",
            "status": "Active" if warning_count else "Normal",
            "class": "warning" if warning_count else "healthy",
            "detail": f"{warning_count} pack(s) with active BMS warnings.",
        },
        {
            "title": "Telegram",
            "status": "Configured" if telegram_configured and options.get("notify_enabled", True) else "Check",
            "class": "healthy" if telegram_configured and options.get("notify_enabled", True) else "warning",
            "detail": "Notifications are enabled and Telegram values are present." if telegram_configured and options.get("notify_enabled", True) else "Telegram is disabled or token/chat ID is missing.",
        },
        {
            "title": "Home Assistant Discovery",
            "status": "Enabled" if discovery_enabled else "Disabled",
            "class": "healthy" if discovery_enabled else "off",
            "detail": f"Discovery topic: {options.get('mqtt_ha_discovery_topic', 'homeassistant')}",
        },
        {
            "title": "Config Backups",
            "status": f"{backup_summary.get('count', 0)} / {backup_summary.get('keep_count', 0)}",
            "class": "healthy" if backup_summary.get("count", 0) else "warning",
            "detail": f"Latest: {backup_summary.get('latest', 'None')}",
        },
        {
            "title": "Read-Only BMS Safety",
            "status": "Read-only",
            "class": "healthy",
            "detail": "The web UI writes Home Assistant add-on options only. It does not write to the BMS.",
        },
    ]

    config_summary = {
        key: redact_value_for_report(key, options.get(key))
        for group_keys in GROUPS.values()
        for key in group_keys
        if key in options
    }

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "health_cards": health_cards,
        "live": live,
        "backup_summary": backup_summary,
        "config_summary": config_summary,
        "events_count": len(load_events()),
        "latest_events": load_events()[:10],
        "battery_topology": build_battery_topology(options, live),
        "clean_bms_serial": clean_bms_serial(live.get("bms_sn", "Unknown")),
        "clean_bms_version": clean_bms_version(live.get("bms_version", "Unknown"), live.get("bms_sn", "Unknown")),
        "read_only_safety": {
            "bms_writes": False,
            "fet_control": False,
            "threshold_writes": False,
            "config_writes": "Home Assistant add-on options only",
        },
    }


def build_sanitized_config(options):
    """Return a redacted copy of add-on options for support use."""
    sanitized = {}
    for key, value in options.items():
        sanitized[key] = redact_value_for_report(key, value)
    return sanitized


def build_backup_summary_for_support():
    backups = list_config_backups() if "list_config_backups" in globals() else []
    summary = config_backup_summary() if "config_backup_summary" in globals() else {
        "count": len(backups),
        "keep_count": 0,
        "latest": "Unknown",
        "oldest": "Unknown",
        "folder": "Unknown",
    }

    return {
        "summary": summary,
        "backups": [
            {
                "filename": item.get("filename"),
                "created": item.get("created"),
                "reason": item.get("reason"),
                "size": item.get("size"),
            }
            for item in backups
        ],
        "note": "This is a summary only. Full backup files are not included in the support bundle.",
    }


def build_support_readme():
    return """Pace BMS Diagnostic Support Bundle

This ZIP contains redacted troubleshooting information from the Pace BMS Home Assistant add-on.

Included files:
- diagnostics.json: current health/status diagnostics
- events.json: recent monitor and web UI events
- backup-summary.json: summary of available config backups
- sanitized-config.json: add-on options with sensitive values redacted
- readme-support.txt: this file

Redacted values:
- Telegram bot token
- Telegram chat ID
- MQTT password
- Other sensitive fields defined by the add-on

Not included:
- Full backup files
- Real credentials
- Telegram tokens
- MQTT passwords
- BMS write/control tools

Safety:
The support bundle only exports diagnostic information.
It does not change Home Assistant settings.
It does not write to the BMS.
It does not send BMS control commands.
"""


CARD_HELP = {
    "Notification Thresholds": "These settings control SOC/SOH alert thresholds, retry count and stale-data timing. SOC low thresholds must be comma-separated numbers, for example 75,50,25,15. Do not use percentage signs.",
    "Report Schedules": "These settings control the daily summary time, delta report time and the delta report calculation window. Use 24-hour HH:MM format, for example 19:00 or 10:15.",
}

FIELD_HELP = {
    "notify_soc_low_thresholds": "Comma-separated SOC low alert thresholds. Use numbers only, no percent signs. Example: 75,50,25,15. The monitor can alert as SOC crosses each threshold.",
    "notify_soc_high_threshold": "High SOC alert threshold as a percentage number. Example: 98 means alert when SOC is at or above 98%.",
    "notify_soc_high_reset": "Reset point for the high SOC alert. Example: 95 means the high SOC alert can trigger again after SOC falls below 95%.",
    "notify_soh_threshold": "SOH alert threshold as a percentage number. Example: 95 means alert when SOH is below 95%.",
    "notify_retry_count": "Number of retry attempts for supported notifications. Use a whole number such as 0, 1, 2 or 3.",
    "notify_stale_data_seconds": "Seconds without fresh BMS data before stale-data notification logic triggers. Example: 120.",
    "notify_stale_data_repeat_seconds": "Repeat interval in seconds for stale-data notifications while the stale condition remains active. Example: 1800.",
    "notify_ignore_charge_fet_off_when_full": "When enabled, Charge FET OFF can be ignored if the pack is full. This helps avoid unnecessary alerts when the BMS disables charging at full SOC.",
    "notify_alert_discharge_fet_off": "When enabled, send an alert if the Discharge FET is OFF.",
    "notify_daily_summary_time": "Time for the daily summary notification. Use 24-hour HH:MM format. Example: 19:00.",
    "notify_delta_report_time": "Time for the cell delta report notification. Use 24-hour HH:MM format. Example: 10:15.",
    "notify_delta_window_start": "Start of the time window used for the delta report. Use 24-hour HH:MM format. Example: 00:00.",
    "notify_delta_window_end": "End of the time window used for the delta report. Use 24-hour HH:MM format. Example: 10:00.",
}

def build_grouped_config(options):
    grouped = {}
    for group_name, keys in GROUPS.items():
        grouped[group_name] = []
        for key in keys:
            raw_value = options.get(key, "")
            grouped[group_name].append({
                "key": key,
                "raw_value": raw_value,
                "input_type": input_type_for_value(key, raw_value),
                "is_bool": isinstance(raw_value, bool),
                "is_sensitive": key in SENSITIVE_KEYS,
                "value": safe_value(key, raw_value),
                "class": status_class(key, raw_value),
            })
    return grouped


def sanitize_config_value(key, value):
    """Return a safe value for config helper output.

    Sensitive values are replaced with placeholders so screenshots/logs do not
    accidentally expose secrets. This helper does not save config.
    """
    placeholders = {
        "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
        "telegram_chat_id": "YOUR_TELEGRAM_CHAT_ID",
        "mqtt_user": "YOUR_MQTT_USER",
        "mqtt_password": "YOUR_MQTT_PASSWORD",
    }

    if key in placeholders:
        return placeholders[key]

    return value


def yaml_scalar(value):
    """Small YAML scalar formatter for simple add-on option values."""
    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        return str(value)

    if value is None:
        return '""'

    text = str(value)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def generate_config_yaml(options):
    """Generate sanitized YAML from current /data/options.json values.

    This is a copy/download helper only. It does not write to Home Assistant
    and it does not write to the BMS.
    """
    lines = [
        "# Pace BMS add-on configuration helper",
        "# Generated from current add-on options.",
        "# Sensitive values are replaced with placeholders.",
        "# Paste/edit these values in the Home Assistant add-on Configuration tab.",
        "",
    ]

    for group_name, keys in GROUPS.items():
        lines.append(f"# ── {group_name} ─────────────────────────────────────────────")
        for key in keys:
            if key not in options:
                continue
            value = sanitize_config_value(key, options.get(key))
            lines.append(f"{key}: {yaml_scalar(value)}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def parse_form_value(key, raw_value, current_value):
    """Parse web form values back to the expected option type."""
    if isinstance(current_value, bool):
        return raw_value == "on"

    if key in SENSITIVE_KEYS:
        # Blank sensitive fields mean keep the current saved value.
        if raw_value is None or str(raw_value).strip() == "":
            return current_value
        return str(raw_value).strip()

    if isinstance(current_value, int) and not isinstance(current_value, bool):
        try:
            return int(str(raw_value).strip())
        except Exception:
            return current_value

    if isinstance(current_value, float):
        try:
            return float(str(raw_value).strip())
        except Exception:
            return current_value

    return "" if raw_value is None else str(raw_value)


def build_options_from_form(form, current_options):
    """Build a new options dictionary from the Config tab form."""
    new_options = dict(current_options)

    for group_name, keys in GROUPS.items():
        for key in keys:
            if key not in current_options:
                continue

            current_value = current_options.get(key)

            if isinstance(current_value, bool):
                raw_value = "on" if key in form else "off"
            else:
                raw_value = form.get(key)

            new_options[key] = parse_form_value(key, raw_value, current_value)

    for deprecated_key in DEPRECATED_OPTION_KEYS:
        new_options.pop(deprecated_key, None)

    return new_options


def supervisor_request(path, payload=None, method="POST", timeout=10):
    """Call the Home Assistant Supervisor API from inside the add-on."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return False, "SUPERVISOR_TOKEN is not available. Check add-on Supervisor API permissions."

    url = f"http://supervisor{path}"
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return True, body or "OK"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return False, f"HTTP {exc.code}: {body}"
    except Exception as exc:
        return False, str(exc)


def validate_addon_options(options):
    """Basic validation for obvious configuration mistakes before saving."""
    errors = []

    def as_int(key, default=None):
        try:
            return int(options.get(key, default))
        except Exception:
            return default

    def as_float(key, default=None):
        try:
            return float(options.get(key, default))
        except Exception:
            return default

    mqtt_host = str(options.get("mqtt_host", "")).strip()
    if not mqtt_host:
        errors.append("mqtt_host cannot be blank.")

    mqtt_port = as_int("mqtt_port")
    if mqtt_port is None or mqtt_port < 1 or mqtt_port > 65535:
        errors.append("mqtt_port must be between 1 and 65535.")

    connection_type = str(options.get("connection_type", "")).strip().lower()
    if connection_type != "serial":
        errors.append("connection_type must be Serial. IP/TCP fields were removed from this add-on config.")
    elif not str(options.get("bms_serial", "")).strip():
        errors.append("bms_serial cannot be blank when connection_type is Serial.")

    scan_interval = as_float("scan_interval")
    if scan_interval is None or scan_interval < 1:
        errors.append("scan_interval must be at least 1 second.")

    notify_retry_count = as_int("notify_retry_count")
    if notify_retry_count is not None and notify_retry_count < 0:
        errors.append("notify_retry_count cannot be negative.")

    soc_high = as_float("notify_soc_high_threshold")
    soc_high_reset = as_float("notify_soc_high_reset")
    if soc_high is not None and not (0 <= soc_high <= 100):
        errors.append("notify_soc_high_threshold must be between 0 and 100.")
    if soc_high_reset is not None and not (0 <= soc_high_reset <= 100):
        errors.append("notify_soc_high_reset must be between 0 and 100.")
    if soc_high is not None and soc_high_reset is not None and soc_high_reset >= soc_high:
        errors.append("notify_soc_high_reset should be lower than notify_soc_high_threshold.")

    soh_threshold = as_float("notify_soh_threshold")
    if soh_threshold is not None and not (0 <= soh_threshold <= 100):
        errors.append("notify_soh_threshold must be between 0 and 100.")

    cell_high = as_float("notify_cell_high_warn_voltage")
    cell_low = as_float("notify_cell_low_warn_voltage")
    if cell_high is not None and not (3.0 <= cell_high <= 5.0):
        errors.append("notify_cell_high_warn_voltage looks unusual; expected roughly 3.0 to 5.0 V.")
    if cell_low is not None and not (1.5 <= cell_low <= 4.0):
        errors.append("notify_cell_low_warn_voltage looks unusual; expected roughly 1.5 to 4.0 V.")
    if cell_high is not None and cell_low is not None and cell_low >= cell_high:
        errors.append("notify_cell_low_warn_voltage must be lower than notify_cell_high_warn_voltage.")

    stale_seconds = as_int("notify_stale_data_seconds")
    if stale_seconds is not None and stale_seconds < 30:
        errors.append("notify_stale_data_seconds should be at least 30 seconds.")

    stale_repeat = as_int("notify_stale_data_repeat_seconds")
    if stale_repeat is not None and stale_repeat < 60:
        errors.append("notify_stale_data_repeat_seconds should be at least 60 seconds.")

    state_force = as_int("state_force_republish_seconds")
    warn_force = as_int("warn_force_republish_seconds")
    if state_force is not None and state_force < 0:
        errors.append("state_force_republish_seconds cannot be negative.")
    if warn_force is not None and warn_force < 0:
        errors.append("warn_force_republish_seconds cannot be negative.")

    return errors


def save_addon_options(new_options):
    """Save add-on options through the Supervisor self endpoint.

    This saves Home Assistant add-on options only. It does not write to the BMS.
    """
    payload = {"options": new_options}

    # Supervisor versions commonly support POST here. Try PUT as a fallback.
    ok, message = supervisor_request("/addons/self/options", payload=payload, method="POST")
    if ok:
        return True, "Configuration saved to Home Assistant add-on options."

    fallback_ok, fallback_message = supervisor_request("/addons/self/options", payload=payload, method="PUT")
    if fallback_ok:
        return True, "Configuration saved to Home Assistant add-on options."

    return False, f"Could not save configuration. POST failed: {message}; PUT failed: {fallback_message}"


def restart_addon():
    """Ask Supervisor to restart this add-on."""
    ok, message = supervisor_request("/addons/self/restart", payload={}, method="POST", timeout=5)
    if ok:
        return True, "Restart requested. The web UI may disconnect briefly."
    return False, f"Restart request failed: {message}"



def redirect_to_tab(tab="status", result="", message=""):
    """Redirect back to the web UI root after POST actions.

    Use ./? instead of ? so browsers do not stay on action routes such as
    /delete-config-backup. Use HTTP 303 so the browser follows with GET.
    """
    params = [f"tab={tab}"]
    if result:
        params.append(f"result={urllib.parse.quote(str(result))}")
    if message:
        params.append(f"message={urllib.parse.quote(str(message))}")
    return redirect("./?" + "&".join(params), code=303)


def render_index(action_result="", action_message="", active_tab="status", compare_data=None, restore_preview=None):
    options, error = load_options()
    grouped = build_grouped_config(options)

    # Performance note:
    # Fetching the live MQTT snapshot requires a short MQTT subscribe window.
    # Only do this on the Status tab. Config and Events should open quickly.
    live = fetch_mqtt_snapshot(options) if options and active_tab in ("status", "dashboard", "diagnostics") else None

    return render_template(
        "index.html",
        grouped=grouped,
        live=live,
        events=load_events(),
        error=error,
        action_result=action_result,
        action_message=action_message,
        active_tab=active_tab,
        config_yaml=generate_config_yaml(options),
        config_backups=list_config_backups(),
        config_backup_summary=config_backup_summary(),
        compare_data=compare_data,
        restore_preview=restore_preview,
        diagnostics=build_diagnostics(options, live) if options and active_tab == "diagnostics" else None,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@app.route("/", methods=["GET"])
def index():
    tab = request.args.get("tab", "status")
    result = request.args.get("result", "")
    message = request.args.get("message", "")

    compare_data = None
    restore_preview = None

    compare_filename = request.args.get("compare_backup", "")
    preview_filename = request.args.get("restore_preview", "")

    if compare_filename:
        options, error = load_options()
        if error:
            return render_index("warn", error, active_tab="backups")

        backup_options, read_message = load_config_backup(compare_filename)
        if backup_options is None:
            return render_index("warn", read_message, active_tab="backups")

        changes = compare_options(options, backup_options)
        compare_data = {
            "filename": compare_filename,
            "change_count": len(changes),
            "changes": changes,
        }
        tab = "backups"
        if not message:
            message = f"Comparison loaded for {compare_filename}."
            result = "ok"

    if preview_filename:
        options, error = load_options()
        if error:
            return render_index("warn", error, active_tab="backups")

        backup_options, read_message = load_config_backup(preview_filename)
        if backup_options is None:
            return render_index("warn", read_message, active_tab="backups")

        changes = compare_options(options, backup_options)
        restore_preview = {
            "filename": preview_filename,
            "change_count": len(changes),
            "changes": changes,
        }
        tab = "backups"
        if not message:
            message = f"Restore preview loaded for {preview_filename}. Review changes before restoring."
            result = "warn"

    return render_index(
        action_result=result,
        action_message=message,
        active_tab=tab,
        compare_data=compare_data,
        restore_preview=restore_preview,
    )


@app.route("/test-telegram", methods=["GET", "POST"])
def route_test_telegram():
    if request.method == "GET":
        return redirect_to_tab("status")

    options, error = load_options()
    if error:
        return redirect_to_tab("status", "warn", error)

    ok, message = test_telegram(options)
    append_event("telegram_test", "Telegram test", message, "ok" if ok else "warn")
    return redirect_to_tab("status", "ok" if ok else "warn", message)


@app.route("/test-mqtt", methods=["GET", "POST"])
def route_test_mqtt():
    if request.method == "GET":
        return redirect_to_tab("status")

    options, error = load_options()
    if error:
        return redirect_to_tab("status", "warn", error)

    ok, message = test_mqtt(options)
    append_event("mqtt_test", "MQTT test", message, "ok" if ok else "warn")
    return redirect_to_tab("status", "ok" if ok else "warn", message)


@app.route("/clear-events", methods=["POST"])
def route_clear_events():
    ok = clear_events()
    if ok:
        append_event("events", "Event history cleared", "Previous event history was cleared from the web UI.", "warn")
        return render_index("ok", "Event history cleared.", active_tab="events")
    return render_index("warn", "Could not clear event history.", active_tab="events")


@app.route("/export-events.json", methods=["GET"])
def route_export_events_json():
    events = load_events()
    payload = json.dumps(events, indent=2)
    return Response(
        payload,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=pacebms-events.json"},
    )


@app.route("/export-events.csv", methods=["GET"])
def route_export_events_csv():
    events = load_events()
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["time", "type", "level", "title", "detail"])
    writer.writeheader()
    for event in events:
        writer.writerow({
            "time": event.get("time", ""),
            "type": event.get("type", ""),
            "level": event.get("level", ""),
            "title": event.get("title", ""),
            "detail": event.get("detail", ""),
        })
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=pacebms-events.csv"},
    )




@app.route("/save-config", methods=["POST"])
def route_save_config():
    options, error = load_options()
    if error:
        return render_index("warn", error, active_tab="config")

    new_options = build_options_from_form(request.form, options)

    if new_options == options:
        message = "No configuration changes detected. Nothing was saved."
        append_event("config_save", "No config changes", message, "info")
        return redirect_to_tab("config", "ok", message)

    validation_errors = validate_addon_options(new_options)
    if validation_errors:
        message = "Configuration was not saved. Please fix: " + " | ".join(validation_errors)
        append_event("config_save", "Configuration save blocked", message, "warn")
        return redirect_to_tab("config", "warn", message)

    backup_ok, backup_message, backup_filename = create_config_backup("before-save")
    append_event("config_backup", "Configuration backup", backup_message, "ok" if backup_ok else "warn")

    ok, message = save_addon_options(new_options)

    if ok and backup_filename:
        message = message + f" Backup created: {backup_filename}"

    append_event("config_save", "Configuration save", message, "ok" if ok else "warn")

    if ok:
        return redirect_to_tab(
            "config",
            "ok",
            message + " Restart required for monitor runtime changes to apply.",
        )

    return redirect_to_tab("config", "warn", message)


@app.route("/restart-addon", methods=["POST"])
def route_restart_addon():
    ok, message = restart_addon()
    append_event("restart", "Add-on restart requested", message, "warn" if ok else "danger")
    return redirect_to_tab("backups", "ok" if ok else "warn", message)




@app.route("/download-all-config-backups.zip", methods=["GET"])
def route_download_all_config_backups_zip():
    ensure_config_backup_dir()
    backups = list(Path(CONFIG_BACKUP_DIR).glob("options-backup-*.json"))

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in backups:
            zf.write(path, arcname=path.name)

    memory_file.seek(0)
    return Response(
        memory_file.getvalue(),
        mimetype="application/zip",
        headers={"Content-Disposition": "attachment; filename=pacebms-config-backups.zip"},
    )


@app.route("/delete-config-backup/<filename>", methods=["POST"])
def route_delete_config_backup(filename):
    ok, message = delete_config_backup(filename)
    append_event(
        "config_backup_delete",
        "Configuration backup deleted" if ok else "Configuration backup delete failed",
        message,
        "ok" if ok else "warn",
    )
    return redirect_to_tab("backups", "ok" if ok else "warn", message)


@app.route("/compare-config-backup/<filename>", methods=["GET"])
def route_compare_config_backup(filename):
    options, error = load_options()
    if error:
        return render_index("warn", error, active_tab="config")

    backup_options, read_message = load_config_backup(filename)
    if backup_options is None:
        return render_index("warn", read_message, active_tab="backups")

    changes = compare_options(options, backup_options)
    compare_data = {
        "filename": filename,
        "change_count": len(changes),
        "changes": changes,
    }

    return render_index("ok", f"Comparison loaded for {filename}.", active_tab="backups", compare_data=compare_data)


@app.route("/preview-restore-config-backup/<filename>", methods=["GET"])
def route_preview_restore_config_backup(filename):
    options, error = load_options()
    if error:
        return render_index("warn", error, active_tab="config")

    backup_options, read_message = load_config_backup(filename)
    if backup_options is None:
        return render_index("warn", read_message, active_tab="backups")

    changes = compare_options(options, backup_options)
    restore_preview = {
        "filename": filename,
        "change_count": len(changes),
        "changes": changes,
    }

    return render_index("warn", f"Restore preview loaded for {filename}. Review changes before restoring.", active_tab="backups", restore_preview=restore_preview)



@app.route("/delete-config-backup", methods=["POST"])
def route_delete_config_backup_post():
    filename = request.form.get("filename", "")
    ok, message = delete_config_backup(filename)
    append_event(
        "config_backup_delete",
        "Configuration backup deleted" if ok else "Configuration backup delete failed",
        message,
        "ok" if ok else "warn",
    )
    return redirect_to_tab("backups", "ok" if ok else "warn", message)


@app.route("/restore-config-backup", methods=["POST"])
def route_restore_config_backup_post():
    filename = request.form.get("filename", "")
    backup_options, read_message = load_config_backup(filename)
    if backup_options is None:
        append_event("config_restore", "Configuration restore failed", read_message, "warn")
        return redirect_to_tab("backups", "warn", read_message)

    pre_ok, pre_message, pre_filename = create_config_backup("before-restore")
    append_event("config_backup", "Pre-restore configuration backup", pre_message, "ok" if pre_ok else "warn")

    ok, message = save_addon_options(backup_options)
    if ok:
        detail = f"Restored backup: {filename}"
        if pre_filename:
            detail += f" | Previous config backed up as: {pre_filename}"
        append_event("config_restore", "Configuration restored", detail, "ok")
        return redirect_to_tab(
            "backups",
            "ok",
            "Configuration restored from backup. Restart required for runtime changes to apply.",
        )

    append_event("config_restore", "Configuration restore failed", message, "warn")
    return redirect_to_tab("backups", "warn", f"Restore failed: {message}")


@app.route("/download-config-backup/<filename>", methods=["GET"])
def route_download_config_backup(filename):
    path = safe_backup_path(filename)
    if not path:
        return Response("Backup not found.", mimetype="text/plain", status=404)

    with open(path, "r", encoding="utf-8") as f:
        payload = f.read()

    return Response(
        payload,
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={os.path.basename(path)}"},
    )


@app.route("/create-config-backup", methods=["POST"])
def route_create_config_backup():
    requested_tab = request.form.get("active_tab", "backups")
    ok, message, filename = create_config_backup("manual")
    append_event("config_backup", "Manual configuration backup", message, "ok" if ok else "warn")
    return redirect_to_tab(requested_tab, "ok" if ok else "warn", message)


@app.route("/restore-config-backup/<filename>", methods=["POST"])
def route_restore_config_backup(filename):
    backup_options, read_message = load_config_backup(filename)
    if backup_options is None:
        append_event("config_restore", "Configuration restore failed", read_message, "warn")
        return render_index("warn", read_message, active_tab="backups")

    pre_ok, pre_message, pre_filename = create_config_backup("before-restore")
    append_event("config_backup", "Pre-restore configuration backup", pre_message, "ok" if pre_ok else "warn")

    ok, message = save_addon_options(backup_options)
    if ok:
        detail = f"Restored backup: {filename}"
        if pre_filename:
            detail += f" | Previous config backed up as: {pre_filename}"
        append_event("config_restore", "Configuration restored", detail, "ok")
        return redirect_to_tab(
            "backups",
            "ok",
            "Configuration restored from backup. Restart required for runtime changes to apply.",
        )

    append_event("config_restore", "Configuration restore failed", message, "warn")
    return redirect_to_tab("backups", "warn", f"Restore failed: {message}")


@app.route("/export-config.yaml", methods=["GET"])
def route_export_config_yaml():
    options, error = load_options()
    if error:
        return Response(error, mimetype="text/plain", status=500)

    payload = generate_config_yaml(options)
    return Response(
        payload,
        mimetype="text/yaml",
        headers={"Content-Disposition": "attachment; filename=pacebms-config-helper.yaml"},
    )



@app.route("/icon.png", methods=["GET"])
def route_icon_png():
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
    if os.path.exists(icon_path):
        return send_file(icon_path, mimetype="image/png")
    return Response("Icon not found.", mimetype="text/plain", status=404)


@app.route("/api/status", methods=["GET"])
def api_status():
    options, error = load_options()
    if error:
        return jsonify({"ok": False, "error": error}), 500
    return jsonify(fetch_mqtt_snapshot(options))


@app.route("/api/events", methods=["GET"])
def api_events():
    return jsonify({"ok": True, "events": load_events()})




@app.route("/download-support-bundle.zip", methods=["GET"])
def route_download_support_bundle_zip():
    options, error = load_options()
    if error:
        return Response(error, mimetype="text/plain", status=500)

    diagnostics = build_diagnostics(options)
    events = load_events()
    backup_summary = build_backup_summary_for_support()
    sanitized_config = build_sanitized_config(options)
    readme = build_support_readme()

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("diagnostics.json", json.dumps(diagnostics, indent=2))
        zf.writestr("events.json", json.dumps(events, indent=2))
        zf.writestr("backup-summary.json", json.dumps(backup_summary, indent=2))
        zf.writestr("sanitized-config.json", json.dumps(sanitized_config, indent=2))
        zf.writestr("readme-support.txt", readme)

    memory_file.seek(0)

    return Response(
        memory_file.getvalue(),
        mimetype="application/zip",
        headers={"Content-Disposition": "attachment; filename=pacebms-support-bundle.zip"},
    )


@app.route("/download-diagnostics.json", methods=["GET"])
def route_download_diagnostics_json():
    options, error = load_options()
    if error:
        return Response(error, mimetype="text/plain", status=500)

    report = build_diagnostics(options)
    payload = json.dumps(report, indent=2)

    return Response(
        payload,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=pacebms-diagnostics.json"},
    )


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8099)
