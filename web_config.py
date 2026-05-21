import csv
import io
import json
import logging
import re
import os
import sqlite3
from pathlib import Path
import threading
import time
import zipfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from logging.handlers import RotatingFileHandler
from flask import Flask, Response, jsonify, render_template, request, send_file, redirect

import paho.mqtt.client as mqtt
import yaml
from bms_notify import telegram_value_configured
from battery_profiles import BATTERY_PROFILE_CHOICES, effective_warning_references, normalize_profile
from bms_live import LIVE_SNAPSHOT_PATH, load_live_snapshot
from bms_history import HISTORY_DB_PATH, init_history_db, query_history

app = Flask(__name__)

OPTIONS_PATH = "/data/options.json"
PENDING_OPTIONS_PATH = "/data/options.pending.json"
EVENT_LOG_PATH = "/data/events.json"
MONITOR_HEALTH_PATH = "/data/monitor_health.json"
CONFIG_BACKUP_DIR = "/data/config_backups"
MONITOR_LOG_PATH = "/data/pacebms-monitor.log"
WEB_LOG_PATH = "/data/pacebms-web.log"
WARNING_NOTIFY_STATE_PATH = "/data/warning_notify_state.json"
WARNING_NOTIFY_CLEAR_FLAG_PATH = "/data/clear_warning_notify_state.flag"
MAX_CONFIG_BACKUPS = 10
MAX_EVENT_LOG_ENTRIES = 50
MAX_LOG_VIEW_LINES = 400
DEPRECATED_OPTION_KEYS = {"bms_ip", "bms_port"}
WEB_STARTED_AT = time.time()
LIVE_SNAPSHOT_REFRESH_SECONDS = 5
LIVE_SNAPSHOT_MAX_AGE_SECONDS = 60
_LIVE_SNAPSHOT_LOCK = threading.Lock()
_LIVE_SNAPSHOT_CACHE = {
    "options_key": None,
    "snapshot": None,
    "updated_at": 0.0,
    "error": "",
}
_LIVE_SNAPSHOT_WORKER_STARTED = False


def load_addon_version():
    try:
        config_path = Path(__file__).resolve().parent / "config.yaml"
        with config_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return str(data.get("version") or "Unknown")
    except Exception:
        return "Unknown"


ADDON_VERSION = load_addon_version()

SECTION_HELP = {
    "History & Live Data": "Controls how the web UI reads live battery values and how local history is stored. Auto uses the monitor-owned live serial snapshot first and falls back to retained MQTT only when configured. Metrics are stored locally in SQLite under /data and never write to the BMS.",
    "Battery Profile & References": "Selects the read-only battery profile used for warning explanations. Auto detect uses detected cell count: 13S defaults suit Hubble AM2-style packs, and 16S defaults suit Eenovance MANA LFP-style packs. Custom references use your configured cell high/low values. These references affect UI and Telegram interpretation only; they never write to the BMS.",
    "Notification Thresholds": "Controls SOC, SOH, stale-data and BMS warning repeat timing. notify_soc_low_thresholds must use comma-separated numbers only, for example 50,25,10. Do not use percentage signs. SOC high and SOH thresholds use single percentage numbers. Stale and warning repeat values are in seconds. BMS warning repeats are severity-aware: caution repeats for low-risk ongoing warnings, warning repeats for near-limit conditions, and critical repeats for protection/fault or measured values outside configured references.",
    "Scheduled Reports": "Controls scheduled Telegram report toggles, report times, delta report window and the daily energy current deadband. Use 24-hour HH:MM format, for example 19:00, 10:15 or 00:00.",
}

CONFIG_SECTION_BADGES = {
    "BMS Connection": "Required",
    "History & Live Data": "Required",
    "MQTT": "Optional",
    "Advanced": "Required",
    "Telegram": "Optional",
    "Notifications": "Optional",
    "FET Notifications": "Optional",
    "Battery Profile & References": "Optional",
    "Notification Thresholds": "Optional",
    "Warning Detail": "Optional",
    "Scheduled Reports": "Optional",
}

CONFIG_SECTION_TIERS = {
    "BMS Connection": "required",
    "History & Live Data": "required",
    "MQTT": "advanced",
    "Advanced": "required",
    "Telegram": "monitoring",
    "Notifications": "monitoring",
    "FET Notifications": "monitoring",
    "Battery Profile & References": "monitoring",
    "Notification Thresholds": "monitoring",
    "Warning Detail": "monitoring",
    "Scheduled Reports": "monitoring",
}

GROUPS = {
    "BMS Connection": [
        "bms_connection_mode",
        "connection_type",
        "bms_serial",
        "bms_baudrate",
        "scan_interval",
    ],
    "History & Live Data": [
        "ui_data_source",
        "metrics_enabled",
        "history_sample_seconds",
        "history_cell_sample_seconds",
        "history_retention_days",
        "history_event_retention_days",
    ],
    "MQTT": [
        "mqtt_enabled",
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
    "Advanced": [
        "debug_output",
        "zero_pad_number_cells",
        "zero_pad_number_packs",
    ],
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
    ],
    "FET Notifications": [
        "notify_fet",
        "notify_ignore_charge_fet_off_when_full",
        "notify_alert_discharge_fet_off",
        "notify_fet_repeat_seconds",
    ],
    "Notification Thresholds": [
        "notify_soc_low_thresholds",
        "notify_soc_high_threshold",
        "notify_soc_high_reset",
        "notify_soh_threshold",
        "notify_retry_count",
        "notify_stale_data_seconds",
        "notify_stale_data_repeat_seconds",
        "notify_warning_repeat_seconds",
        "notify_warning_repeat_caution_seconds",
        "notify_warning_repeat_warning_seconds",
        "notify_warning_repeat_critical_seconds",
        "notify_warning_clear_confirm_reads",
    ],
    "Warning Detail": [
        "notify_warning_detail_enabled",
        "notify_include_highest_and_lowest_cell",
        "notify_include_pack_voltage",
        "notify_include_soc_soh",
    ],
    "Scheduled Reports": [
        "notify_daily_summary",
        "notify_daily_summary_time",
        "notify_delta_report_time",
        "notify_delta_window_start",
        "notify_delta_window_end",
        "daily_energy_current_deadband_a",
    ],
    "Battery Profile & References": [
        "battery_profile",
        "notify_bms_warning_policy",
        "expected_cell_count",
        "expected_pack_count",
        "capacity_fallback_enabled",
        "capacity_per_pack_ah",
        "notify_cell_high_warn_voltage",
        "notify_cell_low_warn_voltage",
        "notify_cell_delta_warn_mv",
        "notify_temp_high_warn_c",
        "notify_temp_low_warn_c",
        "notify_alert_cell_high_voltage",
        "notify_alert_cell_low_voltage",
        "notify_alert_cell_delta",
        "notify_alert_pack_high_voltage",
        "notify_alert_pack_low_voltage",
        "notify_alert_temp_high",
        "notify_alert_temp_low",
        "notify_include_all_cells_above_threshold",
        "notify_include_all_cells_below_threshold",
        "notify_delta_report",
    ],
}

SENSITIVE_KEYS = {
    "telegram_bot_token",
    "telegram_chat_id",
    "mqtt_password",
}

DEFAULT_OPTION_VALUES = {
    "bms_connection_mode": "Serial",
    "connection_type": "Serial",
    "bms_serial": "/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_D-if00-port0",
    "bms_baudrate": 9600,
    "scan_interval": 5,
    "ui_data_source": "auto",
    "metrics_enabled": True,
    "history_sample_seconds": 10,
    "history_cell_sample_seconds": 30,
    "history_retention_days": 90,
    "history_event_retention_days": 365,
    "mqtt_enabled": True,
    "mqtt_host": "192.168.10.16",
    "mqtt_port": 1883,
    "mqtt_user": "YOUR_MQTT_USER",
    "mqtt_password": "YOUR_MQTT_PASSWORD",
    "mqtt_base_topic": "pacebms",
    "mqtt_ha_discovery": True,
    "mqtt_ha_discovery_topic": "homeassistant",
    "mqtt_retain_state": True,
    "state_force_republish_seconds": 300,
    "warn_force_republish_seconds": 300,
    "debug_output": 0,
    "zero_pad_number_cells": 2,
    "zero_pad_number_packs": 2,
    "expected_cell_count": 0,
    "expected_pack_count": 0,
    "capacity_fallback_enabled": False,
    "capacity_per_pack_ah": 0.0,
    "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
    "telegram_chat_id": "YOUR_TELEGRAM_CHAT_ID",
    "notify_enabled": True,
    "notify_startup": True,
    "notify_disconnect": True,
    "notify_stale_data": True,
    "notify_stale_recovery": True,
    "notify_soc_low": True,
    "notify_soc_high": True,
    "notify_soc_high_on_startup": False,
    "notify_soh": True,
    "notify_soh_on_startup": False,
    "notify_warnings": True,
    "notify_warning_detail_enabled": True,
    "notify_fet": True,
    "notify_daily_summary": True,
    "notify_delta_report": True,
    "notify_soc_low_thresholds": "50,25,10",
    "notify_soc_high_threshold": 98,
    "notify_soc_high_reset": 95,
    "notify_soh_threshold": 95,
    "notify_retry_count": 1,
    "notify_stale_data_seconds": 120,
    "notify_stale_data_repeat_seconds": 1800,
    "notify_warning_repeat_seconds": 1800,
    "notify_warning_repeat_caution_seconds": 21600,
    "notify_warning_repeat_warning_seconds": 3600,
    "notify_warning_repeat_critical_seconds": 1800,
    "notify_warning_clear_confirm_reads": 2,
    "battery_profile": "auto",
    "notify_bms_warning_policy": "user_reference_or_critical",
    "notify_cell_high_warn_voltage": 4.20,
    "notify_cell_low_warn_voltage": 3.00,
    "notify_cell_delta_warn_mv": 100,
    "notify_temp_high_warn_c": 55,
    "notify_temp_low_warn_c": 0,
    "notify_alert_cell_high_voltage": True,
    "notify_alert_cell_low_voltage": True,
    "notify_alert_cell_delta": True,
    "notify_alert_pack_high_voltage": True,
    "notify_alert_pack_low_voltage": True,
    "notify_alert_temp_high": True,
    "notify_alert_temp_low": True,
    "notify_include_all_cells_above_threshold": True,
    "notify_include_all_cells_below_threshold": True,
    "notify_include_highest_and_lowest_cell": True,
    "notify_include_pack_voltage": True,
    "notify_include_soc_soh": True,
    "notify_ignore_charge_fet_off_when_full": True,
    "notify_alert_discharge_fet_off": True,
    "notify_fet_repeat_seconds": 3600,
    "notify_daily_summary_time": "19:00",
    "daily_energy_current_deadband_a": 0.2,
    "notify_delta_report_time": "10:15",
    "notify_delta_window_start": "00:00",
    "notify_delta_window_end": "10:00",
}

WARNING_TELEGRAM_POLICY_CHOICES = {
    "all_bms_warnings": "Alert on all BMS warnings",
    "user_reference_or_critical": "Alert on user reference exceeded, plus BMS critical/protection",
    "user_reference_only": "Alert only when user reference is exceeded",
}

DEBUG_OUTPUT_CHOICES = {
    0: "0 - Normal",
    1: "1 - Summary troubleshooting",
    2: "2 - Poll troubleshooting",
    3: "3 - Protocol/raw frame troubleshooting",
}

BMS_CONNECTION_MODE_CHOICES = {
    "Serial": "Serial",
}

UI_DATA_SOURCE_CHOICES = {
    "monitor_live": "Live serial data",
    "auto": "Live serial data, fallback to MQTT",
    "mqtt_retained": "MQTT retained data only",
}


def load_options():
    if not os.path.exists(OPTIONS_PATH):
        return {}, "No /data/options.json file found yet."
    try:
        with open(OPTIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f), None
    except Exception as exc:
        return {}, f"Could not read /data/options.json: {exc}"


def load_pending_options():
    try:
        if not os.path.exists(PENDING_OPTIONS_PATH):
            return None
        with open(PENDING_OPTIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("options"), dict):
            return data
    except Exception:
        return None
    return None


def clear_pending_options():
    try:
        if os.path.exists(PENDING_OPTIONS_PATH):
            os.remove(PENDING_OPTIONS_PATH)
    except Exception:
        pass


def save_pending_options(options):
    """Keep saved-but-not-restarted config visible in the web UI."""
    payload = {
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "restart_required": True,
        "options": options,
    }
    tmp_path = f"{PENDING_OPTIONS_PATH}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp_path, PENDING_OPTIONS_PATH)
        return True
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return False


def config_options_for_edit(runtime_options):
    """Return Config-tab values, including pending saved options before restart."""
    pending = load_pending_options()
    if not pending:
        return runtime_options, None

    pending_options = pending.get("options")
    if pending_options == runtime_options:
        clear_pending_options()
        return runtime_options, None

    return pending_options, pending


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


