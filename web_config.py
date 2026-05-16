import json
import os
import time
import urllib.request
from datetime import datetime
from flask import Flask, render_template

import paho.mqtt.client as mqtt

app = Flask(__name__)

OPTIONS_PATH = "/data/options.json"

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
        "bms_ip",
        "bms_port",
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


def fetch_mqtt_snapshot(options, timeout=1.2):
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

    for pack_id in sorted(pack_ids, key=lambda x: int(x)):
        pfx = f"{base_topic}/pack_{pack_id}"

        cell_prefix = f"{pfx}/v_cells/cell_"
        cell_numbers = []
        cell_values = []
        for topic, value in messages.items():
            if topic.startswith(cell_prefix):
                try:
                    cell_numbers.append(int(topic.rsplit("_", 1)[1]))
                    fv = _to_float(value)
                    if fv is not None:
                        cell_values.append(fv)
                except Exception:
                    pass

        cell_count = max(cell_numbers) if cell_numbers else 0
        total_cells += cell_count

        warnings = messages.get(f"{pfx}/warnings", "Normal") or "Normal"
        has_warning = warnings != "Normal"
        if has_warning:
            warning_count += 1

        voltage = messages.get(f"{pfx}/v_pack", "Unknown")
        current = messages.get(f"{pfx}/i_pack", "Unknown")
        soc = messages.get(f"{pfx}/soc", "Unknown")
        soh = messages.get(f"{pfx}/soh", "Unknown")
        delta = messages.get(f"{pfx}/cells_max_diff_calc", "Unknown")

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
            "charge_fet": messages.get(f"{pfx}/charge_fet", "Unknown"),
            "discharge_fet": messages.get(f"{pfx}/discharge_fet", "Unknown"),
            "fully": messages.get(f"{pfx}/fully", "Unknown"),
        })

    result["packs"] = packs
    result["pack_count"] = len(packs)
    result["total_cells"] = total_cells
    result["warning_count"] = warning_count

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


def render_index(action_result="", action_message=""):
    options, error = load_options()

    grouped = {}
    for group_name, keys in GROUPS.items():
        grouped[group_name] = []
        for key in keys:
            raw_value = options.get(key, "")
            grouped[group_name].append({
                "key": key,
                "value": safe_value(key, raw_value),
                "class": status_class(key, raw_value),
            })

    live = fetch_mqtt_snapshot(options) if options else None

    return render_template(
        "index.html",
        grouped=grouped,
        live=live,
        error=error,
        action_result=action_result,
        action_message=action_message,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@app.route("/", methods=["GET"])
def index():
    return render_index()


@app.route("/test-telegram", methods=["POST"])
def route_test_telegram():
    options, error = load_options()
    if error:
        return render_index("warn", error)

    ok, message = test_telegram(options)
    return render_index("ok" if ok else "warn", message)


@app.route("/test-mqtt", methods=["POST"])
def route_test_mqtt():
    options, error = load_options()
    if error:
        return render_index("warn", error)

    ok, message = test_mqtt(options)
    return render_index("ok" if ok else "warn", message)


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8099)
