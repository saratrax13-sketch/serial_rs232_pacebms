import json
import os
import time
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
    ],
    "Notifications": [
        "notify_soc_low",
        "notify_soc_high",
        "notify_soh",
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
        "bms_status": "Not available",
        "bms_error": "Not available",
        "bms_version": "Unknown",
        "bms_sn": "Unknown",
        "pack_sn": "Unknown",
        "pack_count": 0,
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

    status_raw = messages.get(f"{base_topic}/bms_status", "")
    error_raw = messages.get(f"{base_topic}/bms_error", "")

    result["bms_status"] = parse_json_or_raw(status_raw)
    result["bms_error"] = parse_json_or_raw(error_raw)

    # Direct topics first. These may not be retained on older versions.
    result["bms_version"] = messages.get(f"{base_topic}/bms_version", "Unknown")
    result["bms_sn"] = messages.get(f"{base_topic}/bms_sn", "Unknown")
    result["pack_sn"] = messages.get(f"{base_topic}/pack_sn", "Unknown")

    # Fallback to retained bms_status JSON if direct serial/version topics were not retained.
    if isinstance(result["bms_status"], dict):
        if result["bms_sn"] == "Unknown":
            result["bms_sn"] = result["bms_status"].get("bms_sn", "Unknown")
        if result["bms_version"] == "Unknown":
            result["bms_version"] = result["bms_status"].get("bms_version", "Unknown")

    # Discover pack topics from retained values.
    pack_ids = set()
    prefix = f"{base_topic}/pack_"
    for topic in messages:
        if topic.startswith(prefix):
            remainder = topic[len(prefix):]
            pack_id = remainder.split("/", 1)[0]
            if pack_id.isdigit():
                pack_ids.add(pack_id)

    packs = []
    for pack_id in sorted(pack_ids, key=lambda x: int(x)):
        pfx = f"{base_topic}/pack_{pack_id}"
        pack = {
            "id": pack_id,
            "soc": messages.get(f"{pfx}/soc", "Unknown"),
            "soh": messages.get(f"{pfx}/soh", "Unknown"),
            "voltage": messages.get(f"{pfx}/v_pack", "Unknown"),
            "current": messages.get(f"{pfx}/i_pack", "Unknown"),
            "delta": messages.get(f"{pfx}/cells_max_diff_calc", "Unknown"),
            "warnings": messages.get(f"{pfx}/warnings", "Normal") or "Normal",
            "charge_fet": messages.get(f"{pfx}/charge_fet", "Unknown"),
            "discharge_fet": messages.get(f"{pfx}/discharge_fet", "Unknown"),
            "fully": messages.get(f"{pfx}/fully", "Unknown"),
        }
        packs.append(pack)

    result["packs"] = packs
    result["pack_count"] = len(packs)

    if not messages and not result["error"]:
        result["error"] = "No retained MQTT values were received. Check mqtt_retain_state and MQTT connection."

    return result


@app.route("/")
def index():
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
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8099)
