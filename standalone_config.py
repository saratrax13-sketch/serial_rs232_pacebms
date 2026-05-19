"""Standalone Docker configuration bootstrap.

Home Assistant creates /data/options.json for add-ons. Standalone Docker does
not, so this helper creates it from config.yaml defaults plus environment
overrides when the file is missing. Existing options are never overwritten.
"""

import json
import os
from pathlib import Path

import yaml


DATA_DIR = Path(os.environ.get("PACEBMS_DATA_DIR", "/data"))
OPTIONS_PATH = DATA_DIR / "options.json"
ADDON_CONFIG_PATH = Path(os.environ.get("PACEBMS_ADDON_CONFIG", "config.yaml"))
ENV_PREFIX = "PACEBMS_"

ENV_ALIASES = {
    "BMS_CONNECTION_MODE": "bms_connection_mode",
    "BMS_SERIAL": "bms_serial",
    "BMS_BAUDRATE": "bms_baudrate",
    "SCAN_INTERVAL": "scan_interval",
    "UI_DATA_SOURCE": "ui_data_source",
    "MQTT_ENABLED": "mqtt_enabled",
    "MQTT_HOST": "mqtt_host",
    "MQTT_PORT": "mqtt_port",
    "MQTT_USER": "mqtt_user",
    "MQTT_PASSWORD": "mqtt_password",
    "MQTT_BASE_TOPIC": "mqtt_base_topic",
    "MQTT_HA_DISCOVERY": "mqtt_ha_discovery",
    "MQTT_HA_DISCOVERY_TOPIC": "mqtt_ha_discovery_topic",
    "MQTT_RETAIN_STATE": "mqtt_retain_state",
    "TELEGRAM_BOT_TOKEN": "telegram_bot_token",
    "TELEGRAM_CHAT_ID": "telegram_chat_id",
    "NOTIFY_ENABLED": "notify_enabled",
    "DEBUG_OUTPUT": "debug_output",
    "METRICS_ENABLED": "metrics_enabled",
    "HISTORY_SAMPLE_SECONDS": "history_sample_seconds",
    "HISTORY_CELL_SAMPLE_SECONDS": "history_cell_sample_seconds",
    "HISTORY_RETENTION_DAYS": "history_retention_days",
    "HISTORY_EVENT_RETENTION_DAYS": "history_event_retention_days",
    "BATTERY_PROFILE": "battery_profile",
    "EXPECTED_CELL_COUNT": "expected_cell_count",
    "EXPECTED_PACK_COUNT": "expected_pack_count",
    "CAPACITY_FALLBACK_ENABLED": "capacity_fallback_enabled",
    "CAPACITY_PER_PACK_AH": "capacity_per_pack_ah",
}

SENSITIVE_KEYS = {
    "mqtt_password",
    "telegram_bot_token",
    "telegram_chat_id",
}


def _load_default_options() -> dict:
    if not ADDON_CONFIG_PATH.exists():
        return {}
    with ADDON_CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    options = data.get("options", {})
    return dict(options) if isinstance(options, dict) else {}


def _coerce_value(raw_value: str, current_value):
    if isinstance(current_value, bool):
        return str(raw_value).strip().lower() in {"1", "true", "yes", "on", "enabled"}
    if isinstance(current_value, int) and not isinstance(current_value, bool):
        return int(str(raw_value).strip())
    if isinstance(current_value, float):
        return float(str(raw_value).strip().replace(",", "."))
    return str(raw_value)


def _apply_environment(options: dict) -> dict:
    updated = dict(options)
    option_keys = set(updated)

    for env_name, option_key in ENV_ALIASES.items():
        full_env_name = f"{ENV_PREFIX}{env_name}"
        if full_env_name in os.environ:
            current_value = updated.get(option_key, "")
            updated[option_key] = _coerce_value(os.environ[full_env_name], current_value)

    for option_key in option_keys:
        full_env_name = f"{ENV_PREFIX}{option_key.upper()}"
        if full_env_name in os.environ:
            updated[option_key] = _coerce_value(os.environ[full_env_name], updated.get(option_key, ""))

    return updated


def ensure_standalone_options() -> bool:
    """Create /data/options.json for standalone Docker if it does not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if OPTIONS_PATH.exists():
        print("Standalone config: existing /data/options.json found; leaving it unchanged.", flush=True)
        return False

    options = _apply_environment(_load_default_options())
    if not options:
        print("Standalone config: no defaults available; skipping options.json creation.", flush=True)
        return False

    tmp_path = OPTIONS_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(options, handle, indent=2, sort_keys=True)
    tmp_path.replace(OPTIONS_PATH)

    visible_keys = sorted(k for k in options if k not in SENSITIVE_KEYS)
    print(
        "Standalone config: created /data/options.json with "
        f"{len(options)} options. Non-sensitive keys: {', '.join(visible_keys)}",
        flush=True,
    )
    return True


if __name__ == "__main__":
    ensure_standalone_options()
