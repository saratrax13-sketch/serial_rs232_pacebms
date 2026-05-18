import unittest
import importlib.util
import json
import os
import sys
import tempfile
import types
from unittest.mock import patch


if importlib.util.find_spec("paho") is None:
    paho_module = types.ModuleType("paho")
    mqtt_package = types.ModuleType("paho.mqtt")
    mqtt_client_module = types.ModuleType("paho.mqtt.client")
    mqtt_client_module.Client = object
    mqtt_package.client = mqtt_client_module
    paho_module.mqtt = mqtt_package
    sys.modules["paho"] = paho_module
    sys.modules["paho.mqtt"] = mqtt_package
    sys.modules["paho.mqtt.client"] = mqtt_client_module

if importlib.util.find_spec("serial") is None:
    serial_module = types.ModuleType("serial")
    serial_module.EIGHTBITS = 8
    serial_module.PARITY_NONE = "N"
    serial_module.STOPBITS_ONE = 1
    serial_module.Serial = object
    sys.modules["serial"] = serial_module

if importlib.util.find_spec("yaml") is None:
    yaml_module = types.ModuleType("yaml")
    yaml_module.FullLoader = object
    yaml_module.load = lambda *args, **kwargs: {}
    sys.modules["yaml"] = yaml_module

if importlib.util.find_spec("flask") is None:
    flask_module = types.ModuleType("flask")

    class DummyFlask:
        def __init__(self, *args, **kwargs):
            pass

        def route(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

        def run(self, *args, **kwargs):
            pass

    class DummyResponse:
        def __init__(self, *args, **kwargs):
            pass

    flask_module.Flask = DummyFlask
    flask_module.Response = DummyResponse
    flask_module.jsonify = lambda *args, **kwargs: {}
    flask_module.render_template = lambda *args, **kwargs: ""
    flask_module.request = types.SimpleNamespace(form={})
    flask_module.send_file = lambda *args, **kwargs: None
    flask_module.redirect = lambda *args, **kwargs: None
    sys.modules["flask"] = flask_module

import bms_monitor
import bms_notify
import web_config


def build_pace_response(info: bytes = b"ABCD") -> bytes:
    header = b"\x7e" + b"25" + b"01" + b"46" + b"00"
    lenid = bytes(format(len(info), "03X"), "ASCII")
    lchksum = b"0" if lenid == b"000" else bytes(bms_monitor.lchksum_calc(lenid), "ASCII")
    body = header + lchksum + lenid + info
    return body + bytes(bms_monitor.chksum_calc(body), "ASCII") + b"\r"


class PaceFrameTests(unittest.TestCase):
    def test_valid_pace_frame_parses_info_payload(self):
        ok, payload = bms_monitor.bms_parse_response(build_pace_response(b"HELLO"))

        self.assertTrue(ok)
        self.assertEqual(payload, b"HELLO")

    def test_bad_checksum_is_rejected(self):
        frame = bytearray(build_pace_response(b"HELLO"))
        frame[-3] = ord("0") if frame[-3] != ord("0") else ord("1")

        ok, message = bms_monitor.bms_parse_response(bytes(frame))

        self.assertFalse(ok)
        self.assertEqual(message, "Checksum error")


class WarningNormalizationTests(unittest.TestCase):
    def test_p16s_two_pack_analog_frame_with_interpack_trailer_parses(self):
        payload = (
            b"0002100D1B0D1C0D1C0D1D0D1D0D1C0D1C0D1C0D1C0D1C0D1C0D1D0D1C0D1C0D1C0D1C"
            b"080BA90BA30BA40B9E0BA60BA80BB10BCF0579D1EC3E67045348004451404C0000000000000000641510"
            b"0000100D1D0D1F0D1D0D1D0D1E0D1D0D1E0D1E0D1E0D1E0D1E0D1E0D1E0D1E0D1E0D1D"
            b"080BA00BA10BA20B9C0B9F0BA10BA70BC904DBD1F63CF104514001D251404B000000000000000062150B0000"
        )

        with patch("bms_monitor.bms_request", return_value=(True, payload)):
            ok, data = bms_monitor.bms_get_analog_data(None, {"debug_output": 0})

        self.assertTrue(ok)
        self.assertEqual(data.packs, 2)
        self.assertEqual([pack.cells for pack in data.pack_data], [16, 16])
        self.assertEqual([pack.temps for pack in data.pack_data], [8, 8])
        self.assertAlmostEqual(data.pack_data[0].v_pack, 53.74)
        self.assertAlmostEqual(data.pack_data[1].v_pack, 53.75)

    def test_p16s_two_pack_warning_frame_with_interpack_trailer_parses_cleanly(self):
        payload = (
            b"0002100000000000000000000000000000000006000000000000000000000026000000000000"
            b"0F0040100000000000000000000000000000000006000000000000000000000026000000000000360000"
        )

        with patch("bms_monitor.bms_request", return_value=(True, payload)):
            ok, warnings = bms_monitor.bms_get_warn_info(None, {"debug_output": 0}, 2)

        self.assertTrue(ok)
        self.assertEqual(len(warnings), 2)
        self.assertEqual(warnings[0].warnings, "")
        self.assertEqual(warnings[1].warnings, "")
        self.assertEqual(warnings[0].charge_fet, 1)
        self.assertEqual(warnings[0].discharge_fet, 1)
        self.assertEqual(warnings[1].charge_fet, 1)
        self.assertEqual(warnings[1].discharge_fet, 1)

    def test_warning_state_words_are_not_split_on_letter_n(self):
        family = bms_monitor.normalize_warning_family(
            "Warning State 1: Above cell volt warn | Above total volt warn"
        )

        self.assertEqual(
            family,
            "High cell voltage | High pack voltage",
        )
        self.assertNotIn("War |", family)

    def test_cell_specific_and_generic_high_voltage_share_family(self):
        self.assertEqual(
            bms_monitor.normalize_warning_family(
                "cell 8 Above upper limit, Warning State 1: Above cell volt warn"
            ),
            "High cell voltage",
        )

    def test_protection_state_is_critical(self):
        pack = bms_monitor.PackData(
            pack_number=1,
            cells=13,
            temps=0,
            v_cells=[4180] * 13,
            v_pack=54.1,
            soc=99.0,
            soh=90.0,
        )

        severity, reasons = bms_monitor.classify_warning_severity(
            "Protection State 1: Above cell volt protect, Warning State 1: Above cell volt warn",
            pack,
            {"notify_cell_high_warn_voltage": 4.20},
        )

        self.assertEqual(severity, "critical")
        self.assertTrue(any("protection" in reason.lower() for reason in reasons))

    def test_repeat_interval_uses_severity_specific_config(self):
        config = {
            "notify_warning_repeat_seconds": 1800,
            "notify_warning_repeat_caution_seconds": 21600,
            "notify_warning_repeat_warning_seconds": 3600,
            "notify_warning_repeat_critical_seconds": 900,
        }

        self.assertEqual(bms_monitor.warning_repeat_seconds_for_severity(config, "caution"), 21600)
        self.assertEqual(bms_monitor.warning_repeat_seconds_for_severity(config, "warning"), 3600)
        self.assertEqual(bms_monitor.warning_repeat_seconds_for_severity(config, "critical"), 900)


class TelegramConfigTests(unittest.TestCase):
    def test_placeholder_values_are_not_configured(self):
        self.assertFalse(bms_notify.telegram_value_configured(""))
        self.assertFalse(bms_notify.telegram_value_configured("YOUR_TELEGRAM_BOT_TOKEN"))
        self.assertFalse(bms_notify.telegram_value_configured("YOUR_TELEGRAM_CHAT_ID"))
        self.assertTrue(bms_notify.telegram_value_configured("123456:real-token"))

    def test_placeholder_telegram_does_not_call_network(self):
        config = {
            "notify_enabled": True,
            "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
            "telegram_chat_id": "YOUR_TELEGRAM_CHAT_ID",
        }

        with patch("bms_notify.urllib.request.urlopen") as urlopen:
            bms_notify.telegram_send(config, "test")

        urlopen.assert_not_called()

    def test_web_telegram_test_rejects_placeholders(self):
        ok, message = web_config.test_telegram({
            "notify_enabled": True,
            "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
            "telegram_chat_id": "YOUR_TELEGRAM_CHAT_ID",
        })

        self.assertFalse(ok)
        self.assertIn("not configured", message)

    def test_setup_checklist_flags_telegram_placeholders(self):
        checklist = web_config.build_setup_checklist({
            "connection_type": "Serial",
            "bms_serial": "/dev/ttyUSB0",
            "mqtt_host": "192.168.1.10",
            "mqtt_port": 1883,
            "mqtt_ha_discovery": True,
            "mqtt_retain_state": True,
            "notify_enabled": True,
            "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
            "telegram_chat_id": "YOUR_TELEGRAM_CHAT_ID",
            "notify_warning_repeat_caution_seconds": 21600,
            "notify_warning_repeat_warning_seconds": 3600,
            "notify_warning_repeat_critical_seconds": 900,
        })

        self.assertFalse(checklist["telegram_configured"])
        telegram_item = next(item for item in checklist["items"] if item["title"] == "Telegram")
        self.assertEqual(telegram_item["class"], "warning")

    def test_full_monitoring_check_does_not_send_telegram(self):
        options = {
            "connection_type": "Serial",
            "bms_serial": "/dev/ttyUSB0",
            "scan_interval": 5,
            "mqtt_host": "192.168.1.10",
            "mqtt_port": 1883,
            "notify_enabled": True,
            "telegram_bot_token": "123456:real-token",
            "telegram_chat_id": "12345",
            "notify_soc_high_threshold": 98,
            "notify_soc_high_reset": 95,
            "notify_soh_threshold": 95,
            "notify_cell_high_warn_voltage": 4.2,
            "notify_cell_low_warn_voltage": 3.0,
            "notify_stale_data_seconds": 120,
            "notify_stale_data_repeat_seconds": 1800,
            "notify_warning_repeat_caution_seconds": 21600,
            "notify_warning_repeat_warning_seconds": 3600,
            "notify_warning_repeat_critical_seconds": 900,
            "state_force_republish_seconds": 300,
            "warn_force_republish_seconds": 300,
        }

        with (
            patch("web_config.test_mqtt", return_value=(True, "MQTT OK")),
            patch("bms_notify.urllib.request.urlopen") as urlopen,
        ):
            ok, message = web_config.test_full_monitoring(options)

        self.assertTrue(ok)
        self.assertIn("No BMS commands or Telegram messages", message)
        urlopen.assert_not_called()


class EnergyTrackingTests(unittest.TestCase):
    def test_energy_uses_elapsed_time_after_first_sample(self):
        state = bms_notify.NotifyState({})

        with patch("bms_notify.time.time", side_effect=[1000.0, 1010.0]):
            state.on_energy_update(1, voltage=50.0, current=10.0, scan_interval=5)
            state.on_energy_update(1, voltage=50.0, current=10.0, scan_interval=5)

        expected = 500.0 * (10.0 / 3600.0) / 1000.0
        self.assertAlmostEqual(state.kwh_discharged[1], expected)
        self.assertEqual(state.kwh_charged[1], 0.0)


class HealthEndpointTests(unittest.TestCase):
    def test_setup_page_renders_setup_checklist(self):
        options = {
            "connection_type": "Serial",
            "bms_serial": "/dev/ttyUSB0",
            "scan_interval": 5,
            "mqtt_host": "192.168.1.10",
            "mqtt_port": 1883,
            "mqtt_ha_discovery": True,
            "mqtt_retain_state": True,
            "notify_enabled": True,
            "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
            "telegram_chat_id": "YOUR_TELEGRAM_CHAT_ID",
            "notify_warning_repeat_caution_seconds": 21600,
            "notify_warning_repeat_warning_seconds": 3600,
            "notify_warning_repeat_critical_seconds": 900,
        }
        live = {
            "ok": True,
            "availability": "online",
            "monitor_state": "running",
            "stale": "OFF",
            "stale_reason": "Fresh",
            "last_analog_read": "2026-05-17 20:00:00",
            "last_warn_read": "2026-05-17 20:00:01",
            "analog_age_seconds": 1,
            "warn_age_seconds": 1,
            "overall_status": "OK",
            "overall_class": "healthy",
            "layout": "2 pack(s), 32 cells total",
            "bms_sn": "TEST",
            "base_topic": "pacebms",
            "fetched_at": "now",
            "error": "",
            "severity_summary": {},
            "packs": [],
        }

        with (
            patch("web_config.load_options", return_value=(options, "")),
            patch("web_config.fetch_mqtt_snapshot", return_value=live),
            patch("web_config.load_events", return_value=[]),
        ):
            response = web_config.app.test_client().get("/?tab=setup")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Setup Checklist", response.data)
        self.assertIn(b"Setup Tests", response.data)

    def test_status_page_renders_technician_view(self):
        options = {
            "connection_type": "Serial",
            "bms_serial": "/dev/ttyUSB0",
            "scan_interval": 5,
            "mqtt_host": "192.168.1.10",
            "mqtt_port": 1883,
            "mqtt_ha_discovery": True,
            "mqtt_retain_state": True,
            "notify_enabled": False,
            "notify_warning_repeat_caution_seconds": 21600,
            "notify_warning_repeat_warning_seconds": 3600,
            "notify_warning_repeat_critical_seconds": 900,
        }
        live = {
            "ok": True,
            "availability": "online",
            "monitor_state": "running",
            "stale": "OFF",
            "stale_reason": "Fresh",
            "last_analog_read": "2026-05-17 20:00:00",
            "last_warn_read": "2026-05-17 20:00:01",
            "analog_age_seconds": 1,
            "warn_age_seconds": 1,
            "overall_status": "OK",
            "overall_class": "healthy",
            "layout": "2 pack(s), 32 cells total",
            "bms_sn": "TEST",
            "base_topic": "pacebms",
            "fetched_at": "now",
            "error": "",
            "severity_summary": {},
            "packs": [{
                "id": "01",
                "cell_count": 16,
                "role": "Master",
                "serial": "PACKTEST",
                "soc": "95",
                "soh": "99",
                "cycles": "42",
                "remaining_capacity_ah": "160",
                "full_capacity_ah": "200",
                "design_capacity_ah": "200",
                "voltage": "54.0",
                "current": "1.0",
                "power_kw": "0.05",
                "delta": "12",
                "warnings": "Normal",
                "severity_class": "healthy",
                "severity_label": "Normal",
                "highest_cell": {"number": "01", "voltage": "3.400"},
                "lowest_cell": {"number": "02", "voltage": "3.388"},
                "cell_high_ref": "4.20",
                "pack_high_ref": "67.20",
                "charge_fet": "ON",
                "discharge_fet": "ON",
                "fully": "OFF",
                "reference_checks": ["No active BMS warning."],
            }],
        }

        with (
            patch("web_config.load_options", return_value=(options, "")),
            patch("web_config.fetch_mqtt_snapshot", return_value=live),
            patch("web_config.load_events", return_value=[]),
        ):
            response = web_config.app.test_client().get("/?tab=status")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Technician live view", response.data)
        self.assertNotIn(b"Monitoring Health", response.data)
        self.assertNotIn(b"Live Status", response.data)
        self.assertNotIn(b"Refresh Status", response.data)
        self.assertNotIn(b"Open Setup", response.data)
        self.assertNotIn(b"Tech Status auto-refresh runs every 15 seconds", response.data)
        self.assertIn(b"Warning Intelligence", response.data)
        self.assertIn(b"Energy & Health", response.data)
        self.assertIn(b"Capacity", response.data)
        self.assertIn(b"Power", response.data)
        self.assertIn(b"Pack SOC Comparison", response.data)
        self.assertIn(b"Highest vs Lowest Cell", response.data)

    def test_monitoring_health_uses_heartbeat_and_live_mqtt(self):
        options = {
            "notify_stale_data_seconds": 120,
            "notify_stale_data_repeat_seconds": 1800,
        }
        live = {
            "ok": True,
            "availability": "online",
            "monitor_state": "running",
            "stale": "OFF",
            "last_analog_read": "2026-05-17 20:00:00",
            "last_warn_read": "2026-05-17 20:00:01",
            "analog_age_seconds": 8,
            "warn_age_seconds": 9,
            "warning_count": 0,
            "pack_count": 2,
            "total_cells": 32,
            "layout": "2 pack(s), 32 cells total",
        }
        heartbeat = {
            "updated_at": 1000,
            "state": "running",
            "health_timeout_seconds": 60,
        }

        with patch("web_config.time.time", return_value=1020):
            health = web_config.build_monitoring_health(options, live, heartbeat)

        self.assertEqual(health["status"], "Watching")
        self.assertEqual(health["class"], "healthy")
        heartbeat_check = next(item for item in health["checks"] if item["label"] == "Monitor heartbeat")
        self.assertEqual(heartbeat_check["class"], "healthy")

    def test_monitoring_health_flags_stale_data(self):
        options = {
            "notify_stale_data_seconds": 120,
            "notify_stale_data_repeat_seconds": 1800,
        }
        live = {
            "ok": True,
            "availability": "online",
            "monitor_state": "running",
            "stale": "ON",
            "stale_reason": "Analog data is stale",
            "analog_age_seconds": 180,
            "warn_age_seconds": 10,
            "warning_count": 0,
            "pack_count": 1,
            "total_cells": 16,
            "layout": "1 pack(s), 16 cells total",
        }
        heartbeat = {
            "updated_at": 1000,
            "state": "running",
            "health_timeout_seconds": 60,
        }

        with patch("web_config.time.time", return_value=1010):
            health = web_config.build_monitoring_health(options, live, heartbeat)

        self.assertEqual(health["status"], "Data Stale")
        self.assertEqual(health["class"], "stale")

    def test_user_summary_combines_pack_values(self):
        options = {
            "notify_temp_high_warn_c": 55,
            "notify_temp_low_warn_c": 0,
        }
        live = {
            "ok": True,
            "availability": "online",
            "monitor_state": "running",
            "stale": "OFF",
            "warning_count": 0,
            "total_cells": 32,
            "packs": [
                {
                    "voltage": "52.0",
                    "current": "-10.0",
                    "soc": "80",
                    "soh": "95",
                    "remaining_capacity_ah": "160",
                    "full_capacity_ah": "200",
                    "design_capacity_ah": "200",
                    "temperatures": [25, 26],
                    "fully": "OFF",
                },
                {
                    "voltage": "52.0",
                    "current": "-12.0",
                    "soc": "70",
                    "soh": "90",
                    "remaining_capacity_ah": "140",
                    "full_capacity_ah": "200",
                    "design_capacity_ah": "200",
                    "temperatures": [27, 28],
                    "fully": "OFF",
                },
            ],
        }

        summary = web_config._calculate_user_summary(options, live)

        self.assertEqual(summary["status"], "Discharging")
        self.assertEqual(summary["combined_soc"], "75.0%")
        self.assertEqual(summary["combined_soh"], "92.5%")
        self.assertEqual(summary["total_power_kw"], "-1.14 kW")
        self.assertEqual(summary["remaining_capacity_ah"], "300 Ah")
        self.assertEqual(summary["full_capacity_ah"], "400 Ah")
        self.assertEqual(summary["remaining_energy_kwh"], "15.60 kWh")
        self.assertEqual(summary["runtime_remaining"], "13h 38m")
        self.assertEqual(summary["time_label"], "Runtime Estimate")
        self.assertEqual(summary["power_flow"], "Discharging at 1.14 kW")
        self.assertEqual(summary["warning_summary"], "No active warnings")
        self.assertEqual(summary["health"], "90.0%")
        self.assertEqual(summary["temperature_status"], "Normal")

    def test_user_summary_runtime_states(self):
        options = {
            "notify_temp_high_warn_c": 55,
            "notify_temp_low_warn_c": 0,
        }
        base_live = {
            "ok": True,
            "availability": "online",
            "monitor_state": "running",
            "stale": "OFF",
            "warning_count": 0,
            "total_cells": 16,
            "packs": [{
                "voltage": "50.0",
                "soc": "80",
                "soh": "95",
                "remaining_capacity_ah": "100",
                "full_capacity_ah": "120",
                "design_capacity_ah": "120",
                "temperatures": [25],
                "fully": "OFF",
            }],
        }

        charging = dict(base_live)
        charging["packs"] = [dict(base_live["packs"][0], current="10")]
        charging_summary = web_config._calculate_user_summary(options, charging)
        self.assertEqual(charging_summary["runtime_remaining"], "2h")
        self.assertEqual(charging_summary["time_label"], "Charge Time Estimate")
        self.assertEqual(charging_summary["power_flow"], "Charging at 0.50 kW")
        self.assertIn("Charge-to-full", charging_summary["runtime_detail"])

        idle = dict(base_live)
        idle["packs"] = [dict(base_live["packs"][0], current="0")]
        idle_summary = web_config._calculate_user_summary(options, idle)
        self.assertEqual(idle_summary["runtime_remaining"], "Idle")
        self.assertEqual(idle_summary["time_label"], "Idle")

    def test_dashboard_page_renders_monitoring_snapshot(self):
        options = {
            "connection_type": "Serial",
            "bms_serial": "/dev/ttyUSB0",
            "scan_interval": 5,
            "mqtt_host": "192.168.1.10",
            "mqtt_port": 1883,
            "mqtt_ha_discovery": True,
            "mqtt_retain_state": True,
            "notify_enabled": False,
            "notify_stale_data_seconds": 120,
            "notify_warning_repeat_caution_seconds": 21600,
            "notify_warning_repeat_warning_seconds": 3600,
            "notify_warning_repeat_critical_seconds": 900,
        }
        live = {
            "ok": True,
            "availability": "online",
            "monitor_state": "running",
            "stale": "OFF",
            "stale_reason": "Fresh",
            "last_analog_read": "2026-05-17 20:00:00",
            "last_warn_read": "2026-05-17 20:00:01",
            "analog_age_seconds": 1,
            "warn_age_seconds": 1,
            "overall_status": "Healthy",
            "overall_class": "healthy",
            "layout": "1 pack(s), 16 cells total",
            "bms_sn": "TEST",
            "base_topic": "pacebms",
            "fetched_at": "now",
            "error": "",
            "severity_summary": {},
            "pack_count": 1,
            "total_cells": 16,
            "warning_count": 0,
            "packs": [{
                "id": "01",
                "cell_count": 16,
                "soc": "95",
                "soh": "99",
                "cycles": "42",
                "remaining_capacity_ah": "160",
                "full_capacity_ah": "200",
                "design_capacity_ah": "200",
                "voltage": "54.0",
                "current": "1.0",
                "delta": "12",
                "temperatures": [25, 26],
                "warnings": "Normal",
                "severity_class": "healthy",
                "severity_label": "Normal",
                "highest_cell": {"number": "01", "voltage": "3.400"},
                "lowest_cell": {"number": "02", "voltage": "3.388"},
            }],
        }

        with (
            patch("web_config.load_options", return_value=(options, "")),
            patch("web_config.fetch_mqtt_snapshot", return_value=live),
            patch("web_config.load_events", return_value=[]),
            patch("web_config.load_monitor_health", return_value={
                "updated_at": 1000,
                "state": "running",
                "health_timeout_seconds": 60,
            }),
            patch("web_config.time.time", return_value=1001),
        ):
            response = web_config.app.test_client().get("/?tab=dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Cycles", response.data)
        self.assertIn(b"42", response.data)
        self.assertIn(b"Combined SOH", response.data)
        self.assertIn(b"Lowest Pack SOH", response.data)
        self.assertIn(b"pack-quick-strip", response.data)
        self.assertIn(b"Refresh dashboard", response.data)
        self.assertIn(b"Master", response.data)
        self.assertIn(b"pack-metric-value healthy", response.data)
        self.assertIn(b"Battery Power", response.data)
        self.assertIn(b"Charge Time Estimate", response.data)
        self.assertIn(b"Last Updated", response.data)
        self.assertIn(b"Remaining Capacity", response.data)
        self.assertNotIn(b"Monitoring Snapshot", response.data)
        self.assertNotIn(b"Warning Summary", response.data)

    def test_root_defaults_to_user_dashboard(self):
        options = {
            "connection_type": "Serial",
            "bms_serial": "/dev/ttyUSB0",
            "scan_interval": 5,
            "mqtt_host": "192.168.1.10",
            "mqtt_port": 1883,
            "mqtt_ha_discovery": True,
            "mqtt_retain_state": True,
            "notify_enabled": False,
            "notify_stale_data_seconds": 120,
            "notify_warning_repeat_caution_seconds": 21600,
            "notify_warning_repeat_warning_seconds": 3600,
            "notify_warning_repeat_critical_seconds": 900,
        }
        live = {
            "ok": True,
            "availability": "online",
            "monitor_state": "running",
            "stale": "OFF",
            "stale_reason": "Fresh",
            "last_analog_read": "2026-05-17 20:00:00",
            "last_warn_read": "2026-05-17 20:00:01",
            "analog_age_seconds": 1,
            "warn_age_seconds": 1,
            "overall_status": "Healthy",
            "overall_class": "healthy",
            "layout": "1 pack(s), 16 cells total",
            "bms_sn": "TEST",
            "base_topic": "pacebms",
            "fetched_at": "now",
            "error": "",
            "severity_summary": {},
            "pack_count": 1,
            "total_cells": 16,
            "warning_count": 0,
            "packs": [{
                "id": "01",
                "cell_count": 16,
                "soc": "95",
                "soh": "99",
                "cycles": "42",
                "remaining_capacity_ah": "160",
                "full_capacity_ah": "200",
                "design_capacity_ah": "200",
                "voltage": "54.0",
                "current": "1.0",
                "delta": "12",
                "temperatures": [25, 26],
                "warnings": "Normal",
                "severity_class": "healthy",
                "severity_label": "Normal",
                "highest_cell": {"number": "01", "voltage": "3.400"},
                "lowest_cell": {"number": "02", "voltage": "3.388"},
            }],
        }

        with (
            patch("web_config.load_options", return_value=(options, "")),
            patch("web_config.fetch_mqtt_snapshot", return_value=live),
            patch("web_config.load_events", return_value=[]),
            patch("web_config.load_monitor_health", return_value={
                "updated_at": 1000,
                "state": "running",
                "health_timeout_seconds": 60,
            }),
            patch("web_config.time.time", return_value=1001),
        ):
            response = web_config.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"User view", response.data)
        self.assertIn(b"Battery Confidence", response.data)

    def test_diagnostics_battery_configuration_includes_cycles(self):
        options = {
            "connection_type": "Serial",
            "bms_serial": "/dev/ttyUSB0",
            "scan_interval": 5,
            "mqtt_host": "192.168.1.10",
            "mqtt_port": 1883,
            "mqtt_ha_discovery": True,
            "mqtt_retain_state": True,
            "notify_enabled": False,
            "notify_stale_data_seconds": 120,
            "notify_warning_repeat_caution_seconds": 21600,
            "notify_warning_repeat_warning_seconds": 3600,
            "notify_warning_repeat_critical_seconds": 900,
        }
        live = {
            "ok": True,
            "availability": "online",
            "monitor_state": "running",
            "stale": "OFF",
            "stale_reason": "Fresh",
            "last_analog_read": "2026-05-17 20:00:00",
            "last_warn_read": "2026-05-17 20:00:01",
            "analog_age_seconds": 1,
            "warn_age_seconds": 1,
            "overall_status": "Healthy",
            "overall_class": "healthy",
            "layout": "1 pack(s), 16 cells total",
            "bms_sn": "TEST",
            "pack_sn": "PACKTEST",
            "bms_version": "P16S",
            "base_topic": "pacebms",
            "fetched_at": "now",
            "error": "",
            "severity_summary": {},
            "pack_count": 1,
            "total_cells": 16,
            "warning_count": 0,
            "packs": [{
                "id": "01",
                "cell_count": 16,
                "soc": "95",
                "soh": "99",
                "cycles": "42",
                "voltage": "54.0",
                "current": "1.0",
                "delta": "12",
                "warnings": "Normal",
                "severity_class": "healthy",
                "severity_label": "Normal",
                "highest_cell": {"number": "01", "voltage": "3.400"},
                "lowest_cell": {"number": "02", "voltage": "3.388"},
            }],
        }

        with (
            patch("web_config.load_options", return_value=(options, "")),
            patch("web_config.fetch_mqtt_snapshot", return_value=live),
            patch("web_config.load_events", return_value=[]),
            patch("web_config.load_monitor_health", return_value={
                "updated_at": 1000,
                "state": "running",
                "health_timeout_seconds": 60,
            }),
            patch("web_config.time.time", return_value=1001),
        ):
            response = web_config.app.test_client().get("/?tab=diagnostics")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Battery Configuration", response.data)
        self.assertIn(b"Cycles", response.data)
        self.assertIn(b"42", response.data)
        self.assertIn(b"Max Cycles", response.data)
        self.assertIn(b"Lowest SOH", response.data)
        self.assertIn(b"Average SOC", response.data)
        self.assertIn(b"Diagnostics loaded from current retained MQTT values. Auto-refresh runs every 15 seconds", response.data)

    def test_health_endpoint_fails_when_monitor_heartbeat_is_stale(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_path = web_config.MONITOR_HEALTH_PATH
            web_config.MONITOR_HEALTH_PATH = os.path.join(tmpdir, "monitor_health.json")
            try:
                with open(web_config.MONITOR_HEALTH_PATH, "w", encoding="utf-8") as f:
                    json.dump({
                        "updated_at": 1000,
                        "state": "running",
                        "health_timeout_seconds": 60,
                    }, f)

                with (
                    patch("web_config.time.time", return_value=1100),
                    patch("web_config.jsonify", side_effect=lambda payload: payload),
                ):
                    payload, status = web_config.health()

                self.assertEqual(status, 503)
                self.assertEqual(payload["status"], "unhealthy")
                self.assertEqual(payload["heartbeat_age_seconds"], 100)
            finally:
                web_config.MONITOR_HEALTH_PATH = original_path


if __name__ == "__main__":
    unittest.main()