def load_monitor_health():
    try:
        if not os.path.exists(MONITOR_HEALTH_PATH):
            return None
        with open(MONITOR_HEALTH_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


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

    token = str(options.get("telegram_bot_token", "") or "").strip()
    chat_id = str(options.get("telegram_chat_id", "") or "").strip()

    if not telegram_value_configured(token) or not telegram_value_configured(chat_id):
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
        return False, f"Telegram test failed: {type(exc).__name__}"


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


def mqtt_value_configured(value):
    text = str(value or "").strip()
    return bool(text) and not text.upper().startswith("YOUR_MQTT_")


def build_setup_checklist(options, live=None, history_status=None):
    """Build first-run setup status for the web UI.

    This is a read-only configuration guide. It checks add-on options and
    retained MQTT status only; it does not communicate with the BMS.
    """
    options = options or {}
    live = live or {}

    telegram_configured = (
        telegram_value_configured(options.get("telegram_bot_token"))
        and telegram_value_configured(options.get("telegram_chat_id"))
    )
    telegram_enabled = bool(options.get("notify_enabled", True))
    try:
        mqtt_port = int(options.get("mqtt_port", 0) or 0)
    except Exception:
        mqtt_port = 0
    mqtt_enabled = bool(options.get("mqtt_enabled", DEFAULT_OPTION_VALUES["mqtt_enabled"]))
    mqtt_configured = mqtt_enabled and mqtt_value_configured(options.get("mqtt_host")) and mqtt_port > 0
    bms_configured = (
        str(options.get("connection_type", "")).strip().lower() == "serial"
        and bool(str(options.get("bms_serial", "")).strip())
    )
    discovery_enabled = bool(options.get("mqtt_ha_discovery", False))
    retained_enabled = bool(options.get("mqtt_retain_state", False))
    try:
        warning_repeats = all(
            int(options.get(key, 0) or 0) >= 60
            for key in (
                "notify_warning_repeat_caution_seconds",
                "notify_warning_repeat_warning_seconds",
                "notify_warning_repeat_critical_seconds",
            )
        )
    except Exception:
        warning_repeats = False
    monitor_seen = str(live.get("monitor_state", "")).lower() == "running" or str(live.get("availability", "")).lower() == "online"
    bms_reads_seen = live.get("last_analog_read", "Unknown") not in ("Unknown", "Not available", "")
    history_status = history_status or build_history_status(options)
    history_enabled = str(history_status.get("enabled", "")).upper() == "ON"
    history_has_sample = history_status.get("latest_sample", "No data") not in ("No data", "Unknown", "")
    history_has_error = bool(history_status.get("error"))
    expected_cells = int(_to_float(options.get("expected_cell_count"), 0) or 0)
    expected_packs = int(_to_float(options.get("expected_pack_count"), 0) or 0)
    detected_cells = int(_to_float(live.get("total_cells"), 0) or 0)
    detected_packs = int(_to_float(live.get("pack_count"), 0) or 0)
    layout_check_enabled = expected_cells > 0 or expected_packs > 0
    layout_matches = True
    layout_details = []
    if expected_cells > 0:
        layout_matches = layout_matches and (detected_cells == 0 or detected_cells == expected_cells)
        layout_details.append(f"expected {expected_cells} total cells")
    if expected_packs > 0:
        layout_matches = layout_matches and (detected_packs == 0 or detected_packs == expected_packs)
        layout_details.append(f"expected {expected_packs} pack(s)")

    items = [
        {
            "title": "BMS Serial",
            "status": "Ready" if bms_configured else "Needs setup",
            "class": "healthy" if bms_configured else "warning",
            "detail": "Serial connection is configured." if bms_configured else "Set BMS connection mode to Serial and choose the BMS USB/serial path.",
        },
        {
            "title": "MQTT",
            "status": "Ready" if mqtt_configured else ("Disabled" if not mqtt_enabled else "Needs setup"),
            "class": "healthy" if mqtt_configured or not mqtt_enabled else "warning",
            "detail": "MQTT host and port are configured." if mqtt_configured else ("MQTT is disabled; web UI uses live serial data." if not mqtt_enabled else "Set mqtt_host, mqtt_port and credentials for your MQTT broker."),
        },
        {
            "title": "Home Assistant Discovery",
            "status": "Enabled" if mqtt_enabled and discovery_enabled else "Disabled",
            "class": "healthy" if not mqtt_enabled or discovery_enabled else "warning",
            "detail": "Home Assistant can auto-create MQTT entities." if mqtt_enabled and discovery_enabled else ("MQTT is disabled; discovery is not used." if not mqtt_enabled else "Enable mqtt_ha_discovery for automatic Home Assistant sensors."),
        },
        {
            "title": "Retained State",
            "status": "Enabled" if mqtt_enabled and retained_enabled else "Disabled",
            "class": "healthy" if not mqtt_enabled or retained_enabled else "warning",
            "detail": "MQTT retains latest values for HA fallback." if mqtt_enabled and retained_enabled else ("MQTT is disabled; retained fallback is not used." if not mqtt_enabled else "Enable mqtt_retain_state so HA and fallback values recover after reconnects."),
        },
        {
            "title": "Monitor Seen",
            "status": "Running" if monitor_seen else "Waiting",
            "class": "healthy" if monitor_seen else "warning",
            "detail": f"Monitor status has been seen through {live.get('data_source', 'the current data source')}." if monitor_seen else "Start the add-on and confirm monitor state appears.",
        },
        {
            "title": "BMS Reads",
            "status": "Seen" if bms_reads_seen else "Waiting",
            "class": "healthy" if bms_reads_seen else "warning",
            "detail": f"Last analog read: {live.get('last_analog_read', 'Unknown')}" if bms_reads_seen else "Waiting for a successful analog read from the BMS.",
        },
        {
            "title": "Battery Layout",
            "status": "Auto" if not layout_check_enabled else ("Matches" if layout_matches else "Check"),
            "class": "healthy" if not layout_check_enabled or layout_matches else "warning",
            "detail": (
                "No expected pack/cell count is configured; using detected BMS layout."
                if not layout_check_enabled
                else f"{', '.join(layout_details)}. Detected: {detected_packs or 'Unknown'} pack(s), {detected_cells or 'Unknown'} total cells."
            ),
        },
        {
            "title": "Telegram",
            "status": "Ready" if telegram_configured and telegram_enabled else "Needs setup",
            "class": "healthy" if telegram_configured and telegram_enabled else "warning",
            "detail": "Telegram notifications are enabled and credentials are configured." if telegram_configured and telegram_enabled else "Set a real Telegram bot token/chat ID or disable notify_enabled.",
        },
        {
            "title": "Warning Noise Control",
            "status": "Ready" if warning_repeats else "Check",
            "class": "healthy" if warning_repeats else "warning",
            "detail": "Severity-aware warning repeat intervals are configured." if warning_repeats else "Set caution, warning and critical repeat intervals to at least 60 seconds.",
        },
        {
            "title": "Local History",
            "status": "Ready" if history_enabled and history_has_sample and not history_has_error else ("Disabled" if not history_enabled else "Waiting"),
            "class": "healthy" if history_enabled and history_has_sample and not history_has_error else ("off" if not history_enabled else "warning"),
            "detail": (
                f"Latest sample: {history_status.get('latest_sample', 'No data')}"
                if history_enabled and history_has_sample and not history_has_error
                else (
                    "Local history is disabled; graphs will not retain long-term samples."
                    if not history_enabled
                    else f"Waiting for SQLite samples. {history_status.get('error') or 'Confirm the monitor is running and Store local history is enabled.'}"
                )
            ),
        },
    ]

    ready = sum(1 for item in items if item["class"] == "healthy")
    if ready == len(items):
        summary = "Full Monitoring setup looks ready."
        summary_class = "healthy"
    elif bms_configured:
        summary = "Basic Required serial setup is ready; finish optional MQTT/Telegram monitoring items."
        summary_class = "warning"
    else:
        summary = "Basic Required setup still needs attention."
        summary_class = "warning"

    return {
        "ready_count": ready,
        "total_count": len(items),
        "summary": summary,
        "summary_class": summary_class,
        "items": items,
        "telegram_configured": telegram_configured,
        "telegram_enabled": telegram_enabled,
    }


def test_full_monitoring(options):
    """Dry-check Full Monitoring config without BMS access or Telegram send."""
    checklist = build_setup_checklist(options)
    errors = validate_addon_options(options)

    if bool(options.get("mqtt_enabled", DEFAULT_OPTION_VALUES["mqtt_enabled"])):
        mqtt_ok, mqtt_message = test_mqtt(options)
        if not mqtt_ok:
            errors.append(mqtt_message)

    if not checklist["telegram_configured"]:
        errors.append("Telegram bot token/chat ID are missing or still use placeholder values.")
    if not checklist["telegram_enabled"]:
        errors.append("notify_enabled is disabled, so direct Telegram monitoring is off.")

    if errors:
        return False, "Full Monitoring check needs attention: " + " | ".join(errors[:6])

    return True, "Full Monitoring dry check passed: enabled integrations, Telegram values and notification thresholds look valid. No BMS commands or Telegram messages were sent."


def seconds_label(value):
    seconds = _to_float(value)
    if seconds is None:
        return "Unknown"
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, rem = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {rem}s" if rem else f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h" if hours else f"{days}d"


def runtime_label_from_hours(hours):
    hours_f = _to_float(hours)
    if hours_f is None or hours_f < 0:
        return "Unknown"
    total_minutes = int(round(hours_f * 60))
    days, remainder = divmod(total_minutes, 1440)
    hrs, mins = divmod(remainder, 60)
    if days:
        return f"{days}d {hrs}h" if hrs else f"{days}d"
    if hrs:
        return f"{hrs}h {mins}m" if mins else f"{hrs}h"
    return f"{mins}m"


def _fmt_number(value, decimals=1, suffix=""):
    number = _to_float(value)
    if number is None:
        return "Unknown"
    if decimals == 0:
        return f"{int(round(number))}{suffix}"
    return f"{number:.{decimals}f}{suffix}"


def _calculate_user_summary(options, live):
    packs = live.get("packs", []) if isinstance(live, dict) else []
    if not packs:
        return {
            "status": "Waiting for data",
            "class": "warning",
            "summary": "No retained pack values are available yet.",
            "combined_soc": "Unknown",
            "combined_soh": "Unknown",
            "total_power_kw": "Unknown",
            "power_flow": "Unknown",
            "pack_voltage": "Unknown",
            "battery_current": "Unknown",
            "remaining_capacity_ah": "Unknown",
            "full_capacity_ah": "Unknown",
            "design_capacity_ah": "Unknown",
            "remaining_energy_kwh": "Unknown",
            "capacity_detail": "Full and design capacity are not available yet.",
            "time_label": "Battery Time",
            "runtime_remaining": "Unknown",
            "runtime_detail": "Waiting for retained energy and power values.",
            "health": "Unknown",
            "temperature": "Unknown",
            "temperature_status": "Unknown",
            "active_warnings": str(live.get("warning_count", 0) if isinstance(live, dict) else 0),
            "warning_summary": "Waiting for retained warning values.",
            "warning_class": "warning",
            "power_detail": "Waiting for current and voltage values.",
            "power_class": "warning",
            "last_updated": live.get("fetched_at", "Unknown") if isinstance(live, dict) else "Unknown",
        }

    total_power_kw = 0.0
    total_current = 0.0
    voltage_values = []
    soc_values = []
    soh_values = []
    temp_values = []
    remaining_ah = 0.0
    full_ah = 0.0
    design_ah = 0.0
    remaining_kwh = 0.0
    energy_needed_kwh = 0.0
    weighted_soc_total = 0.0
    weighted_soc_weight = 0.0
    weighted_soh_total = 0.0
    weighted_soh_weight = 0.0
    capacity_fallback_used = False

    for pack in packs:
        voltage = _to_float(pack.get("voltage"))
        current = _to_float(pack.get("current"))
        soc = _to_float(pack.get("soc"))
        soh = _to_float(pack.get("soh"))
        remain = _to_float(pack.get("remaining_capacity_ah"))
        full = _to_float(pack.get("full_capacity_ah"))
        design = _to_float(pack.get("design_capacity_ah"))
        fallback_used = False
        fallback_capacity = _to_float(options.get("capacity_per_pack_ah"), 0)
        if bool(options.get("capacity_fallback_enabled", False)) and fallback_capacity and fallback_capacity > 0:
            if full is None or full <= 0:
                full = fallback_capacity
                fallback_used = True
            if design is None or design <= 0:
                design = fallback_capacity
                fallback_used = True
            if remain is None and soc is not None:
                remain = fallback_capacity * max(0.0, min(100.0, soc)) / 100.0
                fallback_used = True

        if voltage is not None:
            voltage_values.append(voltage)
        if current is not None:
            total_current += current
        if voltage is not None and current is not None:
            total_power_kw += (voltage * current) / 1000.0
        if soc is not None:
            soc_values.append(soc)
            if full is not None and full > 0:
                weighted_soc_total += soc * full
                weighted_soc_weight += full
        if soh is not None:
            soh_values.append(soh)
            if full is not None and full > 0:
                weighted_soh_total += soh * full
                weighted_soh_weight += full
        if remain is not None:
            remaining_ah += remain
            if voltage is not None:
                remaining_kwh += voltage * remain / 1000.0
        if remain is not None and full is not None and voltage is not None and full > remain:
            energy_needed_kwh += voltage * (full - remain) / 1000.0
        if full is not None:
            full_ah += full
        if design is not None:
            design_ah += design
        if fallback_used:
            capacity_fallback_used = True
        for temp in pack.get("temperatures", []):
            temp_f = _to_float(temp)
            if temp_f is not None:
                temp_values.append(temp_f)

    if weighted_soc_weight:
        combined_soc = weighted_soc_total / weighted_soc_weight
    elif soc_values:
        combined_soc = sum(soc_values) / len(soc_values)
    else:
        combined_soc = None

    if weighted_soh_weight:
        combined_soh = weighted_soh_total / weighted_soh_weight
    elif soh_values:
        combined_soh = sum(soh_values) / len(soh_values)
    else:
        combined_soh = None

    fully_count = sum(1 for pack in packs if str(pack.get("fully", "")).upper() == "ON")
    warning_count = int(_to_float(live.get("warning_count"), 0) or 0)
    stale = str(live.get("stale", "Unknown")).upper()
    availability = str(live.get("availability", "Unknown")).lower()

    highest_warning, highest_warning_class = _highest_pack_warning(packs)

    idle_threshold_kw = 0.05
    if availability == "offline" or stale == "ON":
        status = "Communication stale"
        status_class = "stale"
    elif warning_count:
        status = highest_warning or "Warning"
        status_class = highest_warning_class or "warning"
    elif fully_count == len(packs) and abs(total_power_kw) <= idle_threshold_kw:
        status = "Fully charged"
        status_class = "healthy"
    elif total_power_kw > idle_threshold_kw:
        status = "Charging"
        status_class = "healthy"
    elif total_power_kw < -idle_threshold_kw:
        status = "Discharging"
        status_class = "warning"
    else:
        status = "Idle"
        status_class = "healthy"

    if total_power_kw > idle_threshold_kw:
        power_flow = f"Charging at {abs(total_power_kw):.2f} kW"
        power_detail = "Power is flowing into the battery."
        power_class = "charging"
    elif total_power_kw < -idle_threshold_kw:
        power_flow = f"Discharging at {abs(total_power_kw):.2f} kW"
        power_detail = "Power is flowing out of the battery."
        power_class = "discharging"
    else:
        power_flow = "Idle"
        power_detail = "No meaningful battery power flow detected."
        power_class = "idle"

    temp_high = _to_float(options.get("notify_temp_high_warn_c", 55), 55)
    temp_low = _to_float(options.get("notify_temp_low_warn_c", 0), 0)
    highest_temp = max(temp_values) if temp_values else None
    if highest_temp is None:
        temp_status = "Unknown"
        temp_class = "warning"
    elif highest_temp >= temp_high or min(temp_values) <= temp_low:
        temp_status = "Warning"
        temp_class = "warning"
    else:
        temp_status = "Normal"
        temp_class = "healthy"

    avg_voltage = sum(voltage_values) / len(voltage_values) if voltage_values else None
    health = min(soh_values) if soh_values else None
    summary = f"{status}. {len(packs)} pack(s), {live.get('total_cells', 0)} cells detected."
    runtime_remaining = "Unknown"
    time_label = "Battery Time"
    runtime_detail = "Estimate needs current power and capacity values."
    if total_power_kw < -idle_threshold_kw and remaining_kwh > 0:
        discharge_kw = abs(total_power_kw)
        time_label = "Runtime Estimate"
        runtime_remaining = runtime_label_from_hours(remaining_kwh / discharge_kw)
        runtime_detail = "Estimate based on current discharge power."
    elif total_power_kw > idle_threshold_kw and energy_needed_kwh > 0:
        time_label = "Charge Time Estimate"
        runtime_remaining = runtime_label_from_hours(energy_needed_kwh / total_power_kw)
        runtime_detail = "Charge-to-full estimate based on current charge power."
    elif total_power_kw > idle_threshold_kw:
        time_label = "Charge Time Estimate"
        runtime_remaining = "Charging"
        runtime_detail = "Charge time needs full and remaining capacity values."
    elif abs(total_power_kw) <= idle_threshold_kw:
        time_label = "Idle"
        runtime_remaining = "Idle"
        runtime_detail = "No meaningful discharge load detected."

    if availability == "offline" or stale == "ON":
        power_state = "Communication stale"
        power_state_class = "stale"
    elif fully_count == len(packs) and abs(total_power_kw) <= idle_threshold_kw:
        power_state = "Fully charged"
        power_state_class = "healthy"
    elif total_power_kw > idle_threshold_kw:
        power_state = "Charging"
        power_state_class = "healthy"
    elif total_power_kw < -idle_threshold_kw:
        power_state = "Discharging"
        power_state_class = "warning"
    else:
        power_state = "Idle"
        power_state_class = "healthy"

    if warning_count:
        warning_summary = f"{warning_count} active warning(s)"
        if highest_warning:
            warning_summary = f"{warning_summary} - highest severity: {highest_warning}"
        warning_class = highest_warning_class or "warning"
    else:
        warning_summary = "No active warnings"
        warning_class = "healthy"

    capacity_source_note = " | fallback used" if capacity_fallback_used else ""
    capacity_detail = f"Full: {_fmt_number(full_ah if full_ah else None, 0, ' Ah')} | Design: {_fmt_number(design_ah if design_ah else None, 0, ' Ah')}{capacity_source_note}"

    return {
        "status": status,
        "class": status_class,
        "power_state": power_state,
        "power_state_class": power_state_class,
        "summary": summary,
        "combined_soc": _fmt_number(combined_soc, 1, "%"),
        "combined_soh": _fmt_number(combined_soh, 1, "%"),
        "total_power_kw": _fmt_number(total_power_kw, 2, " kW"),
        "power_flow": power_flow,
        "power_detail": power_detail,
        "power_class": power_class,
        "pack_voltage": _fmt_number(avg_voltage, 2, " V"),
        "battery_current": _fmt_number(total_current, 2, " A"),
        "remaining_capacity_ah": _fmt_number(remaining_ah if remaining_ah else None, 0, " Ah"),
        "full_capacity_ah": _fmt_number(full_ah if full_ah else None, 0, " Ah"),
        "design_capacity_ah": _fmt_number(design_ah if design_ah else None, 0, " Ah"),
        "remaining_energy_kwh": _fmt_number(remaining_kwh if remaining_kwh else None, 2, " kWh"),
        "capacity_detail": capacity_detail,
        "time_label": time_label,
        "runtime_remaining": runtime_remaining,
        "runtime_detail": runtime_detail,
        "health": _fmt_number(health, 1, "%"),
        "temperature": _fmt_number(highest_temp, 1, " C"),
        "temperature_status": temp_status,
        "temperature_class": temp_class,
        "active_warnings": str(warning_count),
        "warning_summary": warning_summary,
        "warning_class": warning_class,
        "last_updated": live.get("fetched_at", "Unknown"),
    }


def build_monitoring_health(options, live=None, heartbeat=None):
    """Summarize whether the monitor is still watching the battery.

    This combines retained MQTT monitor values with the local heartbeat file.
    It is status-only and never communicates with the BMS.
    """
    options = options or {}
    live = live or {}
    heartbeat = heartbeat if heartbeat is not None else load_monitor_health()

    stale_seconds = int(_to_float(options.get("notify_stale_data_seconds"), 120) or 120)
    stale_repeat_seconds = int(_to_float(options.get("notify_stale_data_repeat_seconds"), 1800) or 1800)
    heartbeat_timeout = 60
    heartbeat_age = None
    heartbeat_state = "Unknown"
    heartbeat_label = "No heartbeat file yet"
    heartbeat_class = "warning"

    if isinstance(heartbeat, dict):
        heartbeat_state = str(heartbeat.get("state", "Unknown") or "Unknown")
        heartbeat_timeout = int(_to_float(heartbeat.get("health_timeout_seconds"), heartbeat_timeout) or heartbeat_timeout)
        updated_at = _to_float(heartbeat.get("updated_at"))
        if updated_at is not None:
            heartbeat_age = max(0, int(time.time() - updated_at))
            heartbeat_label = seconds_label(heartbeat_age)
            if heartbeat_age <= heartbeat_timeout and heartbeat_state.lower() != "stopped":
                heartbeat_class = "healthy"

    availability = str(live.get("availability", "Unknown"))
    monitor_state = str(live.get("monitor_state", "Unknown"))
    stale_state = str(live.get("stale", "Unknown")).upper()
    analog_age = _to_float(live.get("analog_age_seconds"))
    warn_age = _to_float(live.get("warn_age_seconds"))
    live_ok = bool(live.get("ok"))

    monitor_running = (
        availability.lower() == "online"
        and monitor_state.lower() == "running"
        and heartbeat_class == "healthy"
    )
    data_fresh = stale_state == "OFF" and analog_age is not None and analog_age <= stale_seconds
    warnings_fresh = warn_age is not None and warn_age <= stale_seconds
    pack_count = int(_to_float(live.get("pack_count"), 0) or 0)
    total_cells = int(_to_float(live.get("total_cells"), 0) or 0)

    data_source = str(live.get("data_source") or live.get("source") or "Unknown")

    if not live_ok:
        status = "Waiting for Data"
        status_class = "warning"
        summary = live.get("error") or "No live serial or retained MQTT values were received yet."
    elif not monitor_running:
        status = "Needs Attention"
        status_class = "warning"
        summary = "Monitor status or heartbeat is not confirmed healthy."
    elif stale_state == "ON" or not data_fresh:
        status = "Data Stale"
        status_class = "stale"
        summary = live.get("stale_reason") or "BMS data is older than the configured stale-data threshold."
    elif live.get("warning_count", 0):
        highest_warning, highest_warning_class = _highest_pack_warning(live.get("packs") or [])
        if highest_warning in ("BMS Caution", "Caution"):
            status = "Watching With Caution"
            summary = "Monitoring is active and the BMS reports a warning below configured references."
        else:
            status = "Watching With Warnings"
            summary = "Monitoring is active and one or more packs have BMS warnings."
        status_class = highest_warning_class or "warning"
    else:
        status = "Watching"
        status_class = "healthy"
        summary = f"Monitor heartbeat and {data_source} data look healthy."

    checks = [
        {
            "label": "Monitor heartbeat",
            "value": heartbeat_label,
            "class": heartbeat_class,
            "detail": f"State: {heartbeat_state} | Timeout: {heartbeat_timeout}s",
        },
        {
            "label": "Data source",
            "value": data_source,
            "class": "healthy" if live_ok else "warning",
            "detail": f"Snapshot source: {live.get('source', 'Unknown')}",
        },
        {
            "label": "Monitor state",
            "value": monitor_state,
            "class": "healthy" if availability.lower() == "online" and monitor_state.lower() == "running" else "warning",
            "detail": f"Availability: {availability}",
        },
        {
            "label": "Analog data age",
            "value": seconds_label(analog_age),
            "class": "healthy" if data_fresh else "warning",
            "detail": f"Last analog read: {live.get('last_analog_read', 'Unknown')}",
        },
        {
            "label": "Warning data age",
            "value": seconds_label(warn_age),
            "class": "healthy" if warnings_fresh else "warning",
            "detail": f"Last warning read: {live.get('last_warn_read', 'Unknown')}",
        },
        {
            "label": "Detected packs",
            "value": str(pack_count),
            "class": "healthy" if pack_count > 0 else "warning",
            "detail": live.get("layout", "Unknown"),
        },
        {
            "label": "Cell count",
            "value": str(total_cells),
            "class": "healthy" if total_cells > 0 else "warning",
            "detail": "Detected from current live data source.",
        },
    ]

    return {
        "status": status,
        "class": status_class,
        "summary": summary,
        "checks": checks,
        "stale_threshold_seconds": stale_seconds,
        "stale_repeat_seconds": stale_repeat_seconds,
        "heartbeat_age_seconds": heartbeat_age if heartbeat_age is not None else "Unknown",
        "heartbeat_timeout_seconds": heartbeat_timeout,
    }


def attach_monitoring_health(options, live):
    if isinstance(live, dict):
        live = normalize_live_snapshot_for_template(live, options)
        live["monitoring_health"] = build_monitoring_health(options, live)
        live["user_summary"] = _calculate_user_summary(options, live)
    return live


def _safe_cell_extreme(value):
    if not isinstance(value, dict):
        return {"number": "Unknown", "voltage": "Unknown"}
    return {
        "number": value.get("number") or "Unknown",
        "voltage": value.get("voltage") or "Unknown",
    }


def _severity_label_class(label):
    label = str(label or "")
    if label == "Critical":
        return "critical"
    if label in ("BMS Caution", "Caution"):
        return "caution"
    if label == "Normal":
        return "healthy"
    return "warning"


def _highest_pack_warning(packs):
    severity_rank = {"Critical": 3, "Warning": 2, "BMS Caution": 1, "Caution": 1}
    highest = None
    for pack in packs or []:
        if str(pack.get("warnings") or "Normal") == "Normal":
            continue
        label = str(pack.get("severity_label") or "Warning")
        if highest is None or severity_rank.get(label, 2) > severity_rank.get(highest, 2):
            highest = label
    return highest, _severity_label_class(highest) if highest else None


def _warning_signature(packs):
    parts = []
    for index, pack in enumerate(packs or [], start=1):
        if not isinstance(pack, dict):
            continue
        pack_id = str(pack.get("id") or f"{index:02d}")
        warnings = str(pack.get("warnings") or "Normal")
        severity_label = str(pack.get("severity_label") or "Normal")
        parts.append(f"{pack_id}:{warnings}:{severity_label}")
    return "||".join(parts)


def _apply_overall_warning_status(live):
    if not isinstance(live, dict):
        return live
    availability = str(live.get("availability", "Unknown")).lower()
    monitor_state = str(live.get("monitor_state", "Unknown")).lower()
    stale = str(live.get("stale", "Unknown")).upper()
    warning_count = int(_to_float(live.get("warning_count"), 0) or 0)

    if availability == "offline" or monitor_state in {"disconnected", "stopped"}:
        live["overall_status"] = "Offline"
        live["overall_class"] = "offline"
    elif stale == "ON":
        live["overall_status"] = "Stale"
        live["overall_class"] = "stale"
    elif warning_count > 0:
        highest, highest_class = _highest_pack_warning(live.get("packs") or [])
        live["overall_status"] = highest or "Warning"
        live["overall_class"] = highest_class or "warning"
    elif live.get("ok"):
        live["overall_status"] = "Healthy"
        live["overall_class"] = "healthy"
    else:
        live["overall_status"] = "Unknown"
        live["overall_class"] = "unknown"
    return live


def normalize_live_snapshot_for_template(live, options=None):
    """Fill optional retained MQTT fields so partial snapshots do not break rendering."""
    if not isinstance(live, dict):
        return live

    options = options or DEFAULT_OPTION_VALUES
    normalized = dict(live)
    raw_packs = normalized.get("packs") or []
    packs = []
    for index, raw_pack in enumerate(raw_packs, start=1):
        pack = dict(raw_pack or {})
        pack_id = str(pack.get("id") or f"{index:02d}")
        warnings = pack.get("warnings") or "Normal"
        severity_class = pack.get("severity_class")
        severity_label = pack.get("severity_label")
        if not severity_class or not severity_label:
            severity_class, severity_label = classify_warning_severity(
                warnings,
                normalized.get("availability", "online"),
                normalized.get("stale", "OFF"),
            )

        pack.update({
            "id": pack_id,
            "role": pack.get("role") or ("Master" if pack_id == "01" else "Slave"),
            "serial": pack.get("serial") or "Not reported",
            "cell_count": pack.get("cell_count") or "Unknown",
            "soc": pack.get("soc") or "Unknown",
            "soh": pack.get("soh") or "Unknown",
            "cycles": pack.get("cycles") or "Unknown",
            "remaining_capacity_ah": pack.get("remaining_capacity_ah") or "Unknown",
            "full_capacity_ah": pack.get("full_capacity_ah") or "Unknown",
            "design_capacity_ah": pack.get("design_capacity_ah") or "Unknown",
            "voltage": pack.get("voltage") or "Unknown",
            "current": pack.get("current") or "Unknown",
            "power_kw": pack.get("power_kw") or "Unknown",
            "delta": pack.get("delta") or "Unknown",
            "warnings": warnings,
            "severity_class": severity_class,
            "severity_label": severity_label,
            "highest_cell": _safe_cell_extreme(pack.get("highest_cell")),
            "lowest_cell": _safe_cell_extreme(pack.get("lowest_cell")),
            "cell_high_ref": pack.get("cell_high_ref") or "Unknown",
            "cell_low_ref": pack.get("cell_low_ref") or "Unknown",
            "pack_high_ref": pack.get("pack_high_ref") or "Unknown",
            "pack_low_ref": pack.get("pack_low_ref") or "Unknown",
            "charge_fet": pack.get("charge_fet") or "Unknown",
            "discharge_fet": pack.get("discharge_fet") or "Unknown",
            "fully": pack.get("fully") or "Unknown",
            "temperatures": pack.get("temperatures") if isinstance(pack.get("temperatures"), list) else [],
            "reference_checks": pack.get("reference_checks") if isinstance(pack.get("reference_checks"), list) else [],
        })
        if not pack.get("warning_intelligence"):
            cell_values = []
            for cell in pack.get("cells") or []:
                cell_num = _to_float(cell.get("number"))
                cell_v = _to_float(cell.get("voltage"))
                if cell_num is not None and cell_v is not None:
                    cell_values.append((int(cell_num), cell_v))
            pack_v = _to_float(pack.get("voltage"))
            cell_high_ref = _to_float(pack.get("cell_high_ref"), _to_float(normalized.get("cell_high_ref"), 4.20))
            cell_low_ref = _to_float(pack.get("cell_low_ref"), _to_float(normalized.get("cell_low_ref"), 3.00))
            pack_high_ref = _to_float(pack.get("pack_high_ref"))
            pack_low_ref = _to_float(pack.get("pack_low_ref"))
            pack["warning_intelligence"] = build_warning_intelligence(
                pack,
                warnings,
                sorted(cell_values, key=lambda item: item[0]),
                pack_v,
                cell_high_ref,
                cell_low_ref,
                pack_high_ref,
                pack_low_ref,
                pack.get("battery_profile", ""),
                pack.get("reference_source", ""),
                bool(options.get("notify_enabled", DEFAULT_OPTION_VALUES.get("notify_enabled", True)) and options.get("notify_warnings", DEFAULT_OPTION_VALUES.get("notify_warnings", True))),
                _to_float(options.get("notify_cell_delta_warn_mv", DEFAULT_OPTION_VALUES.get("notify_cell_delta_warn_mv")), 100),
                {
                    "notify_alert_cell_high_voltage": bool(options.get("notify_alert_cell_high_voltage", DEFAULT_OPTION_VALUES.get("notify_alert_cell_high_voltage", True))),
                    "notify_alert_cell_low_voltage": bool(options.get("notify_alert_cell_low_voltage", DEFAULT_OPTION_VALUES.get("notify_alert_cell_low_voltage", True))),
                    "notify_alert_cell_delta": bool(options.get("notify_alert_cell_delta", DEFAULT_OPTION_VALUES.get("notify_alert_cell_delta", True))),
                    "notify_alert_pack_high_voltage": bool(options.get("notify_alert_pack_high_voltage", DEFAULT_OPTION_VALUES.get("notify_alert_pack_high_voltage", True))),
                    "notify_alert_pack_low_voltage": bool(options.get("notify_alert_pack_low_voltage", DEFAULT_OPTION_VALUES.get("notify_alert_pack_low_voltage", True))),
                },
                options.get("notify_bms_warning_policy", DEFAULT_OPTION_VALUES.get("notify_bms_warning_policy", "user_reference_or_critical")),
            )
        _apply_ui_warning_severity(pack)
        packs.append(pack)

    normalized["packs"] = packs
    normalized["warning_signature"] = _warning_signature(packs)
    normalized["pack_count"] = normalized.get("pack_count") or len(packs)
    if not normalized.get("total_cells"):
        total_cells = 0
        for pack in packs:
            cell_count = _to_float(pack.get("cell_count"), 0)
            total_cells += int(cell_count or 0)
        normalized["total_cells"] = total_cells
    _apply_overall_warning_status(normalized)
    return normalized


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
        return "critical", "Critical"

    if "protection state" in lower or "short circuit" in lower:
        return "critical", "Critical"

    if "above cell volt" in lower or "above total volt" in lower:
        return "warning", "Warning"

    if "temp" in lower:
        return "warning", "Warning"

    if "fet" in lower:
        return "warning", "Warning"

    return "caution", "Caution"


def _margin_text(value, ref, direction):
    if value is None or ref is None:
        return "Unknown", "Unknown"
    if direction == "above":
        margin = ref - value
        if margin > 0.0005:
            return f"{margin:.3f} V below ref", "Not exceeded"
        if margin < -0.0005:
            return f"{abs(margin):.3f} V above ref", "Exceeded"
        return "0.000 V below ref", "At reference"
    margin = value - ref
    if margin > 0.0005:
        return f"{margin:.3f} V above ref", "Not exceeded"
    if margin < -0.0005:
        return f"{abs(margin):.3f} V below ref", "Exceeded"
    return "0.000 V above ref", "At reference"


def _extract_warning_cell_numbers(warnings, phrase):
    numbers = []
    for part in re.split(r"[\n|,;]+", str(warnings or "")):
        if phrase not in part.lower():
            continue
        match = re.search(r"\bcell\s*0*(\d+)\b", part, re.IGNORECASE)
        if match:
            numbers.append(int(match.group(1)))
    return sorted(set(numbers))


def _has_bms_high_cell_warning(warnings):
    low = str(warnings or "").lower()
    return (
        ("above cell" in low and "volt" in low)
        or ("above upper limit" in low and "cell" in low)
        or ("cell" in low and "volt protect" in low and "above" in low)
    )


def _has_bms_low_cell_warning(warnings):
    low = str(warnings or "").lower()
    return (
        (("lower cell" in low or "low cell" in low or "below cell" in low) and "volt" in low)
        or ("below lower limit" in low and "cell" in low)
        or ("cell" in low and "volt protect" in low and ("lower" in low or "below" in low))
    )


def _warning_cell_label_map(warnings, highest_cell_num=None, lowest_cell_num=None):
    labels = {}
    for cell_num in _extract_warning_cell_numbers(warnings, "above upper limit"):
        labels.setdefault(cell_num, []).append("BMS High Warning")
    for cell_num in _extract_warning_cell_numbers(warnings, "below lower limit"):
        labels.setdefault(cell_num, []).append("BMS Low Warning")
    if _has_bms_high_cell_warning(warnings) and highest_cell_num is not None:
        labels.setdefault(highest_cell_num, [])
        if "BMS High Warning" not in labels[highest_cell_num]:
            labels[highest_cell_num].append("BMS High Warning")
    if _has_bms_low_cell_warning(warnings) and lowest_cell_num is not None:
        labels.setdefault(lowest_cell_num, [])
        if "BMS Low Warning" not in labels[lowest_cell_num]:
            labels[lowest_cell_num].append("BMS Low Warning")
    return labels


def _margin_text_for_unit(value, ref, direction, unit, precision=1):
    if value is None or ref is None:
        return "Unknown", "Unknown"
    if direction == "above":
        margin = ref - value
        if margin > 0.0005:
            return f"{margin:.{precision}f} {unit} below ref", "Not exceeded"
        if margin < -0.0005:
            return f"{abs(margin):.{precision}f} {unit} above ref", "Exceeded"
        return f"{0:.{precision}f} {unit} below ref", "At reference"
    margin = value - ref
    if margin > 0.0005:
        return f"{margin:.{precision}f} {unit} above ref", "Not exceeded"
    if margin < -0.0005:
        return f"{abs(margin):.{precision}f} {unit} below ref", "Exceeded"
    return f"{0:.{precision}f} {unit} above ref", "At reference"


def _warning_status_class(status):
    return "critical" if status == "Exceeded" else ("warning" if status == "At reference" else "healthy")


def _show_reference_row(row):
    return row.get("status") != "Not exceeded"


def _bms_detail_status_text(status):
    if status == "Not exceeded":
        return "BMS caution"
    return status


def _bms_detail_status_class(status):
    if status == "Not exceeded":
        return "caution"
    return _warning_status_class(status)


def _warning_has_critical_or_protection_text(warnings):
    low = str(warnings or "").lower()
    critical_words = (
        "protection state",
        "protect",
        "fault state",
        "short circuit",
        "over current",
        "overcurrent",
        "lower cell volt protect",
        "above cell volt protect",
        "below cell volt protect",
    )
    return any(word in low for word in critical_words)


def _apply_ui_warning_severity(pack):
    if not isinstance(pack, dict):
        return
    warnings = str(pack.get("warnings") or "Normal")
    if warnings == "Normal":
        pack["severity_class"] = "healthy"
        pack["severity_label"] = "Normal"
        return
    if str(pack.get("severity_class") or "").lower() in ("critical", "offline", "stale"):
        return
    if _warning_has_critical_or_protection_text(warnings):
        pack["severity_class"] = "critical"
        pack["severity_label"] = "Critical"
        return

    warning_intelligence = pack.get("warning_intelligence") or {}
    rows = list(warning_intelligence.get("user_reference_rows") or [])
    for group in warning_intelligence.get("groups") or []:
        rows.extend(group.get("rows") or [])

    if any(row.get("status") == "Exceeded" for row in rows):
        pack["severity_class"] = "critical"
        pack["severity_label"] = "Critical"
    elif any(row.get("status") == "At reference" for row in rows):
        pack["severity_class"] = "warning"
        pack["severity_label"] = "Warning"
    else:
        pack["severity_class"] = "caution"
        pack["severity_label"] = "BMS Caution"


def build_warning_intelligence(
    pack,
    warnings,
    cell_values,
    pack_v,
    cell_high_ref,
    cell_low_ref,
    pack_high_ref,
    pack_low_ref,
    profile_label="",
    reference_source="",
    notify_enabled=True,
    cell_delta_ref=None,
    alert_toggles=None,
    telegram_policy="user_reference_or_critical",
):
    warning_text = str(warnings or "Normal")
    lower_warning = warning_text.lower()
    cell_map = {num: value for num, value in cell_values}
    alert_toggles = alert_toggles or {}

    def notify_state(key):
        enabled = bool(notify_enabled and alert_toggles.get(key, True))
        return {
            "notify": "On" if enabled else "Off",
            "notify_class": "healthy" if enabled else "warning",
            "notify_enabled": enabled,
        }

    def cell_row(cell_num, direction, ref, notify_key):
        value = cell_map.get(cell_num)
        margin, status = _margin_text(value, ref, direction)
        row = {
            "label": f"Cell {cell_num:02d}",
            "value": f"{value:.3f} V" if value is not None else "Unknown",
            "ref": f"{ref:.2f} V" if ref is not None else "Unknown",
            "margin": margin,
            "status": status,
            "class": _warning_status_class(status),
        }
        row.update(notify_state(notify_key))
        return row

    def bms_detail_row(row):
        detail = dict(row)
        raw_status = row.get("status")
        detail["status"] = _bms_detail_status_text(raw_status)
        detail["class"] = _bms_detail_status_class(raw_status)
        detail["reference_status"] = raw_status
        return detail

    def pack_row(direction, ref, notify_key):
        margin, status = _margin_text(pack_v, ref, direction)
        row = {
            "label": "Pack",
            "value": f"{pack_v:.3f} V" if pack_v is not None else "Unknown",
            "ref": f"{ref:.2f} V" if ref is not None else "Unknown",
            "margin": margin,
            "status": status,
        }
        row.update(notify_state(notify_key))
        row["class"] = _warning_status_class(status)
        return row

    def reference_row(label, value, ref, direction, unit, notify_key, value_precision=3, ref_precision=2, margin_precision=3):
        margin, status = _margin_text_for_unit(value, ref, direction, unit, margin_precision)
        value_text = f"{value:.{value_precision}f} {unit}" if value is not None else "Unknown"
        ref_text = f"{ref:.{ref_precision}f} {unit}" if ref is not None else "Unknown"
        row = {
            "label": label,
            "value": value_text,
            "ref": ref_text,
            "margin": margin,
            "status": status,
            "class": _warning_status_class(status),
        }
        row.update(notify_state(notify_key))
        return row

    high_cells = _extract_warning_cell_numbers(warning_text, "above upper limit")
    low_cells = _extract_warning_cell_numbers(warning_text, "below lower limit")

    if not high_cells and "above cell volt" in lower_warning and pack.get("highest_cell", {}).get("number") != "Unknown":
        high_cells = [int(pack["highest_cell"]["number"])]
    if not low_cells and ("lower cell volt" in lower_warning or "below lower limit" in lower_warning) and pack.get("lowest_cell", {}).get("number") != "Unknown":
        low_cells = [int(pack["lowest_cell"]["number"])]

    groups = []
    if high_cells or "above cell volt" in lower_warning:
        high_rows = [
            cell_row(cell_num, "above", cell_high_ref, "notify_alert_cell_high_voltage")
            for cell_num in high_cells
        ]
        if high_rows:
            groups.append({
                "title": "Above upper limit",
                "rows": [bms_detail_row(row) for row in high_rows],
            })
    if low_cells or "lower cell volt" in lower_warning:
        low_rows = [
            cell_row(cell_num, "below", cell_low_ref, "notify_alert_cell_low_voltage")
            for cell_num in low_cells
        ]
        if low_rows:
            groups.append({
                "title": "Below lower limit",
                "rows": [bms_detail_row(row) for row in low_rows],
            })
    if "above total volt" in lower_warning or "total voltage above upper limit" in lower_warning:
        high_pack_rows = [pack_row("above", pack_high_ref, "notify_alert_pack_high_voltage")]
        if high_pack_rows:
            groups.append({
                "title": "Pack voltage",
                "rows": [bms_detail_row(row) for row in high_pack_rows],
            })
    if "lower total volt" in lower_warning or "total voltage below lower limit" in lower_warning:
        low_pack_rows = [pack_row("below", pack_low_ref, "notify_alert_pack_low_voltage")]
        if low_pack_rows:
            groups.append({
                "title": "Low pack voltage",
                "rows": [bms_detail_row(row) for row in low_pack_rows],
            })

    highest_cell = pack.get("highest_cell", {}) if isinstance(pack, dict) else {}
    lowest_cell = pack.get("lowest_cell", {}) if isinstance(pack, dict) else {}
    highest_num = highest_cell.get("number")
    lowest_num = lowest_cell.get("number")
    highest_v = _to_float(highest_cell.get("voltage"))
    lowest_v = _to_float(lowest_cell.get("voltage"))
    cell_delta = _to_float(pack.get("delta") if isinstance(pack, dict) else None)

    user_reference_rows = [
        reference_row(
            f"High cell voltage ({'Cell ' + str(highest_num) if highest_num not in (None, 'Unknown') else 'highest cell'})",
            highest_v,
            cell_high_ref,
            "above",
            "V",
            "notify_alert_cell_high_voltage",
        ),
        reference_row(
            f"Low cell voltage ({'Cell ' + str(lowest_num) if lowest_num not in (None, 'Unknown') else 'lowest cell'})",
            lowest_v,
            cell_low_ref,
            "below",
            "V",
            "notify_alert_cell_low_voltage",
        ),
        reference_row(
            "Cell delta",
            cell_delta,
            cell_delta_ref,
            "above",
            "mV",
            "notify_alert_cell_delta",
            value_precision=0,
            ref_precision=0,
            margin_precision=0,
        ),
        reference_row(
            "Pack high voltage",
            pack_v,
            pack_high_ref,
            "above",
            "V",
            "notify_alert_pack_high_voltage",
        ),
        reference_row(
            "Pack low voltage",
            pack_v,
            pack_low_ref,
            "below",
            "V",
            "notify_alert_pack_low_voltage",
        ),
    ]
    user_reference_rows = [
        row for row in user_reference_rows
        if _show_reference_row(row)
    ]

    bms_exceeded = any(row.get("reference_status", row.get("status")) == "Exceeded" for group in groups for row in group["rows"])
    user_exceeded_rows = [row for row in user_reference_rows if row["status"] == "Exceeded"]
    notify_exceeded_rows = [row for row in user_exceeded_rows if row.get("notify_enabled")]
    exceeded = bool(bms_exceeded or user_exceeded_rows)
    has_warning = warning_text != "Normal"
    show_user_reference_details = bool(user_reference_rows)
    user_reference_summary = (
        "One or more user alert references are exceeded."
        if user_exceeded_rows
        else "All configured user alert references are within limits."
    )

    reference_checks = [
        f"Cell high reference: {cell_high_ref:.2f} V",
        f"Pack high reference: {pack_high_ref:.2f} V" if pack_high_ref is not None else "Pack high reference: Unknown",
    ]
    if profile_label:
        reference_checks.append(f"Battery profile: {profile_label}")
    if reference_source:
        reference_checks.append(f"Reference source: {reference_source}")
    if has_warning and not exceeded:
        reference_checks.append("BMS warning is active below configured reference.")
        reference_checks.append("BMS internal threshold appears lower than the configured user reference.")
    elif exceeded:
        reference_checks.append("One or more measured values exceed a configured user reference.")
    else:
        reference_checks.append("No active BMS warning and no user reference is exceeded.")

    policy_labels = {
        "all_bms_warnings": "All BMS warnings",
        "user_reference_or_critical": "User reference exceeded, plus BMS critical/protection",
        "user_reference_only": "User reference exceeded only",
    }
    policy_label = policy_labels.get(str(telegram_policy or ""), str(telegram_policy or "Default policy"))

    if not notify_enabled:
        telegram_decision = "Telegram BMS warning alerts are disabled."
        telegram_decision_class = "warning"
    elif notify_exceeded_rows and has_warning:
        telegram_decision = "Telegram alert allowed: BMS warning is active and an enabled user reference is exceeded."
        telegram_decision_class = "critical"
    elif notify_exceeded_rows:
        telegram_decision = "No BMS warning is active. The UI shows the user reference crossing as a watch condition; Telegram waits for the configured warning policy."
        telegram_decision_class = "warning"
    elif has_warning:
        if str(telegram_policy) == "all_bms_warnings":
            telegram_decision = "Telegram alert allowed by policy because any BMS warning may be sent."
            telegram_decision_class = "warning"
        elif str(telegram_policy) == "user_reference_only":
            telegram_decision = "Telegram filtered: BMS warning is active, but no enabled user reference is exceeded."
            telegram_decision_class = "healthy"
        elif _warning_has_critical_or_protection_text(warning_text):
            telegram_decision = "Telegram will send because this BMS warning includes critical/protection text. User reference values are not exceeded, but your policy allows critical BMS protection warnings."
            telegram_decision_class = "critical"
        else:
            telegram_decision = "Telegram filtered: BMS warning is active below user references and does not include critical/protection text."
            telegram_decision_class = "healthy"
    else:
        telegram_decision = "No Telegram warning is due: no BMS warning is active and no enabled user reference is exceeded."
        telegram_decision_class = "healthy"

    if not has_warning and user_exceeded_rows:
        interpretation = "No BMS warning is active, but one or more user-defined references are exceeded. Treat this as an app-side watch condition."
        suggested_action = "Watch the trend and confirm the configured references match the battery profile and your preferred alert policy."
    elif not has_warning:
        interpretation = "No active BMS warning is reported for this pack."
        suggested_action = "Continue normal monitoring."
    elif exceeded:
        interpretation = "BMS warning is active and at least one current measured value exceeds a configured user reference."
        suggested_action = "Review immediately and compare against the battery manufacturer limits."
    else:
        interpretation = "BMS warning is active even though the configured user references have not been exceeded. This usually means the BMS internal threshold is different from the app reference, or the warning was triggered briefly before the latest retained reading."
        suggested_action = "Keep watching the trend and verify the BMS internal thresholds against the configured user references."

    return {
        "groups": groups,
        "user_reference_rows": user_reference_rows,
        "show_user_reference_details": show_user_reference_details,
        "user_reference_summary": user_reference_summary,
        "reference_checks": reference_checks,
        "telegram_policy": policy_label,
        "telegram_decision": telegram_decision,
        "telegram_decision_class": telegram_decision_class,
        "interpretation": interpretation,
        "suggested_action": suggested_action,
    }


def fetch_mqtt_snapshot(options, timeout=0.45):
    """Read retained MQTT values for a live status overview.

    This connects briefly to the configured MQTT broker and subscribes to the
    add-on base topic. It only reads retained/current MQTT states. It does not
    publish anything and it does not communicate with the BMS directly.
    """
    if not bool(options.get("mqtt_enabled", DEFAULT_OPTION_VALUES["mqtt_enabled"])):
        return {
            "ok": False,
            "error": "MQTT is disabled.",
            "source": "mqtt_retained",
            "data_source": "MQTT disabled",
            "packs": [],
            "pack_count": 0,
            "total_cells": 0,
            "warning_count": 0,
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    host = options.get("mqtt_host")
    port = int(options.get("mqtt_port", 1883) or 1883)
    user = options.get("mqtt_user", "")
    password = options.get("mqtt_password", "")
    base_topic = options.get("mqtt_base_topic", "pacebms").strip().strip("/")

    result = {
        "ok": False,
        "error": "",
        "source": "mqtt_retained",
        "data_source": "MQTT fallback",
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
        temp_prefix = f"{pfx}/temps/temp_"
        cell_numbers = []
        cell_values = []
        temp_values = []

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
            if topic.startswith(temp_prefix):
                try:
                    temp_f = _to_float(value)
                    if temp_f is not None:
                        temp_values.append(temp_f)
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

        voltage = messages.get(f"{pfx}/v_pack", "Unknown")
        current = messages.get(f"{pfx}/i_pack", "Unknown")
        soc = messages.get(f"{pfx}/soc", "Unknown")
        soh = messages.get(f"{pfx}/soh", "Unknown")
        cycles = messages.get(f"{pfx}/cycles", "Unknown")
        delta = messages.get(f"{pfx}/cells_max_diff_calc", "Unknown")
        remaining_capacity_ah = messages.get(f"{pfx}/i_remain_cap", "Unknown")
        full_capacity_ah = messages.get(f"{pfx}/i_full_cap", "Unknown")
        design_capacity_ah = messages.get(f"{pfx}/i_design_cap", "Unknown")

        refs = effective_warning_references(options, cell_count)
        cell_high_ref = refs["cell_high"]
        cell_low_ref = refs["cell_low"]

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
            bms_cell_warning_labels = _warning_cell_label_map(warnings, high_num, low_num)

            for cell_num, cell_v in sorted(cell_values, key=lambda item: item[0]):
                labels = []
                if cell_num == high_num:
                    labels.append("Highest")
                if cell_num == low_num:
                    labels.append("Lowest")
                labels.extend(bms_cell_warning_labels.get(cell_num, []))
                if cell_v > cell_high_ref:
                    labels.append("Above high reference")
                if cell_v < cell_low_ref:
                    labels.append("Below low reference")

            has_reference_label = any("reference" in label for label in labels)
            has_bms_label = any(label.startswith("BMS ") for label in labels)
            detailed_cells.append({
                "number": f"{cell_num:02d}",
                "voltage": f"{cell_v:.3f}",
                "labels": labels,
                "class": "cell-alert" if has_reference_label else ("cell-caution" if has_bms_label else ("cell-highlow" if labels else "cell-normal")),
            })

        pack_v = _to_float(voltage)
        pack_current = _to_float(current)
        pack_power_kw = None
        if pack_v is not None and pack_current is not None:
            pack_power_kw = (pack_v * pack_current) / 1000.0
        pack_high_ref = refs["pack_high"]
        pack_low_ref = refs["pack_low"]

        high_cell_exceeded = bool(highest_cell_v is not None and highest_cell_v > cell_high_ref)
        low_cell_exceeded = bool(lowest_cell_v is not None and lowest_cell_v < cell_low_ref)
        high_pack_exceeded = bool(pack_v is not None and pack_high_ref is not None and pack_v > pack_high_ref)
        low_pack_exceeded = bool(pack_v is not None and pack_low_ref is not None and pack_v < pack_low_ref)
        references_exceeded = high_cell_exceeded or low_cell_exceeded or high_pack_exceeded or low_pack_exceeded

        if has_warning and severity_class not in ("critical", "offline", "stale"):
            if references_exceeded:
                severity_class, severity_label = "critical", "Critical"
            elif "above cell volt" in warnings.lower() or "above total volt" in warnings.lower():
                severity_class, severity_label = "caution", "Caution"

        severity_summary[severity_label] = severity_summary.get(severity_label, 0) + 1

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

        try:
            pack_number = int(pack_id)
        except (TypeError, ValueError):
            pack_number = 0
        is_master = pack_number == 1
        pack_serial = clean_bms_serial(result.get("pack_sn", "Unknown"))
        bms_serial = clean_bms_serial(result.get("bms_sn", "Unknown"))
        serial_display = pack_serial if is_master and pack_serial != "Unknown" else bms_serial if is_master else "N/A"
        serial_note = "Reported by BMS" if is_master and serial_display != "Unknown" else "Current BMS read does not expose a separate serial for this pack"

        pack_data = {
            "id": pack_id,
            "role": "Master" if is_master else "Slave",
            "serial": serial_display,
            "serial_note": serial_note,
            "cell_count": cell_count,
            "soc": soc,
            "soh": soh,
            "cycles": cycles,
            "remaining_capacity_ah": remaining_capacity_ah,
            "full_capacity_ah": full_capacity_ah,
            "design_capacity_ah": design_capacity_ah,
            "voltage": voltage,
            "current": current,
            "power_kw": f"{pack_power_kw:.2f}" if pack_power_kw is not None else "Unknown",
            "delta": delta,
            "temperatures": sorted(temp_values),
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
            "battery_profile": refs["profile_label"],
            "reference_source": _reference_source_label(refs),
            "reference_checks": reference_checks,
            "charge_fet": messages.get(f"{pfx}/charge_fet", "Unknown"),
            "discharge_fet": messages.get(f"{pfx}/discharge_fet", "Unknown"),
            "fully": messages.get(f"{pfx}/fully", "Unknown"),
        }
        pack_data["warning_intelligence"] = build_warning_intelligence(
            pack_data,
            warnings,
            sorted(cell_values, key=lambda item: item[0]),
            pack_v,
            cell_high_ref,
            cell_low_ref,
            pack_high_ref,
            pack_low_ref,
            refs["profile_label"],
            _reference_source_label(refs),
            bool(options.get("notify_enabled", True) and options.get("notify_warnings", True)),
            _to_float(options.get("notify_cell_delta_warn_mv"), 100),
            {
                "notify_alert_cell_high_voltage": bool(options.get("notify_alert_cell_high_voltage", True)),
                "notify_alert_cell_low_voltage": bool(options.get("notify_alert_cell_low_voltage", True)),
                "notify_alert_cell_delta": bool(options.get("notify_alert_cell_delta", True)),
                "notify_alert_pack_high_voltage": bool(options.get("notify_alert_pack_high_voltage", True)),
                "notify_alert_pack_low_voltage": bool(options.get("notify_alert_pack_low_voltage", True)),
            },
            options.get("notify_bms_warning_policy", "user_reference_or_critical"),
        )
        packs.append(pack_data)

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

    _apply_overall_warning_status(result)

    if not messages and not result["error"]:
        result["error"] = "No retained MQTT values were received. Check mqtt_retain_state and MQTT connection."

    return result


def fetch_monitor_live_snapshot(options):
    """Read the monitor-owned live serial snapshot without touching the BMS."""
    snapshot = load_live_snapshot(LIVE_SNAPSHOT_PATH)
    if not isinstance(snapshot, dict):
        return {
            "ok": False,
            "error": "No live serial snapshot has been written yet.",
            "source": "live_serial",
            "data_source": "Live serial",
            "packs": [],
            "pack_count": 0,
            "total_cells": 0,
            "warning_count": 0,
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    updated_at = _to_float(snapshot.get("updated_at_epoch"))
    if updated_at is not None:
        age = max(0, int(time.time() - updated_at))
        snapshot["snapshot_age_seconds"] = age
        stale_limit = int(_to_float(options.get("notify_stale_data_seconds"), 120) or 120)
        if age > stale_limit:
            snapshot["stale"] = "ON"
            snapshot["stale_reason"] = f"Live serial snapshot age {age}s exceeds {stale_limit}s"
            snapshot["data_source"] = "Stale live serial"

    snapshot.setdefault("source", "live_serial")
    snapshot.setdefault("data_source", "Live serial")
    snapshot.setdefault("error", "")
    return snapshot


def live_snapshot_options_key(options):
    """Build a non-secret key for values that change the live snapshot view."""
    keys = (
        "ui_data_source",
        "mqtt_enabled",
        "mqtt_host",
        "mqtt_port",
        "mqtt_base_topic",
        "notify_cell_high_warn_voltage",
        "notify_cell_low_warn_voltage",
        "notify_cell_delta_threshold_mv",
        "notify_pack_high_voltage",
        "notify_pack_low_voltage",
    )
    return tuple((key, str(options.get(key, ""))) for key in keys)


def clone_live_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        return None
    return json.loads(json.dumps(snapshot))


def clear_live_snapshot_cache():
    with _LIVE_SNAPSHOT_LOCK:
        _LIVE_SNAPSHOT_CACHE["options_key"] = None
        _LIVE_SNAPSHOT_CACHE["snapshot"] = None
        _LIVE_SNAPSHOT_CACHE["updated_at"] = 0.0
        _LIVE_SNAPSHOT_CACHE["error"] = ""


def update_live_snapshot_cache(options, snapshot, error=""):
    if not options or not isinstance(snapshot, dict):
        return
    with _LIVE_SNAPSHOT_LOCK:
        _LIVE_SNAPSHOT_CACHE["options_key"] = live_snapshot_options_key(options)
        _LIVE_SNAPSHOT_CACHE["snapshot"] = clone_live_snapshot(snapshot)
        _LIVE_SNAPSHOT_CACHE["updated_at"] = time.time()
        _LIVE_SNAPSHOT_CACHE["error"] = str(error or snapshot.get("error", ""))


def get_cached_live_snapshot(options, max_age_seconds=LIVE_SNAPSHOT_MAX_AGE_SECONDS):
    if not options:
        return None
    with _LIVE_SNAPSHOT_LOCK:
        if _LIVE_SNAPSHOT_CACHE["options_key"] != live_snapshot_options_key(options):
            return None
        snapshot = _LIVE_SNAPSHOT_CACHE["snapshot"]
        updated_at = float(_LIVE_SNAPSHOT_CACHE["updated_at"] or 0.0)

    if not snapshot:
        return None
    if max_age_seconds is not None and time.time() - updated_at > max_age_seconds:
        return None
    return clone_live_snapshot(snapshot)


def refresh_live_snapshot_cache_once(options):
    mode = str(options.get("ui_data_source", DEFAULT_OPTION_VALUES["ui_data_source"]) or DEFAULT_OPTION_VALUES["ui_data_source"])
    snapshot = None
    if mode in ("auto", "monitor_live"):
        snapshot = fetch_monitor_live_snapshot(options)
        if mode == "monitor_live" or snapshot.get("ok"):
            update_live_snapshot_cache(options, snapshot)
            return snapshot

    if mode in ("auto", "mqtt_retained") and bool(options.get("mqtt_enabled", DEFAULT_OPTION_VALUES["mqtt_enabled"])):
        snapshot = fetch_mqtt_snapshot(options)
    elif snapshot is None:
        snapshot = {
            "ok": False,
            "error": "No enabled live data source is available.",
            "source": mode,
            "data_source": "No data",
            "packs": [],
            "pack_count": 0,
            "total_cells": 0,
            "warning_count": 0,
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    update_live_snapshot_cache(options, snapshot)
    return snapshot


def live_snapshot_cache_worker():
    while True:
        try:
            options, error = load_options()
            if options and not error:
                refresh_live_snapshot_cache_once(options)
        except Exception as exc:
            with _LIVE_SNAPSHOT_LOCK:
                _LIVE_SNAPSHOT_CACHE["error"] = str(exc)
        time.sleep(LIVE_SNAPSHOT_REFRESH_SECONDS)


def ensure_live_snapshot_cache_worker():
    global _LIVE_SNAPSHOT_WORKER_STARTED
    with _LIVE_SNAPSHOT_LOCK:
        if _LIVE_SNAPSHOT_WORKER_STARTED:
            return
        _LIVE_SNAPSHOT_WORKER_STARTED = True

    thread = threading.Thread(
        target=live_snapshot_cache_worker,
        name="pacebms-live-snapshot-cache",
        daemon=True,
    )
    thread.start()


def get_page_live_snapshot(options):
    """Return live serial data first, then retained MQTT fallback when configured."""
    cached = get_cached_live_snapshot(options)
    if cached is not None:
        return cached
    return refresh_live_snapshot_cache_once(options)


def input_type_for_value(key, value):
    if key in ("battery_profile", "notify_bms_warning_policy", "debug_output", "bms_connection_mode", "connection_type", "ui_data_source"):
        return "select"
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
    cycle_values = []
    soh_values = []
    soc_values = []
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
            serial_display = "N/A"
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
            "cycles": pack.get("cycles", "Unknown"),
            "voltage": pack.get("voltage", "Unknown"),
            "current": pack.get("current", "Unknown"),
            "delta": pack.get("delta", "Unknown"),
            "status": status,
            "warnings": warnings,
        })
        cycles = _to_float(pack.get("cycles"))
        soh = _to_float(pack.get("soh"))
        soc = _to_float(pack.get("soc"))
        if cycles is not None:
            cycle_values.append(int(cycles))
        if soh is not None:
            soh_values.append(soh)
        if soc is not None:
            soc_values.append(soc)

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
        "max_cycles": max(cycle_values) if cycle_values else "Unknown",
        "min_soh": f"{min(soh_values):.1f}%" if soh_values else "Unknown",
        "avg_soc": f"{(sum(soc_values) / len(soc_values)):.1f}%" if soc_values else "Unknown",
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
        live = attach_monitoring_health(options, fetch_mqtt_snapshot(options))
    elif isinstance(live, dict) and "monitoring_health" not in live:
        live = attach_monitoring_health(options, live)

    live = live or {}

    telegram_configured = (
        telegram_value_configured(options.get("telegram_bot_token"))
        and telegram_value_configured(options.get("telegram_chat_id"))
    )
    mqtt_configured = bool(options.get("mqtt_host"))
    discovery_enabled = bool(options.get("mqtt_ha_discovery", False))

    stale_state = str(live.get("stale", "Unknown")).upper()
    availability = str(live.get("availability", "Unknown")).lower()
    monitor_state = str(live.get("monitor_state", "Unknown")).lower()
    warning_count = int(live.get("warning_count", 0) or 0)
    highest_warning, highest_warning_class = _highest_pack_warning(live.get("packs") or [])

    live_ok = bool(live.get("ok"))
    data_source = live.get("data_source") or ("Live serial" if str(live.get("source", "")) == "live_serial" else "Live data")
    bms_fresh = stale_state == "OFF" and live.get("last_analog_read", "Unknown") not in ("Unknown", "Not available")
    monitor_ok = availability == "online" and monitor_state == "running"

    health_cards = [
        {
            "title": "Live Data",
            "status": "OK" if live_ok else "Check",
            "class": "healthy" if live_ok else "warning",
            "detail": f"{data_source} values were received." if live_ok else live.get("error", "No live data values received."),
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
            "status": highest_warning or ("Active" if warning_count else "Normal"),
            "class": (highest_warning_class or "warning") if warning_count else "healthy",
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

    expected_cells = int(_to_float(options.get("expected_cell_count"), 0) or 0)
    expected_packs = int(_to_float(options.get("expected_pack_count"), 0) or 0)
    detected_cells = int(_to_float(live.get("total_cells"), 0) or 0)
    detected_packs = int(_to_float(live.get("pack_count"), 0) or 0)
    layout_notes = []
    if expected_packs:
        layout_notes.append(f"Expected packs: {expected_packs}; detected: {detected_packs or 'Unknown'}")
    if expected_cells:
        layout_notes.append(f"Expected total cells: {expected_cells}; detected: {detected_cells or 'Unknown'}")
    if options.get("capacity_fallback_enabled"):
        layout_notes.append(f"Capacity fallback: {options.get('capacity_per_pack_ah', 0)} Ah per pack when BMS capacity is unavailable")
    if layout_notes:
        health_cards.insert(3, {
            "title": "Layout Checks",
            "status": "Configured",
            "class": "healthy",
            "detail": " | ".join(layout_notes),
        })

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
        "history_status": build_history_status(options),
    }


def format_bytes(size):
    try:
        size = float(size)
    except Exception:
        return "Unknown"
    units = ["B", "KB", "MB", "GB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


def build_history_status(options):
    """Return lightweight SQLite history health for diagnostics and support."""
    enabled = bool(options.get("metrics_enabled", True)) if options else True
    raw_retention = options.get("history_retention_days", 90) if options else 90
    event_retention = options.get("history_event_retention_days", 365) if options else 365
    status = {
        "enabled": "ON" if enabled else "OFF",
        "class": "healthy" if enabled else "off",
        "db_path": str(HISTORY_DB_PATH),
        "db_size": "No data",
        "wal_size": "No data",
        "latest_sample": "No data",
        "retention": f"Raw {raw_retention} days | Events {event_retention} days",
        "rows": {
            "bank": 0,
            "pack": 0,
            "cell": 0,
            "temperature": 0,
            "warnings": 0,
            "system": 0,
        },
        "error": "",
    }
    if not enabled:
        return status

    try:
        init_history_db(HISTORY_DB_PATH)
        db_size = HISTORY_DB_PATH.stat().st_size if HISTORY_DB_PATH.exists() else 0
        wal_path = Path(str(HISTORY_DB_PATH) + "-wal")
        wal_size = wal_path.stat().st_size if wal_path.exists() else 0
        status["db_size"] = format_bytes(db_size)
        status["wal_size"] = format_bytes(wal_size)
        table_map = {
            "bank": "bank_metrics",
            "pack": "pack_metrics",
            "cell": "cell_metrics",
            "temperature": "temperature_metrics",
            "warnings": "warning_events",
            "system": "system_events",
        }
        latest_ts = None
        conn = sqlite3.connect(HISTORY_DB_PATH, timeout=2)
        try:
            for label, table in table_map.items():
                status["rows"][label] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                table_latest = conn.execute(f"SELECT MAX(ts) FROM {table}").fetchone()[0]
                if table_latest is not None:
                    latest_ts = max(latest_ts or 0, int(table_latest))
        finally:
            conn.close()
        if latest_ts:
            status["latest_sample"] = datetime.fromtimestamp(latest_ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as exc:
        status["class"] = "warning"
        status["error"] = str(exc)
    return status


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
    "BMS Connection": "Physical BMS connection settings. Serial is the supported read-only BMS interface in this build. Use a stable /dev/serial/by-id path where possible, keep the Pace baud rate at 9600 unless the BMS requires otherwise, and set the poll interval for serial reads. These settings affect monitor runtime after restart and never write to the BMS.",
    "Advanced": "Advanced runtime settings. Keep pack and cell number padding stable after Home Assistant MQTT Discovery has created entities. Changing padding changes MQTT state topics, discovery topics and unique IDs, which can leave old retained discovery entities in Home Assistant until they are cleaned up.",
    "History & Live Data": "Controls where the web UI reads display data from and whether local SQLite history is stored. This does not change how the BMS is polled. Live serial data reads the monitor-owned snapshot; fallback mode uses MQTT only if live serial data is unavailable and MQTT is enabled. History settings store local metrics for charts and never write to the BMS.",
    "MQTT": "Optional MQTT publishing and Home Assistant discovery settings. MQTT can be disabled for direct serial web monitoring. When enabled, the broker, credentials, base topic, discovery topic, retain setting and force-republish intervals control outbound MQTT only. These settings do not write to the BMS.",
    "Telegram": "Direct Telegram notification settings. Enable or disable Telegram, configure bot token and chat ID, and choose startup, disconnect, stale-data and recovery messages. Blank sensitive fields in the Config form keep the existing saved value. Telegram settings never write to the BMS.",
    "Notifications": "Notification category switches for SOC, SOH and BMS warning alerts. These toggles decide which detected conditions can notify. Threshold numbers and repeat intervals are configured in Notification Thresholds, while detailed BMS warning context is configured in Warning Detail and Battery Profile & Alert References.",
    "Battery Profile & References": "Shows measured battery values beside profile/default references and user-configured references. This card also contains read-only expected layout checks and capacity fallback settings used only when BMS capacity is unavailable. The BMS warning Telegram policy and row alert switches control Telegram noise only; active BMS warnings remain visible in the UI. The editable values are Home Assistant add-on options only and never write to the BMS.",
    "FET Notifications": "Controls charge/discharge FET notification behavior. These settings only decide when to alert; they do not control FETs.",
    "Notification Thresholds": "Controls SOC, SOH, stale-data and BMS warning repeat timing. notify_soc_low_thresholds must use comma-separated numbers only, for example 50,25,10. Do not use percentage signs. SOC high and SOH thresholds use single percentage numbers. Stale and warning repeat values are in seconds. BMS warning repeats are severity-aware: caution repeats for low-risk ongoing warnings, warning repeats for near-limit conditions, and critical repeats for protection/fault or measured values outside configured references.",
    "Warning Detail": "Controls the extra context included in BMS warning explanations, such as highest/lowest cell, pack voltage and SOC/SOH. These settings only affect Telegram/UI message detail and never write to the BMS.",
    "Scheduled Reports": "Controls scheduled Telegram reports, daily summary timing, energy deadband and cell delta report window. These settings do not write to the BMS.",
}

FIELD_HELP = {
    "bms_connection_mode": "Physical BMS connection mode. Serial is the only supported read-only BMS interface in this build.",
    "ui_data_source": "Controls where the web UI reads display data from. It does not change how the BMS is polled. Live serial data uses the monitor-owned snapshot; fallback mode uses retained MQTT only if live serial data is unavailable and MQTT is enabled.",
    "mqtt_enabled": "Enables MQTT publishing and Home Assistant discovery. Disable this when using the app as a direct serial web monitor without MQTT.",
    "metrics_enabled": "Enables local SQLite history for charts and troubleshooting. This stores displayed battery values under /data.",
    "history_sample_seconds": "Pack and bank metric sample interval for history storage. Default: 10 seconds.",
    "history_cell_sample_seconds": "Cell and temperature metric sample interval for history storage. Default: 30 seconds.",
    "history_retention_days": "Raw metric history retention. Default: 90 days.",
    "history_event_retention_days": "Event/history retention for warning and system events. Default: 365 days.",
    "notify_warning_repeat_seconds": "Repeat interval in seconds for the same active BMS warning Telegram notification. Example: 1800 means repeat at most every 30 minutes.",
    "notify_warning_repeat_caution_seconds": "Repeat interval for ongoing caution-level BMS warnings. Recommended: 21600 seconds (6 hours).",
    "notify_warning_repeat_warning_seconds": "Repeat interval for ongoing warning-level BMS warnings. Recommended: 3600 seconds (1 hour).",
    "notify_warning_repeat_critical_seconds": "Repeat interval for ongoing critical BMS warnings. Recommended: 1800 seconds (30 minutes).",
    "notify_warning_clear_confirm_reads": "Number of consecutive normal warning reads required before the app sends a warning-cleared message and allows the same warning to alert again. This reduces clear/re-alert flicker.",
    "battery_profile": "Read-only reference profile used for warning context. Profile defaults apply until you edit the user-defined voltage, delta or temperature reference fields.",
    "notify_bms_warning_policy": "Controls when BMS warning Telegram messages are sent: all warnings, user reference exceeded plus critical/protection, or user reference exceeded only.",
    "notify_alert_cell_high_voltage": "Enables Telegram alerts for high-cell-voltage reference crossings.",
    "notify_alert_cell_low_voltage": "Enables Telegram alerts for low-cell-voltage reference crossings.",
    "notify_alert_cell_delta": "Enables Telegram alerts/reports for cell-delta reference crossings.",
    "notify_alert_pack_high_voltage": "Enables Telegram alerts for pack high-voltage reference crossings.",
    "notify_alert_pack_low_voltage": "Enables Telegram alerts for pack low-voltage reference crossings.",
    "notify_alert_temp_high": "Enables Telegram alerts for high-temperature reference crossings.",
    "notify_alert_temp_low": "Enables Telegram alerts for low-temperature reference crossings.",
    "notify_soc_low_thresholds": "Comma-separated SOC low alert thresholds. Use numbers only, no percent signs. Example: 50,25,10.",
    "notify_soc_high_threshold": "Single SOC high alert threshold. Example: 98 means alert when SOC is at or above 98%.",
    "notify_soc_high_reset": "High SOC reset point. Example: 95 means the high SOC alert can trigger again after SOC drops below 95%.",
    "notify_soh_threshold": "Single SOH threshold. Example: 95 means alert when SOH is below 95%.",
    "notify_retry_count": "Whole number retry count for supported notifications. Example: 1.",
    "notify_stale_data_seconds": "Seconds without fresh BMS data before stale-data notification logic triggers. Example: 120.",
    "notify_stale_data_repeat_seconds": "Repeat interval in seconds while stale data remains active. Example: 1800.",
    "notify_ignore_charge_fet_off_when_full": "When enabled, Charge FET OFF can be ignored if the pack is full. This helps avoid unnecessary alerts when the BMS disables charging at full SOC.",
    "notify_alert_discharge_fet_off": "When enabled, send an alert if the Discharge FET is OFF.",
    "notify_fet_repeat_seconds": "Minimum seconds before the same FET OFF alert can be sent again after a noisy ON/OFF flicker. Recommended: 3600 seconds.",
    "notify_daily_summary_time": "Daily summary notification time. Use HH:MM 24-hour format. Example: 19:00.",
    "daily_energy_current_deadband_a": "Current below this value is ignored for daily charged/discharged kWh. Example: 0.2 ignores tiny zero-current noise.",
    "notify_delta_report_time": "Cell delta report notification time. Use HH:MM 24-hour format. Example: 10:15.",
    "notify_delta_window_start": "Start of the delta report calculation window. Use HH:MM 24-hour format. Example: 00:00.",
    "notify_delta_window_end": "End of the delta report calculation window. Use HH:MM 24-hour format. Example: 10:00.",
    "expected_cell_count": "Optional expected total cell count across all packs. Use 0 for auto/detected. This only warns when detected layout differs; it does not force parsing.",
    "expected_pack_count": "Optional expected pack count. Use 0 for auto/detected. This only warns when detected layout differs; it does not force parsing.",
    "capacity_fallback_enabled": "Use configured capacity only when BMS capacity is missing or invalid. Valid BMS-reported capacity always wins.",
    "capacity_per_pack_ah": "Fallback capacity per pack in Ah for runtime/charge estimates when BMS capacity is unavailable. Use 0 to disable.",
}

FIELD_LABELS = {
    "bms_connection_mode": "BMS connection mode",
    "connection_type": "Connection type",
    "bms_serial": "Serial device",
    "bms_baudrate": "BMS baud rate",
    "scan_interval": "Poll interval",
    "ui_data_source": "Web UI display source",
    "metrics_enabled": "Store local history",
    "history_sample_seconds": "Pack/bank history sample interval",
    "history_cell_sample_seconds": "Cell history sample interval",
    "history_retention_days": "Raw history retention",
    "history_event_retention_days": "Event history retention",
    "mqtt_enabled": "Enable MQTT publishing",
    "mqtt_host": "MQTT broker host",
    "mqtt_port": "MQTT broker port",
    "mqtt_user": "MQTT username",
    "mqtt_password": "MQTT password",
    "mqtt_base_topic": "MQTT base topic",
    "mqtt_ha_discovery": "Home Assistant discovery",
    "mqtt_ha_discovery_topic": "Discovery topic",
    "mqtt_retain_state": "Retain MQTT state",
    "state_force_republish_seconds": "State republish interval",
    "warn_force_republish_seconds": "Warning republish interval",
    "debug_output": "Log detail level",
    "zero_pad_number_cells": "Cell number padding (entity-sensitive)",
    "zero_pad_number_packs": "Pack number padding (entity-sensitive)",
    "expected_cell_count": "Expected total cells",
    "expected_pack_count": "Expected pack count",
    "capacity_fallback_enabled": "Use capacity fallback when BMS capacity is missing",
    "capacity_per_pack_ah": "Fallback capacity per pack",
    "notify_enabled": "Enable Telegram notifications",
    "telegram_bot_token": "Telegram bot token",
    "telegram_chat_id": "Telegram chat ID",
    "notify_startup": "Startup/shutdown messages",
    "notify_disconnect": "BMS disconnect alerts",
    "notify_stale_data": "Stale data alerts",
    "notify_stale_recovery": "Stale data recovery alerts",
    "notify_soc_low": "Low SOC alerts",
    "notify_soc_high": "High SOC alerts",
    "notify_soc_high_on_startup": "High SOC startup alert",
    "notify_soh": "Low SOH alerts",
    "notify_soh_on_startup": "Low SOH startup alert",
    "notify_warnings": "BMS warning alerts",
    "notify_fet": "FET state alerts",
    "notify_ignore_charge_fet_off_when_full": "Ignore Charge FET OFF when full",
    "notify_alert_discharge_fet_off": "Discharge FET OFF alert",
    "notify_fet_repeat_seconds": "FET alert repeat interval",
    "notify_soc_low_thresholds": "Low SOC thresholds",
    "notify_soc_high_threshold": "High SOC threshold",
    "notify_soc_high_reset": "High SOC reset point",
    "notify_soh_threshold": "SOH alert threshold",
    "notify_retry_count": "Telegram retry count",
    "notify_stale_data_seconds": "Stale data threshold",
    "notify_stale_data_repeat_seconds": "Stale alert repeat interval",
    "notify_warning_repeat_seconds": "Default warning repeat interval",
    "notify_warning_repeat_caution_seconds": "Caution repeat interval",
    "notify_warning_repeat_warning_seconds": "Warning repeat interval",
    "notify_warning_repeat_critical_seconds": "Critical repeat interval",
    "notify_warning_clear_confirm_reads": "Warning clear confirmation reads",
    "notify_warning_detail_enabled": "Detailed warning messages",
    "notify_include_highest_and_lowest_cell": "Include highest/lowest cells",
    "notify_include_pack_voltage": "Include pack voltage",
    "notify_include_soc_soh": "Include SOC and SOH",
    "notify_daily_summary": "Daily summary report",
    "notify_daily_summary_time": "Daily summary time",
    "notify_delta_report": "Cell delta report",
    "notify_delta_report_time": "Cell delta report time",
    "notify_delta_window_start": "Delta report window start",
    "notify_delta_window_end": "Delta report window end",
    "daily_energy_current_deadband_a": "Energy current deadband",
    "battery_profile": "Battery profile",
    "notify_bms_warning_policy": "BMS warning Telegram policy",
    "notify_cell_high_warn_voltage": "High cell voltage reference",
    "notify_cell_low_warn_voltage": "Low cell voltage reference",
    "notify_cell_delta_warn_mv": "Cell delta reference",
    "notify_temp_high_warn_c": "High temperature reference",
    "notify_temp_low_warn_c": "Low temperature reference",
    "notify_alert_cell_high_voltage": "Telegram alert for high cell voltage",
    "notify_alert_cell_low_voltage": "Telegram alert for low cell voltage",
    "notify_alert_cell_delta": "Telegram alert for cell delta",
    "notify_alert_pack_high_voltage": "Telegram alert for high pack voltage",
    "notify_alert_pack_low_voltage": "Telegram alert for low pack voltage",
    "notify_alert_temp_high": "Telegram alert for high temperature",
    "notify_alert_temp_low": "Telegram alert for low temperature",
    "notify_include_all_cells_above_threshold": "List all cells above high reference",
    "notify_include_all_cells_below_threshold": "List all cells below low reference",
}


def field_label(key):
    return FIELD_LABELS.get(key, str(key).replace("_", " ").strip().title())


def build_grouped_config(options):
    grouped = {}
    for group_name, keys in GROUPS.items():
        grouped[group_name] = []
        for key in keys:
            raw_value = options.get(key, DEFAULT_OPTION_VALUES.get(key, ""))
            grouped[group_name].append({
                "key": key,
                "label": field_label(key),
                "raw_value": raw_value,
                "input_type": input_type_for_value(key, raw_value),
                "choices": (
                    BATTERY_PROFILE_CHOICES if key == "battery_profile"
                    else WARNING_TELEGRAM_POLICY_CHOICES if key == "notify_bms_warning_policy"
                    else DEBUG_OUTPUT_CHOICES if key == "debug_output"
                    else BMS_CONNECTION_MODE_CHOICES if key in ("bms_connection_mode", "connection_type")
                    else UI_DATA_SOURCE_CHOICES if key == "ui_data_source"
                    else {}
                ),
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
            value = sanitize_config_value(key, options.get(key, DEFAULT_OPTION_VALUES.get(key, "")))
            lines.append(f"{key}: {yaml_scalar(value)}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def parse_form_value(key, raw_value, current_value):
    """Parse web form values back to the expected option type."""
    if key in ("bms_connection_mode", "connection_type"):
        return "Serial"
    if key == "ui_data_source":
        value = str(raw_value or DEFAULT_OPTION_VALUES["ui_data_source"]).strip()
        return value if value in UI_DATA_SOURCE_CHOICES else DEFAULT_OPTION_VALUES["ui_data_source"]
    if key == "battery_profile":
        return normalize_profile(raw_value)
    if key == "notify_bms_warning_policy":
        policy = str(raw_value or DEFAULT_OPTION_VALUES["notify_bms_warning_policy"]).strip()
        return policy if policy in WARNING_TELEGRAM_POLICY_CHOICES else DEFAULT_OPTION_VALUES["notify_bms_warning_policy"]
    if key == "debug_output":
        try:
            parsed = int(str(raw_value).strip())
        except Exception:
            return DEFAULT_OPTION_VALUES["debug_output"]
        return parsed if parsed in DEBUG_OUTPUT_CHOICES else DEFAULT_OPTION_VALUES["debug_output"]

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
            return float(normalize_decimal_text(raw_value))
        except Exception:
            return current_value

    return "" if raw_value is None else str(raw_value)


def build_options_from_form(form, current_options):
    """Build a new options dictionary from the Config tab form."""
    new_options = dict(current_options)

    for group_name, keys in GROUPS.items():
        for key in keys:
            current_value = current_options.get(key, DEFAULT_OPTION_VALUES.get(key, ""))

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
            return float(normalize_decimal_text(options.get(key, default)))
        except Exception:
            return default

    mqtt_enabled = bool(options.get("mqtt_enabled", DEFAULT_OPTION_VALUES["mqtt_enabled"]))
    mqtt_host = str(options.get("mqtt_host", "")).strip()
    mqtt_port = as_int("mqtt_port")
    if mqtt_enabled:
        if not mqtt_host:
            errors.append("mqtt_host cannot be blank when MQTT is enabled.")
        if mqtt_port is None or mqtt_port < 1 or mqtt_port > 65535:
            errors.append("mqtt_port must be between 1 and 65535 when MQTT is enabled.")
    elif mqtt_port is not None and (mqtt_port < 1 or mqtt_port > 65535):
        errors.append("mqtt_port must be between 1 and 65535 when provided.")

    bms_connection_mode = str(options.get("bms_connection_mode", "Serial")).strip().lower()
    if bms_connection_mode != "serial":
        errors.append("bms_connection_mode must be Serial.")

    connection_type = str(options.get("connection_type", "")).strip().lower()
    if connection_type != "serial":
        errors.append("connection_type must be Serial. IP/TCP fields were removed from this add-on config.")
    elif not str(options.get("bms_serial", "")).strip():
        errors.append("bms_serial cannot be blank when connection_type is Serial.")

    scan_interval = as_float("scan_interval")
    if scan_interval is None or scan_interval < 1:
        errors.append("scan_interval must be at least 1 second.")

    ui_data_source = str(options.get("ui_data_source", DEFAULT_OPTION_VALUES["ui_data_source"])).strip()
    if ui_data_source not in UI_DATA_SOURCE_CHOICES:
        errors.append("ui_data_source must be one of: auto, monitor_live, mqtt_retained.")

    history_sample = as_int("history_sample_seconds")
    history_cell_sample = as_int("history_cell_sample_seconds")
    history_retention = as_int("history_retention_days")
    history_event_retention = as_int("history_event_retention_days")
    if history_sample is not None and history_sample < 1:
        errors.append("history_sample_seconds must be at least 1 second.")
    if history_cell_sample is not None and history_cell_sample < 1:
        errors.append("history_cell_sample_seconds must be at least 1 second.")
    if history_retention is not None and history_retention < 1:
        errors.append("history_retention_days must be at least 1 day.")
    if history_event_retention is not None and history_event_retention < 1:
        errors.append("history_event_retention_days must be at least 1 day.")

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

    for key in (
        "notify_warning_repeat_caution_seconds",
        "notify_warning_repeat_warning_seconds",
        "notify_warning_repeat_critical_seconds",
    ):
        value = as_int(key)
        if value is not None and value < 60:
            errors.append(f"{key} should be at least 60 seconds.")

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


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def configure_web_logging(options=None):
    options = options or {}
    debug_level = safe_int(options.get("debug_output", 0), 0)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] [web] %(message)s")
    root_logger = logging.getLogger()

    if not any(getattr(handler, "baseFilename", None) == WEB_LOG_PATH for handler in root_logger.handlers):
        try:
            handler = RotatingFileHandler(WEB_LOG_PATH, maxBytes=1_000_000, backupCount=3)
            handler.setFormatter(formatter)
            root_logger.addHandler(handler)
        except Exception:
            pass

    logging.getLogger("werkzeug").setLevel(logging.INFO if debug_level >= 3 else logging.WARNING)


def read_log_tail(path, limit=MAX_LOG_VIEW_LINES):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
    except FileNotFoundError:
        return []
    except Exception:
        return []
    return [line.rstrip("\n") for line in lines[-limit:] if line.strip()]


def classify_log_line(line, source):
    text = str(line or "")
    lowered = text.lower()
    category = "Monitor" if source == "monitor" else "Web UI"
    view_level = 1

    if "get /api/status" in lowered or "get /health" in lowered or "werkzeug" in lowered:
        return 3, "Web UI"
    if "[debug]" in lowered:
        if "duplicate suppressed" in lowered:
            return 2, "Warnings"
        if "raw" in lowered or "frame" in lowered or "checksum" in lowered or "unknown(0x" in lowered:
            return 3, "Protocol"
        return 2, category
    if "raw" in lowered or "frame" in lowered or "checksum" in lowered or "unknown(0x" in lowered:
        view_level = 3
        category = "Protocol"
    elif "analog read ok" in lowered or "warn read ok" in lowered:
        view_level = 2
        category = "Monitor"
    elif "telegram" in lowered:
        view_level = 0 if any(word in lowered for word in ("failed", "skipping", "not configured")) else 1
        category = "Telegram"
    elif "mqtt" in lowered:
        view_level = 0 if any(word in lowered for word in ("failed", "disconnected", "error")) else 1
        category = "MQTT"
    elif any(word in lowered for word in ("warning", "protect", "critical", "fault", "stale", "disconnect", "recovered")):
        view_level = 0
        category = "Warnings"
    elif "[error]" in lowered or "exception" in lowered or "traceback" in lowered:
        view_level = 0

    return view_level, category


def log_row_views(line, level, category):
    """Return the simplified log views this row should appear in."""
    lowered = str(line or "").lower()
    normalized_category = str(category or "")
    important = level <= 0

    if "telegram sent" in lowered:
        important = True
    if normalized_category == "MQTT" and any(word in lowered for word in ("connected", "disconnected", "failed", "error")):
        important = True
    if any(phrase in lowered for phrase in (
        "starting up",
        "startup notification",
        "monitor started",
        "monitor stopped",
        "shutdown",
        "warn read ok",
        "warnings=",
        "duplicate suppressed",
        "warning notification sent",
        "warning reminder sent",
        "warning cleared",
        "stale data",
        "data recovered",
    )):
        important = True

    battery_reads = important or any(phrase in lowered for phrase in (
        "analog read ok",
        "warn read ok",
        "pack_",
        "charge_fet",
        "discharge_fet",
    ))

    return {
        "important": important,
        "battery": battery_reads,
        "everything": True,
    }


def parse_log_time(line):
    text = str(line or "")
    match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d{3})?", text)
    if match:
        return match.group(0)

    access_match = re.search(r"\[(\d{1,2})/([A-Za-z]{3})/(\d{4})\s+(\d{2}:\d{2}:\d{2})", text)
    if access_match:
        day, month_name, year, clock = access_match.groups()
        month_map = {
            "jan": "01", "feb": "02", "mar": "03", "apr": "04",
            "may": "05", "jun": "06", "jul": "07", "aug": "08",
            "sep": "09", "oct": "10", "nov": "11", "dec": "12",
        }
        month = month_map.get(month_name.lower())
        if month:
            return f"{year}-{month}-{int(day):02d} {clock}"
    return ""


def clean_log_message(line):
    text = str(line or "").strip()
    text = re.sub(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d{3})?\s+", "", text)
    return text


def build_log_view(options):
    rows = []
    for source, path in (("monitor", MONITOR_LOG_PATH), ("web", WEB_LOG_PATH)):
        for index, line in enumerate(read_log_tail(path)):
            level, category = classify_log_line(line, source)
            time_text = parse_log_time(line)
            views = log_row_views(line, level, category)
            rows.append({
                "source": "Monitor" if source == "monitor" else "Web UI",
                "time": time_text,
                "level": level,
                "level_label": f"Debug {level}",
                "category": category,
                "important": views["important"],
                "battery": views["battery"],
                "everything": views["everything"],
                "message": clean_log_message(line),
                "sort_key": f"{time_text}-{source}-{index:04d}",
            })

    rows.sort(key=lambda row: row["sort_key"], reverse=True)
    rows = rows[:MAX_LOG_VIEW_LINES]
    debug_output = safe_int(options.get("debug_output", 0), 0) if options else 0
    default_view = "battery"
    visible_at_default = sum(1 for row in rows if row.get(default_view))
    counts_by_level = {level: sum(1 for row in rows if row["level"] <= level) for level in range(4)}
    counts_by_view = {
        "important": sum(1 for row in rows if row.get("important")),
        "battery": sum(1 for row in rows if row.get("battery")),
        "everything": len(rows),
    }
    row_times = [row["time"] for row in rows if row["time"]]
    return {
        "rows": rows,
        "debug_output": debug_output,
        "default_view": default_view,
        "visible_at_default": visible_at_default,
        "counts_by_level": counts_by_level,
        "counts_by_view": counts_by_view,
        "oldest_time": row_times[-1] if row_times else "Unknown",
        "newest_time": row_times[0] if row_times else "Unknown",
        "monitor_log_path": MONITOR_LOG_PATH,
        "web_log_path": WEB_LOG_PATH,
    }


def _fmt_reference_value(value, unit="", decimals=2):
    try:
        number = float(value)
    except Exception:
        return "Unknown"
    if decimals == 0:
        return f"{number:.0f}{unit}"
    return f"{number:.{decimals}f}{unit}"


def _reference_source_label(refs):
    if isinstance(refs, dict) and refs.get("source") == "user_configured":
        return "user-defined alert references"
    if isinstance(refs, dict) and refs.get("source") == "profile":
        return "battery profile defaults"
    return "user custom settings"


def build_battery_reference_table(options, live):
    """Build the Config-tab profile/reference table.

    This is a display/form helper only. It does not write to the BMS.
    """
    options = options or {}
    live = live or {}
    packs = live.get("packs") or []
    cell_counts = []
    highest_cells = []
    lowest_cells = []
    deltas = []
    temps = []
    pack_voltages = []

    for pack in packs:
        try:
            cell_counts.append(int(pack.get("cell_count") or 0))
        except Exception:
            pass
        high_v = _to_float((pack.get("highest_cell") or {}).get("voltage"))
        low_v = _to_float((pack.get("lowest_cell") or {}).get("voltage"))
        delta_v = _to_float(pack.get("delta"))
        pack_v = _to_float(pack.get("voltage"))
        if high_v is not None:
            highest_cells.append(high_v)
        if low_v is not None:
            lowest_cells.append(low_v)
        if delta_v is not None:
            deltas.append(delta_v)
        if pack_v is not None:
            pack_voltages.append(pack_v)
        for temp in pack.get("temperatures", []) or []:
            temp_v = _to_float(temp)
            if temp_v is not None:
                temps.append(temp_v)

    detected_cell_count = max(cell_counts) if cell_counts else None
    refs = effective_warning_references(options, detected_cell_count)
    selected = normalize_profile(options.get("battery_profile", "auto"))

    def opt(key, default=""):
        return options.get(key, DEFAULT_OPTION_VALUES.get(key, default))

    rows = [
        {
            "label": "High cell voltage",
            "key": "notify_cell_high_warn_voltage",
            "reference": _fmt_reference_value(refs.get("profile_cell_high"), " V", 2),
            "measured": _fmt_reference_value(max(highest_cells), " V", 3) if highest_cells else "Waiting for data",
            "user_key": "notify_cell_high_warn_voltage",
            "user_value": opt("notify_cell_high_warn_voltage", 4.20),
            "step": "0.01",
            "alert_key": "notify_alert_cell_high_voltage",
            "alert_value": bool(opt("notify_alert_cell_high_voltage", True)),
            "checkbox_key": "notify_include_all_cells_above_threshold",
            "checkbox_label": "Include all high cells",
            "checkbox_value": bool(opt("notify_include_all_cells_above_threshold", True)),
        },
        {
            "label": "Low cell voltage",
            "key": "notify_cell_low_warn_voltage",
            "reference": _fmt_reference_value(refs.get("profile_cell_low"), " V", 2),
            "measured": _fmt_reference_value(min(lowest_cells), " V", 3) if lowest_cells else "Waiting for data",
            "user_key": "notify_cell_low_warn_voltage",
            "user_value": opt("notify_cell_low_warn_voltage", 3.00),
            "step": "0.01",
            "alert_key": "notify_alert_cell_low_voltage",
            "alert_value": bool(opt("notify_alert_cell_low_voltage", True)),
            "checkbox_key": "notify_include_all_cells_below_threshold",
            "checkbox_label": "Include all low cells",
            "checkbox_value": bool(opt("notify_include_all_cells_below_threshold", True)),
        },
        {
            "label": "Cell delta",
            "key": "notify_cell_delta_warn_mv",
            "reference": _fmt_reference_value(refs.get("profile_delta_mv"), " mV", 0),
            "measured": _fmt_reference_value(max(deltas), " mV", 0) if deltas else "Waiting for data",
            "user_key": "notify_cell_delta_warn_mv",
            "user_value": opt("notify_cell_delta_warn_mv", 100),
            "step": "1",
            "alert_key": "notify_alert_cell_delta",
            "alert_value": bool(opt("notify_alert_cell_delta", True)),
            "checkbox_key": "notify_delta_report",
            "checkbox_label": "Delta report",
            "checkbox_value": bool(opt("notify_delta_report", True)),
        },
        {
            "label": "Pack high voltage",
            "key": "notify_pack_high_reference",
            "reference": _fmt_reference_value(refs.get("profile_pack_high"), " V", 2),
            "measured": _fmt_reference_value(max(pack_voltages), " V", 3) if pack_voltages else "Waiting for data",
            "user_key": None,
            "user_value": "Auto calculated",
            "step": None,
            "alert_key": "notify_alert_pack_high_voltage",
            "alert_value": bool(opt("notify_alert_pack_high_voltage", True)),
            "checkbox_key": "notify_include_pack_voltage",
            "checkbox_label": "Include pack voltage",
            "checkbox_value": bool(opt("notify_include_pack_voltage", True)),
        },
        {
            "label": "Pack low voltage",
            "key": "notify_pack_low_reference",
            "reference": _fmt_reference_value(refs.get("profile_pack_low"), " V", 2),
            "measured": _fmt_reference_value(min(pack_voltages), " V", 3) if pack_voltages else "Waiting for data",
            "user_key": None,
            "user_value": "Auto calculated",
            "step": None,
            "alert_key": "notify_alert_pack_low_voltage",
            "alert_value": bool(opt("notify_alert_pack_low_voltage", True)),
            "checkbox_key": None,
            "checkbox_label": "Uses pack voltage detail",
            "checkbox_value": bool(opt("notify_include_pack_voltage", True)),
        },
        {
            "label": "High temperature",
            "key": "notify_temp_high_warn_c",
            "reference": _fmt_reference_value(refs.get("profile_temp_high"), " C", 0),
            "measured": _fmt_reference_value(max(temps), " C", 1) if temps else "Waiting for data",
            "user_key": "notify_temp_high_warn_c",
            "user_value": opt("notify_temp_high_warn_c", 55),
            "step": "1",
            "alert_key": "notify_alert_temp_high",
            "alert_value": bool(opt("notify_alert_temp_high", True)),
            "checkbox_key": None,
            "checkbox_label": "Warnings enabled",
            "checkbox_value": bool(opt("notify_warnings", True)),
        },
        {
            "label": "Low temperature",
            "key": "notify_temp_low_warn_c",
            "reference": _fmt_reference_value(refs.get("profile_temp_low"), " C", 0),
            "measured": _fmt_reference_value(min(temps), " C", 1) if temps else "Waiting for data",
            "user_key": "notify_temp_low_warn_c",
            "user_value": opt("notify_temp_low_warn_c", 0),
            "step": "1",
            "alert_key": "notify_alert_temp_low",
            "alert_value": bool(opt("notify_alert_temp_low", True)),
            "checkbox_key": None,
            "checkbox_label": "Uses warnings enabled",
            "checkbox_value": bool(opt("notify_warnings", True)),
        },
    ]

    return {
        "selected": selected,
        "policy": opt("notify_bms_warning_policy", "user_reference_or_critical"),
        "policy_choices": WARNING_TELEGRAM_POLICY_CHOICES,
        "detected_cell_count": detected_cell_count or "Unknown",
        "profile_label": refs.get("profile_label", "Unknown"),
        "reference_source": _reference_source_label(refs),
        "rows": rows,
    }


def render_index(action_result="", action_message="", active_tab="dashboard", compare_data=None, restore_preview=None):
    runtime_options, error = load_options()
    config_options, pending_options = config_options_for_edit(runtime_options) if runtime_options else ({}, None)
    options = config_options if active_tab == "config" else runtime_options
    grouped = build_grouped_config(config_options if active_tab == "config" else options)

    # Live tabs render from the running monitor/runtime options. The Config tab may
    # show pending saved options before restart, but live data must keep using the
    # active runtime config so the header/source badge does not jump to "No data".
    live = attach_monitoring_health(runtime_options, get_page_live_snapshot(runtime_options)) if runtime_options and active_tab in ("status", "dashboard", "history", "setup", "diagnostics", "config") else None
    config_live = get_page_live_snapshot(runtime_options) if runtime_options and active_tab == "config" else None
    history_status = build_history_status(runtime_options) if runtime_options and active_tab in ("setup", "diagnostics") else None
    setup_checklist = build_setup_checklist(runtime_options, live, history_status) if runtime_options else None

    return render_template(
        "index.html",
        grouped=grouped,
        live=live,
        events=load_events(),
        error=error,
        action_result=action_result,
        action_message=action_message,
        active_tab=active_tab,
        config_yaml=generate_config_yaml(config_options if active_tab == "config" else options),
        config_backups=list_config_backups(),
        config_backup_summary=config_backup_summary(),
        compare_data=compare_data,
        restore_preview=restore_preview,
        diagnostics=build_diagnostics(runtime_options, live) if runtime_options and active_tab == "diagnostics" else None,
        history_status=history_status,
        log_view=build_log_view(runtime_options) if runtime_options and active_tab == "logs" else None,
        battery_reference_table=build_battery_reference_table(config_options, config_live) if config_options and active_tab == "config" else None,
        setup_checklist=setup_checklist,
        pending_options=pending_options,
        card_help=CARD_HELP,
        field_help=FIELD_HELP,
        config_section_badges=CONFIG_SECTION_BADGES,
        config_section_tiers=CONFIG_SECTION_TIERS,
        addon_version=ADDON_VERSION,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def render_classic_index():
    tab = request.args.get("tab", "dashboard")
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


@app.route("/", methods=["GET"])
def index():
    return render_classic_index()


@app.route("/test-telegram", methods=["GET", "POST"])
def route_test_telegram():
    if request.method == "GET":
        return redirect_to_tab("setup")

    options, error = load_options()
    if error:
        return redirect_to_tab("setup", "warn", error)

    ok, message = test_telegram(options)
    append_event("telegram_test", "Telegram test", message, "ok" if ok else "warn")
    return redirect_to_tab("setup", "ok" if ok else "warn", message)


@app.route("/test-mqtt", methods=["GET", "POST"])
def route_test_mqtt():
    if request.method == "GET":
        return redirect_to_tab("setup")

    options, error = load_options()
    if error:
        return redirect_to_tab("setup", "warn", error)

    ok, message = test_mqtt(options)
    append_event("mqtt_test", "MQTT test", message, "ok" if ok else "warn")
    return redirect_to_tab("setup", "ok" if ok else "warn", message)


@app.route("/test-full-monitoring", methods=["GET", "POST"])
def route_test_full_monitoring():
    if request.method == "GET":
        return redirect_to_tab("setup")

    options, error = load_options()
    if error:
        return redirect_to_tab("setup", "warn", error)

    ok, message = test_full_monitoring(options)
    append_event("full_monitoring_test", "Full Monitoring check", message, "ok" if ok else "warn")
    return redirect_to_tab("setup", "ok" if ok else "warn", message)


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


@app.route("/download-logs.txt", methods=["GET"])
def route_download_logs_txt():
    options, error = load_options()
    if error:
        return Response(error, mimetype="text/plain", status=500)

    log_view = build_log_view(options)
    lines = [
        "PaceBMS support logs",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Configured debug_output: {log_view['debug_output']}",
        "",
    ]
    for row in reversed(log_view["rows"]):
        lines.append(
            f"{row['time']} [{row['source']}] [{row['category']}] [debug {row['level']}] {row['message']}".strip()
        )

    return Response(
        "\n".join(lines) + "\n",
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment; filename=pacebms-logs.txt"},
    )


@app.route("/clear-warning-suppression", methods=["POST"])
def route_clear_warning_suppression():
    """Request clearing Telegram warning cooldown/suppression state.

    This only affects add-on notification state. It does not send BMS commands
    and it does not change BMS thresholds or FET states.
    """
    try:
        Path(WARNING_NOTIFY_CLEAR_FLAG_PATH).write_text(datetime.now().isoformat(), encoding="utf-8")
        if os.path.exists(WARNING_NOTIFY_STATE_PATH):
            os.remove(WARNING_NOTIFY_STATE_PATH)
        message = "Warning notification suppression state cleared. The next active warning can notify again."
        append_event("warning_suppression", "Warning suppression cleared", message, "ok")
        return redirect_to_tab("config", "ok", message)
    except Exception as exc:
        message = f"Could not clear warning suppression state: {exc}"
        append_event("warning_suppression", "Warning suppression clear failed", message, "warn")
        return redirect_to_tab("config", "warn", message)





INTEGER_FIELDS = {
    "mqtt_port": (1, 65535),
    "state_force_republish_seconds": (0, 86400),
    "warn_force_republish_seconds": (0, 86400),
    "bms_baudrate": (1200, 921600),
    "scan_interval": (1, 3600),
    "debug_output": (0, 3),
    "zero_pad_number_cells": (0, 4),
    "zero_pad_number_packs": (0, 4),
    "expected_cell_count": (0, 512),
    "expected_pack_count": (0, 32),
    "notify_cell_delta_warn_mv": (0, 5000),
    "notify_temp_high_warn_c": (-40, 100),
    "notify_temp_low_warn_c": (-40, 100),
    "notify_soc_high_threshold": (0, 100),
    "notify_soc_high_reset": (0, 100),
    "notify_soh_threshold": (0, 100),
    "notify_retry_count": (0, 10),
    "notify_stale_data_seconds": (10, 86400),
    "notify_stale_data_repeat_seconds": (60, 86400),
    "notify_warning_repeat_seconds": (60, 86400),
    "notify_warning_repeat_caution_seconds": (60, 86400),
    "notify_warning_repeat_warning_seconds": (60, 86400),
    "notify_warning_repeat_critical_seconds": (60, 86400),
    "notify_warning_clear_confirm_reads": (1, 10),
    "notify_fet_repeat_seconds": (60, 86400),
}

FLOAT_FIELDS = {
    "notify_cell_high_warn_voltage": (0.0, 5.0),
    "notify_cell_low_warn_voltage": (0.0, 5.0),
    "daily_energy_current_deadband_a": (0.0, 10.0),
    "capacity_per_pack_ah": (0.0, 2000.0),
}

TIME_FIELDS = {
    "notify_daily_summary_time",
    "notify_delta_report_time",
    "notify_delta_window_start",
    "notify_delta_window_end",
}

REQUIRED_TEXT_FIELDS = {
    "mqtt_host",
    "mqtt_user",
    "mqtt_base_topic",
    "mqtt_ha_discovery_topic",
    "connection_type",
    "bms_serial",
}

COMMA_NUMBER_LIST_FIELDS = {
    "notify_soc_low_thresholds": (0.0, 100.0),
}

BOOLEAN_FIELDS = {
    "notify_enabled",
    "notify_startup",
    "notify_disconnect",
    "notify_soc_low",
    "notify_soc_high",
    "notify_soc_high_on_startup",
    "notify_soh",
    "notify_soh_on_startup",
    "notify_warnings",
    "notify_warning_detail_enabled",
    "notify_fet",
    "notify_daily_summary",
    "notify_delta_report",
    "notify_stale_data",
    "notify_stale_recovery",
    "notify_include_all_cells_above_threshold",
    "notify_include_all_cells_below_threshold",
    "notify_include_highest_and_lowest_cell",
    "notify_include_pack_voltage",
    "notify_include_soc_soh",
    "notify_ignore_charge_fet_off_when_full",
    "notify_alert_discharge_fet_off",
    "mqtt_ha_discovery",
    "mqtt_retain_state",
    "capacity_fallback_enabled",
}


def normalize_decimal_text(value):
    """Allow comma decimal input such as 4,2 and convert it to 4.2."""
    if isinstance(value, str):
        return value.strip().replace(",", ".")
    return str(value)


def is_valid_time_hhmm(value):
    import re
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{2}:\d{2}", text):
        return False
    try:
        hour, minute = text.split(":")
        return 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59
    except Exception:
        return False

def validate_config_options(options):
    """Validate web config options before saving to Home Assistant."""
    import re
    errors = []

    for key in REQUIRED_TEXT_FIELDS:
        if key in options and str(options.get(key, "")).strip() == "":
            errors.append(f"{key} is required and cannot be blank.")

    for key, (minimum, maximum) in INTEGER_FIELDS.items():
        if key not in options:
            continue
        value = options.get(key)
        try:
            # Reject booleans and text decimals for integer fields.
            if isinstance(value, bool):
                raise ValueError()
            text = str(value).strip()
            if not re.fullmatch(r"-?\d+", text):
                raise ValueError()
            parsed = int(text)
            if parsed < minimum or parsed > maximum:
                errors.append(f"{key} must be a whole number between {minimum} and {maximum}.")
        except Exception:
            errors.append(f"{key} must be a whole number between {minimum} and {maximum}.")

    for key, (minimum, maximum) in FLOAT_FIELDS.items():
        if key not in options:
            continue
        value = options.get(key)
        try:
            parsed = float(normalize_decimal_text(value))
            if parsed < minimum or parsed > maximum:
                errors.append(f"{key} must be a number between {minimum} and {maximum}.")
        except Exception:
            errors.append(f"{key} must be a number between {minimum} and {maximum}. Decimal comma is allowed, e.g. 4,2.")

    for key in TIME_FIELDS:
        if key not in options:
            continue
        if not is_valid_time_hhmm(options.get(key)):
            errors.append(f"{key} must use 24-hour HH:MM format, for example 19:00 or 10:15.")

    for key, (minimum, maximum) in COMMA_NUMBER_LIST_FIELDS.items():
        if key not in options:
            continue
        text = str(options.get(key, "")).strip()
        if not text:
            errors.append(f"{key} cannot be blank. Use comma-separated numbers, for example 50,25,10.")
            continue

        parts = [part.strip() for part in text.split(",")]
        if any(part == "" for part in parts):
            errors.append(f"{key} has an empty value. Use format like 50,25,10.")
            continue

        parsed_values = []
        bad = False
        for part in parts:
            try:
                parsed = float(part.replace(",", "."))
                if parsed < minimum or parsed > maximum:
                    bad = True
                parsed_values.append(parsed)
            except Exception:
                bad = True

        if bad:
            errors.append(f"{key} must contain comma-separated numbers between {minimum} and {maximum}. Example: 50,25,10.")

    if options.get("connection_type") not in ("Serial", "serial"):
        errors.append("connection_type must be Serial. IP mode is not enabled in this add-on build.")

    if "battery_profile" in options and normalize_profile(options.get("battery_profile")) != str(options.get("battery_profile", "")).strip().lower():
        errors.append("battery_profile must be one of: auto, p13s_hubble_am2, p16s_eenovance_mana, custom.")
    if str(options.get("notify_bms_warning_policy", "")).strip() not in WARNING_TELEGRAM_POLICY_CHOICES:
        errors.append("notify_bms_warning_policy must be one of: all_bms_warnings, user_reference_or_critical, user_reference_only.")

    # Logical threshold check
    try:
        high = float(normalize_decimal_text(options.get("notify_soc_high_threshold", 98)))
        reset = float(normalize_decimal_text(options.get("notify_soc_high_reset", 95)))
        if reset >= high:
            errors.append("notify_soc_high_reset must be lower than notify_soc_high_threshold.")
    except Exception:
        pass

    try:
        low_cell = float(normalize_decimal_text(options.get("notify_cell_low_warn_voltage", 3.0)))
        high_cell = float(normalize_decimal_text(options.get("notify_cell_high_warn_voltage", 4.2)))
        if low_cell >= high_cell:
            errors.append("notify_cell_low_warn_voltage must be lower than notify_cell_high_warn_voltage.")
    except Exception:
        pass

    # Explicit Report Schedule validation
    report_schedule_fields = {
        "notify_daily_summary_time": "Daily summary time",
        "notify_delta_report_time": "Delta report time",
        "notify_delta_window_start": "Delta report window start",
        "notify_delta_window_end": "Delta report window end",
    }
    for schedule_key, schedule_label in report_schedule_fields.items():
        if schedule_key in options:
            if not is_valid_time_hhmm(options.get(schedule_key)):
                errors.append(f"{schedule_key} must use 24-hour HH:MM format, for example 19:00, 10:15 or 00:00.")


    return errors



@app.route("/save-config", methods=["POST"])
def route_save_config():
    options, error = load_options()
    if error:
        return render_index("warn", error, active_tab="config")

    edit_options, _pending_options = config_options_for_edit(options)
    new_options = build_options_from_form(request.form, edit_options)

    if new_options == edit_options:
        message = "No configuration changes detected. Nothing was saved."
        append_event("config_save", "No config changes", message, "info")
        return redirect_to_tab("config", "ok", message)

    validation_errors = validate_addon_options(new_options)
    if validation_errors:
        message = "Configuration was not saved. Please fix: " + " | ".join(validation_errors)
        append_event("config_save", "Configuration save blocked", message, "warn")
        return redirect_to_tab("config", "warn", message)

    validation_errors = validate_config_options(new_options)
    if validation_errors:
        message = "Configuration validation failed:\n" + "\n".join(f"- {error}" for error in validation_errors)
        append_event("config_save", "Configuration validation failed", message, "warn")
        return render_index("warn", message, active_tab="config")

    backup_ok, backup_message, backup_filename = create_config_backup("before-save")
    append_event("config_backup", "Configuration backup", backup_message, "ok" if backup_ok else "warn")

    ok, message = save_addon_options(new_options)

    if ok and backup_filename:
        message = message + f" Backup created: {backup_filename}"

    if ok:
        pending_ok = save_pending_options(new_options)
        if not pending_ok:
            message = message + " Pending display cache could not be saved; restart still required."

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
    live = refresh_live_snapshot_cache_once(options)
    return jsonify(attach_monitoring_health(options, live))


@app.route("/api/live", methods=["GET"])
def api_live():
    options, error = load_options()
    if error:
        return jsonify({"ok": False, "error": error}), 500
    live = refresh_live_snapshot_cache_once(options)
    return jsonify(attach_monitoring_health(options, live))


@app.route("/api/history", methods=["GET"])
def api_history():
    try:
        range_seconds = int(request.args.get("range_seconds", "1800"))
    except Exception:
        range_seconds = 1800
    try:
        return jsonify(query_history(range_seconds=range_seconds, db_path=HISTORY_DB_PATH))
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc), "bank": [], "packs": []}), 500


@app.route("/api/history/pack/<pack_id>", methods=["GET"])
def api_history_pack(pack_id):
    try:
        range_seconds = int(request.args.get("range_seconds", "1800"))
    except Exception:
        range_seconds = 1800
    history = query_history(range_seconds=range_seconds, db_path=HISTORY_DB_PATH)
    history["packs"] = [row for row in history.get("packs", []) if str(row.get("pack_id")) == str(pack_id).zfill(2)]
    return jsonify(history)


@app.route("/api/history/cells/<pack_id>", methods=["GET"])
def api_history_cells(pack_id):
    try:
        range_seconds = int(request.args.get("range_seconds", "1800"))
    except Exception:
        range_seconds = 1800
    init_history_db(HISTORY_DB_PATH)
    import sqlite3
    since = int(time.time()) - max(60, range_seconds)
    conn = sqlite3.connect(HISTORY_DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT ts, pack_id, cell_number, voltage
            FROM cell_metrics
            WHERE ts >= ? AND pack_id = ?
            ORDER BY ts ASC, cell_number ASC
            """,
            (since, str(pack_id).zfill(2)),
        ).fetchall()
    finally:
        conn.close()
    return jsonify({"ok": True, "range_seconds": range_seconds, "cells": [dict(row) for row in rows]})


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
    heartbeat = load_monitor_health()
    now = int(time.time())

    if heartbeat is None:
        web_uptime = int(time.time() - WEB_STARTED_AT)
        status = 200 if web_uptime < 90 else 503
        return jsonify({
            "status": "starting" if status == 200 else "unhealthy",
            "reason": "No monitor heartbeat file found yet.",
            "web_uptime_seconds": web_uptime,
        }), status

    updated_at = int(heartbeat.get("updated_at", 0) or 0)
    age = max(0, now - updated_at) if updated_at else 999999
    timeout = int(heartbeat.get("health_timeout_seconds", 60) or 60)
    monitor_state = str(heartbeat.get("state", "unknown"))
    healthy = age <= timeout and monitor_state != "stopped"

    return jsonify({
        "status": "ok" if healthy else "unhealthy",
        "monitor_state": monitor_state,
        "heartbeat_age_seconds": age,
        "health_timeout_seconds": timeout,
        "detail": heartbeat.get("detail", ""),
        "last_analog_success": heartbeat.get("last_analog_success"),
        "last_warn_success": heartbeat.get("last_warn_success"),
    }), 200 if healthy else 503


if __name__ == "__main__":
    startup_options, _startup_error = load_options()
    configure_web_logging(startup_options)
    ensure_live_snapshot_cache_worker()
    app.run(host="0.0.0.0", port=8099)
