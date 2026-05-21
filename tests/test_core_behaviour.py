import unittest
import importlib.util
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
import types
from datetime import datetime
from pathlib import Path
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
import battery_profiles
import standalone_config
import web_config
import bms_live


def build_pace_response(info: bytes = b"ABCD") -> bytes:
    header = b"\x7e" + b"25" + b"01" + b"46" + b"00"
    lenid = bytes(format(len(info), "03X"), "ASCII")
    lchksum = b"0" if lenid == b"000" else bytes(bms_monitor.lchksum_calc(lenid), "ASCII")
    body = header + lchksum + lenid + info
    return body + bytes(bms_monitor.chksum_calc(body), "ASCII") + b"\r"


class PaceFrameTests(unittest.TestCase):
    def test_debug_output_is_normalized_for_monitor_runtime(self):
        self.assertEqual(bms_monitor.get_debug_output({"debug_output": "3"}), 3)
        self.assertEqual(bms_monitor.get_debug_output({"debug_output": "-1"}), 0)
        self.assertEqual(bms_monitor.get_debug_output({"debug_output": "9"}), 3)
        self.assertEqual(bms_monitor.get_debug_output({"debug_output": "bad"}), 0)

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


class MonitorRuntimeResilienceTests(unittest.TestCase):
    def setUp(self):
        bms_monitor._publish_cache.clear()

    def tearDown(self):
        bms_monitor._publish_cache.clear()

    def test_setup_mqtt_returns_client_when_initial_connect_fails(self):
        class FakeMqttClient:
            def __init__(self, *args, **kwargs):
                self.loop_started = False

            def will_set(self, *args, **kwargs):
                pass

            def username_pw_set(self, *args, **kwargs):
                pass

            def connect(self, *args, **kwargs):
                raise OSError("broker offline")

            def loop_start(self):
                self.loop_started = True

        config = {
            "mqtt_base_topic": "pacebms",
            "mqtt_user": "user",
            "mqtt_password": "password",
            "mqtt_host": "192.168.1.10",
            "mqtt_port": 1883,
        }

        with patch("bms_monitor.mqtt.Client", FakeMqttClient):
            client = bms_monitor.setup_mqtt(config, "TESTSN")

        self.assertIsInstance(client, FakeMqttClient)
        self.assertFalse(client.loop_started)

    def test_initialize_bms_identity_retries_without_exiting_when_serial_missing(self):
        with (
            patch("bms_monitor.bms_connect", return_value=(None, False)) as connect,
            patch("bms_monitor.write_monitor_health") as health,
            patch("bms_monitor.time.sleep"),
        ):
            result = bms_monitor.initialize_bms_identity({}, retry_seconds=0, max_attempts=2)

        self.assertEqual(result, (None, None, None, None))
        self.assertEqual(connect.call_count, 2)
        self.assertEqual(health.call_count, 2)

    def test_mqtt_publish_does_not_cache_when_client_is_disconnected(self):
        class FakeMqttClient:
            def is_connected(self):
                return False

            def publish(self, *args, **kwargs):
                raise AssertionError("publish should not be called while disconnected")

        sent = bms_monitor.mqtt_publish(
            FakeMqttClient(),
            "pacebms/test",
            "123",
            retain=True,
        )

        self.assertFalse(sent)
        self.assertNotIn("pacebms/test", bms_monitor._publish_cache)

    def test_mqtt_publish_caches_only_after_successful_publish(self):
        class FakeMqttClient:
            def __init__(self):
                self.published = []

            def is_connected(self):
                return True

            def publish(self, topic, value, qos=0, retain=False):
                self.published.append((topic, value, qos, retain))

        client = FakeMqttClient()

        first = bms_monitor.mqtt_publish(client, "pacebms/test", "123", retain=True)
        second = bms_monitor.mqtt_publish(client, "pacebms/test", "123", retain=True)

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(client.published, [("pacebms/test", "123", 0, True)])
        self.assertEqual(bms_monitor._publish_cache["pacebms/test"], "123")


class StandaloneDockerConfigTests(unittest.TestCase):
    def test_standalone_bootstrap_creates_options_from_defaults_and_env(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text(
                """
options:
  bms_serial: /dev/ttyUSB0
  bms_baudrate: 9600
  scan_interval: 5
  mqtt_host: 192.168.1.10
  mqtt_port: 1883
  mqtt_password: placeholder
  notify_enabled: true
  debug_output: 0
""".strip(),
                encoding="utf-8",
            )

            old_data_dir = standalone_config.DATA_DIR
            old_options_path = standalone_config.OPTIONS_PATH
            old_config_path = standalone_config.ADDON_CONFIG_PATH
            try:
                standalone_config.DATA_DIR = data_dir
                standalone_config.OPTIONS_PATH = data_dir / "options.json"
                standalone_config.ADDON_CONFIG_PATH = config_path
                with patch.dict(os.environ, {
                    "PACEBMS_MQTT_HOST": "10.0.0.5",
                    "PACEBMS_SCAN_INTERVAL": "7",
                    "PACEBMS_NOTIFY_ENABLED": "false",
                }, clear=False):
                    created = standalone_config.ensure_standalone_options()

                self.assertTrue(created)
                saved = json.loads((data_dir / "options.json").read_text(encoding="utf-8"))
                self.assertEqual(saved["mqtt_host"], "10.0.0.5")
                self.assertEqual(saved["scan_interval"], 7)
                self.assertFalse(saved["notify_enabled"])
            finally:
                standalone_config.DATA_DIR = old_data_dir
                standalone_config.OPTIONS_PATH = old_options_path
                standalone_config.ADDON_CONFIG_PATH = old_config_path

    def test_standalone_bootstrap_does_not_overwrite_existing_options(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            options_path = data_dir / "options.json"
            options_path.write_text('{"mqtt_host": "existing"}', encoding="utf-8")

            old_data_dir = standalone_config.DATA_DIR
            old_options_path = standalone_config.OPTIONS_PATH
            try:
                standalone_config.DATA_DIR = data_dir
                standalone_config.OPTIONS_PATH = options_path
                created = standalone_config.ensure_standalone_options()

                self.assertFalse(created)
                self.assertEqual(json.loads(options_path.read_text(encoding="utf-8"))["mqtt_host"], "existing")
            finally:
                standalone_config.DATA_DIR = old_data_dir
                standalone_config.OPTIONS_PATH = old_options_path


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

    def test_low_power_detail_does_not_create_new_low_voltage_family(self):
        self.assertEqual(
            bms_monitor.normalize_warning_family(
                "cell 4 Below lower limit, Low cell voltage, Low power warning"
            ),
            "Low cell voltage",
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
            "notify_warning_repeat_critical_seconds": 1800,
        }

        self.assertEqual(bms_monitor.warning_repeat_seconds_for_severity(config, "caution"), 21600)
        self.assertEqual(bms_monitor.warning_repeat_seconds_for_severity(config, "warning"), 3600)
        self.assertEqual(bms_monitor.warning_repeat_seconds_for_severity(config, "critical"), 1800)

    def test_warning_cooldown_survives_brief_clear_flicker(self):
        previous_state = {
            "family": "High cell voltage | High pack voltage",
            "active": False,
            "last_sent": 100.0,
            "severity": "normal",
            "telegram_sent_active": False,
        }

        self.assertTrue(
            bms_monitor.warning_previous_sent_for_family(
                previous_state,
                "High cell voltage | High pack voltage",
            )
        )
        self.assertTrue(
            bms_monitor.warning_same_cooldown_family(
                previous_state,
                "High cell voltage | High pack voltage",
            )
        )
        self.assertFalse(
            bms_monitor.warning_same_cooldown_family(
                previous_state,
                "Low cell voltage",
            )
        )

    def test_warning_telegram_policy_filters_bms_warning_below_reference(self):
        pack = bms_monitor.PackData(
            pack_number=1,
            cells=13,
            temps=0,
            v_cells=[4160] * 13,
            v_pack=54.08,
            soc=99.0,
            soh=90.0,
        )
        config = {
            "notify_bms_warning_policy": "user_reference_or_critical",
            "notify_cell_high_warn_voltage": 4.20,
            "notify_cell_low_warn_voltage": 3.00,
            "notify_cell_delta_warn_mv": 100,
            "notify_alert_cell_high_voltage": True,
            "notify_alert_pack_high_voltage": True,
        }

        allowed, reason = bms_monitor.warning_telegram_allowed(
            config,
            "Warning State 1: Above cell volt warn | Above total volt warn",
            pack,
            "caution",
        )

        self.assertFalse(allowed)
        self.assertIn("no enabled user reference exceeded", reason)

    def test_effective_warning_references_use_user_values_in_auto_profile(self):
        refs = battery_profiles.effective_warning_references(
            {
                "battery_profile": "auto",
                "notify_cell_high_warn_voltage": 4.13,
                "notify_cell_low_warn_voltage": 3.00,
                "notify_cell_delta_warn_mv": 50,
                "notify_temp_high_warn_c": 32,
                "notify_temp_low_warn_c": 10,
            },
            13,
        )

        self.assertEqual(refs["profile_label"], "P13S / Hubble AM2 51V")
        self.assertEqual(refs["source"], "user_configured")
        self.assertAlmostEqual(refs["cell_high"], 4.13)
        self.assertAlmostEqual(refs["pack_high"], 53.69)
        self.assertAlmostEqual(refs["profile_cell_high"], 4.20)
        self.assertAlmostEqual(refs["profile_pack_high"], 54.60)

    def test_warning_telegram_policy_allows_user_reference_crossing(self):
        pack = bms_monitor.PackData(
            pack_number=1,
            cells=13,
            temps=0,
            v_cells=[4210] * 13,
            v_pack=54.73,
            soc=99.0,
            soh=90.0,
        )
        config = {
            "notify_bms_warning_policy": "user_reference_or_critical",
            "notify_cell_high_warn_voltage": 4.20,
            "notify_cell_low_warn_voltage": 3.00,
            "notify_cell_delta_warn_mv": 100,
            "notify_alert_cell_high_voltage": True,
        }

        allowed, reason = bms_monitor.warning_telegram_allowed(
            config,
            "Warning State 1: Above cell volt warn",
            pack,
            "critical",
        )

        self.assertTrue(allowed)
        self.assertIn("high cell", reason)

    def test_warning_telegram_policy_uses_user_high_reference_not_profile_default(self):
        pack = bms_monitor.PackData(
            pack_number=1,
            cells=13,
            temps=0,
            v_cells=[4158] * 13,
            v_pack=54.08,
            soc=99.0,
            soh=90.0,
        )
        config = {
            "battery_profile": "auto",
            "notify_bms_warning_policy": "user_reference_or_critical",
            "notify_cell_high_warn_voltage": 4.13,
            "notify_cell_low_warn_voltage": 3.00,
            "notify_cell_delta_warn_mv": 100,
            "notify_alert_cell_high_voltage": True,
        }

        allowed, reason = bms_monitor.warning_telegram_allowed(
            config,
            "Warning State 1: Above cell volt warn",
            pack,
            "warning",
        )

        self.assertTrue(allowed)
        self.assertIn("high cell", reason)

    def test_warning_telegram_policy_respects_reference_row_toggle(self):
        pack = bms_monitor.PackData(
            pack_number=1,
            cells=13,
            temps=0,
            v_cells=[4210] * 13,
            v_pack=54.73,
            soc=99.0,
            soh=90.0,
        )
        config = {
            "notify_bms_warning_policy": "user_reference_only",
            "notify_cell_high_warn_voltage": 4.20,
            "notify_cell_low_warn_voltage": 3.00,
            "notify_cell_delta_warn_mv": 100,
            "notify_alert_cell_high_voltage": False,
        }

        allowed, reason = bms_monitor.warning_telegram_allowed(
            config,
            "Warning State 1: Above cell volt warn",
            pack,
            "critical",
        )

        self.assertFalse(allowed)
        self.assertIn("user_reference_only", reason)

    def test_warning_telegram_policy_allows_bms_protection_in_default_policy(self):
        pack = bms_monitor.PackData(
            pack_number=1,
            cells=13,
            temps=0,
            v_cells=[4160] * 13,
            v_pack=54.08,
            soc=99.0,
            soh=90.0,
        )
        config = {
            "notify_bms_warning_policy": "user_reference_or_critical",
            "notify_cell_high_warn_voltage": 4.20,
            "notify_cell_low_warn_voltage": 3.00,
            "notify_cell_delta_warn_mv": 100,
        }

        allowed, reason = bms_monitor.warning_telegram_allowed(
            config,
            "Protection State 1: Above cell volt protect",
            pack,
            "critical",
        )

        self.assertTrue(allowed)
        self.assertIn("critical", reason.lower())

    def test_all_bms_warnings_policy_still_respects_reference_row_toggle(self):
        pack = bms_monitor.PackData(
            pack_number=1,
            cells=13,
            temps=0,
            v_cells=[4160] * 13,
            v_pack=54.08,
            soc=99.0,
            soh=90.0,
        )
        config = {
            "notify_bms_warning_policy": "all_bms_warnings",
            "notify_cell_high_warn_voltage": 4.20,
            "notify_cell_low_warn_voltage": 3.00,
            "notify_cell_delta_warn_mv": 100,
            "notify_alert_cell_high_voltage": False,
            "notify_alert_pack_high_voltage": False,
        }

        allowed, reason = bms_monitor.warning_telegram_allowed(
            config,
            "Warning State 1: Above cell volt warn | Above total volt warn",
            pack,
            "caution",
        )

        self.assertFalse(allowed)
        self.assertIn("disabled", reason)

    def test_escalated_same_family_forces_notification_past_raw_text_dedupe(self):
        notify = bms_notify.NotifyState({"notify_warnings": True})
        warning_text = "Warning State 1: Above cell volt warn"
        notify.last_warnings[1] = warning_text

        with patch("bms_notify.telegram_send") as telegram:
            bms_monitor.call_warning_notify(
                notify,
                1,
                warning_text,
                force=True,
                severity="critical",
                repeat=False,
            )

        telegram.assert_called_once()
        self.assertIn("BMS Warning (Critical)", telegram.call_args.args[1])

    def test_low_soc_startup_does_not_replay_already_crossed_thresholds(self):
        notify = bms_notify.NotifyState({
            "notify_enabled": True,
            "notify_soc_low": True,
            "notify_soc_high": False,
            "notify_soc_low_thresholds": "75,50,25,10",
        })

        with patch("bms_notify.telegram_send") as telegram:
            notify.on_soc_update(1, 60.0)
            notify.on_soc_update(1, 49.0)

        self.assertEqual(notify.soc_thresholds_hit[1], {75, 50})
        telegram.assert_called_once()
        self.assertIn("threshold: 50%", telegram.call_args.args[1])

    def test_fet_alert_cooldown_suppresses_noisy_off_flicker(self):
        notify = bms_notify.NotifyState({
            "notify_enabled": True,
            "notify_fet": True,
            "notify_alert_discharge_fet_off": True,
            "notify_fet_repeat_seconds": 1800,
        })

        with (
            patch("bms_notify.time.time", side_effect=[1000.0, 1100.0, 3001.0]),
            patch("bms_notify.telegram_send") as telegram,
        ):
            notify.on_fet_update(1, "ON", "ON")
            notify.on_fet_update(1, "ON", "OFF")
            notify.on_fet_update(1, "ON", "ON")
            notify.on_fet_update(1, "ON", "OFF")
            notify.on_fet_update(1, "ON", "ON")
            notify.on_fet_update(1, "ON", "OFF")

        self.assertEqual(telegram.call_count, 2)


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
            "notify_warning_repeat_critical_seconds": 1800,
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
            "notify_warning_repeat_critical_seconds": 1800,
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

    def test_bms_warning_telegram_matches_warning_intelligence_layout(self):
        notify = bms_notify.NotifyState({
            "notify_warning_detail_enabled": True,
            "notify_cell_high_warn_voltage": 4.20,
            "notify_cell_low_warn_voltage": 3.00,
            "notify_include_highest_and_lowest_cell": True,
            "notify_include_pack_voltage": True,
            "notify_include_soc_soh": True,
        })
        pack = types.SimpleNamespace(
            v_cells=[4163, 4176, 4168, 4169, 4170, 4171, 4172, 4200],
            t_cells=[],
            v_pack=54.377,
            soc=100.0,
            soh=90.3,
            cells=13,
            cell_max_diff=37,
            cycles=987,
        )

        message = notify._build_warning_detail(
            1,
            "cell 2 Above upper limit, cell 8 Above upper limit, Warning State 1: Above cell volt warn | Above total volt warn",
            pack,
        )

        self.assertIn("Quick Metrics", message)
        self.assertIn("BMS Reported Warning Details", message)
        self.assertNotIn("- Cell 02: 4.176 V | Ref: 4.20 V", message)
        self.assertIn("- Cell 08: 4.200 V | Ref: 4.20 V | Margin: 0.000 V below ref | At reference | Notify: On", message)
        self.assertNotIn("- Pack: 54.377 V | Ref: 54.60 V", message)
        self.assertIn("Battery profile: P13S / Hubble AM2 51V", message)
        self.assertIn("Reference Check", message)
        self.assertIn("Interpretation", message)
        self.assertIn("Suggested Action", message)

    def test_warning_detail_handles_generic_bms_warning_words(self):
        notify = bms_notify.NotifyState({
            "notify_warning_detail_enabled": True,
            "notify_warnings": True,
            "notify_cell_high_warn_voltage": 4.20,
            "notify_cell_low_warn_voltage": 3.00,
            "notify_include_all_cells_above_threshold": True,
            "notify_include_highest_and_lowest_cell": True,
            "notify_include_pack_voltage": True,
        })
        pack = types.SimpleNamespace(
            v_cells=[4163, 4176, 4168, 4169, 4170, 4171, 4172, 4200],
            t_cells=[],
            v_pack=54.377,
            soc=100.0,
            soh=90.3,
            cells=13,
            cell_max_diff=37,
            cycles=987,
        )

        message = notify._build_warning_detail(
            1,
            "cell 2 Above upper limit, cell 8 Above upper limit, Above cell voltage, Above total voltage",
            pack,
        )

        self.assertIn("Above upper limit:", message)
        self.assertNotIn("- Cell 02: 4.176 V | Ref: 4.20 V", message)
        self.assertIn("- Cell 08: 4.200 V | Ref: 4.20 V", message)
        self.assertNotIn("Pack voltage:", message)
        self.assertNotIn("- Pack: 54.377 V | Ref: 54.60 V", message)

    def test_p16_profile_uses_lfp_reference_defaults(self):
        notify = bms_notify.NotifyState({
            "notify_warning_detail_enabled": True,
            "battery_profile": "auto",
            "notify_warnings": True,
        })
        pack = types.SimpleNamespace(
            v_cells=[3440] * 16,
            t_cells=[],
            v_pack=55.000,
            soc=98.0,
            soh=100.0,
            cells=16,
            cell_max_diff=12,
            cycles=100,
        )

        message = notify._build_warning_detail(
            1,
            "Warning State 1: Above total volt warn",
            pack,
        )

        self.assertIn("Battery profile: P16S / Eenovance MANA LFP 51.2V", message)
        self.assertNotIn("- Pack: 55.000 V | Ref: 56.16 V", message)
        self.assertIn("No configured reference comparison matched this warning text.", message)

    def test_warning_detail_shows_pack_high_rows_above_reference(self):
        notify = bms_notify.NotifyState({
            "notify_warning_detail_enabled": True,
            "notify_warnings": True,
            "notify_cell_high_warn_voltage": 4.20,
            "notify_include_pack_voltage": True,
        })
        pack = types.SimpleNamespace(
            v_cells=[4157, 4140, 4140, 4140, 4140, 4140, 4140, 4140],
            t_cells=[],
            v_pack=58.822,
            soc=99.3,
            soh=88.5,
            cells=13,
            cell_max_diff=35,
            cycles=992,
        )

        message = notify._build_warning_detail(
            1,
            "Warning State 1: Above total volt warn",
            pack,
        )

        self.assertIn("Pack voltage:", message)
        self.assertIn("- Pack: 58.822 V | Ref: 54.60 V | Margin: 4.222 V above ref | Exceeded | Notify: On", message)

    def test_warning_detail_hides_low_cell_rows_above_reference(self):
        notify = bms_notify.NotifyState({
            "notify_warning_detail_enabled": True,
            "notify_warnings": True,
            "notify_cell_low_warn_voltage": 3.00,
            "notify_include_all_cells_below_threshold": True,
            "notify_include_pack_voltage": True,
        })
        pack = types.SimpleNamespace(
            v_cells=[4123, 4145, 4141, 4137, 4141, 4156, 4144, 4160],
            t_cells=[],
            v_pack=53.855,
            soc=99.7,
            soh=88.5,
            cells=13,
            cell_max_diff=36,
            cycles=992,
        )

        message = notify._build_warning_detail(
            1,
            "cell 1 Below lower limit | Low cell voltage | Low power warning",
            pack,
        )

        self.assertNotIn("Below lower limit:", message)
        self.assertNotIn("- Cell 01: 4.123 V | Ref: 3.00 V", message)
        self.assertIn("No configured reference comparison matched this warning text.", message)
        self.assertIn("BMS warning is active below configured reference.", message)

    def test_warning_detail_shows_low_cell_rows_below_reference(self):
        notify = bms_notify.NotifyState({
            "notify_warning_detail_enabled": True,
            "notify_warnings": True,
            "notify_cell_low_warn_voltage": 3.00,
            "notify_include_all_cells_below_threshold": True,
        })
        pack = types.SimpleNamespace(
            v_cells=[3493, 3480, 3475, 3465, 3440, 3492, 2984, 3488],
            t_cells=[],
            v_pack=44.474,
            soc=1.0,
            soh=88.4,
            cells=13,
            cell_max_diff=481,
            cycles=990,
        )

        message = notify._build_warning_detail(
            1,
            "cell 7 Below lower limit | Low cell voltage | Low power warning",
            pack,
        )

        self.assertIn("Below lower limit:", message)
        self.assertIn("- Cell 07: 2.984 V | Ref: 3.00 V | Margin: 0.016 V below ref | Exceeded | Notify: On", message)


class EnergyTrackingTests(unittest.TestCase):
    def test_energy_uses_elapsed_time_after_first_sample(self):
        state = bms_notify.NotifyState({})

        with patch("bms_notify.time.time", side_effect=[1000.0, 1010.0]):
            state.on_energy_update(1, voltage=50.0, current=10.0, scan_interval=5)
            state.on_energy_update(1, voltage=50.0, current=10.0, scan_interval=5)

        expected = 500.0 * (10.0 / 3600.0) / 1000.0
        self.assertAlmostEqual(state.kwh_charged[1], expected)
        self.assertEqual(state.kwh_discharged[1], 0.0)

    def test_energy_ignores_deadband_current(self):
        state = bms_notify.NotifyState({"daily_energy_current_deadband_a": 0.2})

        with patch("bms_notify.time.time", side_effect=[1000.0, 1010.0]):
            state.on_energy_update(1, voltage=50.0, current=0.1, scan_interval=5)
            state.on_energy_update(1, voltage=50.0, current=0.1, scan_interval=5)

        self.assertEqual(state.kwh_charged[1], 0.0)
        self.assertEqual(state.kwh_discharged[1], 0.0)

    def test_daily_summary_reports_no_measurable_energy(self):
        state = bms_notify.NotifyState({"notify_delta_window_start": "00:00", "notify_delta_window_end": "23:59"})
        state.on_soc_update(1, 80.0)
        state.on_soc_update(1, 81.0)
        state.on_daily_warning_observed(1, "Warning State 1: Above cell volt warn")
        state.worst_cell_dev[1] = {"cell": 1, "dev": 8.2, "time": "16:01", "volt": 4.135, "avg": 4.127}

        with patch("bms_notify.telegram_send") as send:
            state._send_daily_summary(1)

        message = send.call_args.args[1]
        self.assertIn("Energy movement: no measurable charge/discharge recorded today", message)
        self.assertIn("SOC: 80.0% -> 81.0% (+1.0%)", message)
        self.assertIn("Warnings today: Above cell voltage", message)

    def test_daily_summary_uses_sqlite_history_after_restart(self):
        state = bms_notify.NotifyState({"daily_energy_current_deadband_a": 0.2, "history_sample_seconds": 10})

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pacebms_metrics.db"
            with patch("bms_notify.HISTORY_DB_PATH", db_path):
                bms_notify.init_history_db(db_path)
                report_now = datetime(2026, 5, 20, 12, 0)
                now = int(report_now.timestamp())
                rows = [
                    (now - 20, 1, "01", 75.0, 50.0, -10.0, "cell 7 Below lower limit"),
                    (now - 10, 2, "01", 74.0, 49.5, -10.0, "cell 7 Below lower limit"),
                    (now - 20, 3, "02", 20.0, 48.0, 8.0, "Warning State 1: Above cell volt warn"),
                    (now - 10, 4, "02", 21.0, 48.5, 8.0, "Warning State 1: Above cell volt warn"),
                ]
                con = sqlite3.connect(db_path)
                try:
                    for ts, snapshot_id, pack_id, soc, voltage, current, warnings in rows:
                        con.execute(
                            """
                            INSERT INTO pack_metrics (
                                ts, snapshot_id, pack_id, soc, voltage, current, warnings
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (ts, snapshot_id, pack_id, soc, voltage, current, warnings),
                        )
                    for ts, snapshot_id, pack_id, cells in [
                        (now - 10, 2, "01", [3.50, 3.40, 3.49]),
                        (now - 10, 4, "02", [3.30, 3.35, 3.70]),
                    ]:
                        for cell_number, voltage in enumerate(cells, start=1):
                            con.execute(
                                "INSERT INTO cell_metrics (ts, snapshot_id, pack_id, cell_number, voltage) VALUES (?, ?, ?, ?, ?)",
                                (ts, snapshot_id, pack_id, cell_number, voltage),
                            )
                    con.commit()
                finally:
                    con.close()

                with patch("bms_notify.datetime") as dt_mock:
                    dt_mock.now.return_value = report_now
                    dt_mock.combine.side_effect = datetime.combine
                    dt_mock.fromtimestamp.side_effect = datetime.fromtimestamp
                    with patch("bms_notify.telegram_send") as send:
                        state._send_daily_summary(2)

        message = send.call_args.args[1]
        self.assertIn("Pack 01:", message)
        self.assertIn("Discharged:", message)
        self.assertIn("SOC: 75.0% -> 74.0% (-1.0%)", message)
        self.assertIn("cell 7 Below lower limit", message)
        self.assertIn("Pack 02:", message)
        self.assertIn("Charged:", message)
        self.assertIn("SOC: 20.0% -> 21.0% (+1.0%)", message)
        self.assertIn("Above cell voltage", message)

    def test_daily_summary_uses_sqlite_warning_events(self):
        state = bms_notify.NotifyState({"daily_energy_current_deadband_a": 0.2, "history_sample_seconds": 10})

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pacebms_metrics.db"
            with patch("bms_notify.HISTORY_DB_PATH", db_path):
                bms_notify.init_history_db(db_path)
                report_now = datetime(2026, 5, 20, 12, 0)
                now = int(report_now.timestamp())
                con = sqlite3.connect(db_path)
                try:
                    for snapshot_id, soc in [(1, 80.0), (2, 79.5)]:
                        con.execute(
                            """
                            INSERT INTO pack_metrics (
                                ts, snapshot_id, pack_id, soc, voltage, current, warnings
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (now - 10 + snapshot_id, snapshot_id, "01", soc, 50.0, -4.0, ""),
                        )
                    con.execute(
                        """
                        INSERT INTO warning_events (ts, snapshot_id, pack_id, severity, title, message)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            now - 5,
                            2,
                            "01",
                            "warning",
                            "BMS warning notification sent",
                            "cell 7 Below lower limit; sent by Telegram",
                        ),
                    )
                    con.commit()
                finally:
                    con.close()

                with patch("bms_notify.datetime") as dt_mock:
                    dt_mock.now.return_value = report_now
                    dt_mock.combine.side_effect = datetime.combine
                    dt_mock.fromtimestamp.side_effect = datetime.fromtimestamp
                    with patch("bms_notify.telegram_send") as send:
                        state._send_daily_summary(1)

        message = send.call_args.args[1]
        self.assertIn("Pack 01:", message)
        self.assertIn("Warnings today: cell 7 Below lower limit", message)

    def test_daily_summary_uses_sqlite_power_kw_for_energy_after_restart(self):
        state = bms_notify.NotifyState({"daily_energy_current_deadband_a": 0.2, "history_sample_seconds": 10})

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pacebms_metrics.db"
            with patch("bms_notify.HISTORY_DB_PATH", db_path):
                bms_notify.init_history_db(db_path)
                report_now = datetime(2026, 5, 20, 12, 0)
                now = int(report_now.timestamp())
                con = sqlite3.connect(db_path)
                try:
                    for ts, snapshot_id, power_kw in [
                        (now - 20, 1, None),
                        (now - 10, 2, 0.50),
                        (now, 3, -0.25),
                    ]:
                        con.execute(
                            """
                            INSERT INTO pack_metrics (
                                ts, snapshot_id, pack_id, soc, voltage, current, power_kw, warnings
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (ts, snapshot_id, "01", 80.0, None, None, power_kw, ""),
                        )
                    con.commit()
                finally:
                    con.close()

                with patch("bms_notify.datetime") as dt_mock:
                    dt_mock.now.return_value = report_now
                    dt_mock.combine.side_effect = datetime.combine
                    dt_mock.fromtimestamp.side_effect = datetime.fromtimestamp
                    with patch("bms_notify.telegram_send") as send:
                        state._send_daily_summary(1)

        message = send.call_args.args[1]
        self.assertIn("Charged:    0.001 kWh", message)
        self.assertIn("Discharged: 0.001 kWh", message)

    def test_daily_summary_uses_sqlite_warning_events_without_pack_samples(self):
        state = bms_notify.NotifyState({"daily_energy_current_deadband_a": 0.2, "history_sample_seconds": 10})
        state.on_daily_warning_observed(1, "Warning State 1: Above cell volt warn")

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pacebms_metrics.db"
            with patch("bms_notify.HISTORY_DB_PATH", db_path):
                bms_notify.init_history_db(db_path)
                report_now = datetime(2026, 5, 20, 12, 0)
                now = int(report_now.timestamp())
                con = sqlite3.connect(db_path)
                try:
                    con.execute(
                        """
                        INSERT INTO warning_events (ts, snapshot_id, pack_id, severity, title, message)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            now - 5,
                            10,
                            "02",
                            "critical",
                            "BMS warning notification sent",
                            "Protection State: Discharge MOS fault",
                        ),
                    )
                    con.commit()
                finally:
                    con.close()

                with patch("bms_notify.datetime") as dt_mock:
                    dt_mock.now.return_value = report_now
                    dt_mock.combine.side_effect = datetime.combine
                    dt_mock.fromtimestamp.side_effect = datetime.fromtimestamp
                    with patch("bms_notify.telegram_send") as send:
                        state._send_daily_summary(1)

        message = send.call_args.args[1]
        self.assertIn("Pack 02:", message)
        self.assertIn("Energy movement: no SQLite history samples recorded today", message)
        self.assertIn("Warnings today: Protection State: Discharge MOS fault", message)
        self.assertNotIn("Above cell voltage", message)

    def test_delta_report_uses_sqlite_history_after_restart(self):
        state = bms_notify.NotifyState({"notify_delta_window_start": "00:00", "notify_delta_window_end": "23:59"})

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pacebms_metrics.db"
            with patch("bms_notify.HISTORY_DB_PATH", db_path):
                bms_notify.init_history_db(db_path)
                report_now = datetime(2026, 5, 20, 12, 0)
                now = int(report_now.timestamp())
                con = sqlite3.connect(db_path)
                try:
                    for pack_id, snapshot_id, delta, high_cell, high_v, low_cell, low_v in [
                        ("01", 1, 120.0, "06", 3.50, "07", 3.38),
                        ("01", 2, 180.0, "06", 3.55, "07", 3.37),
                        ("02", 3, 90.0, "11", 3.48, "13", 3.39),
                    ]:
                        con.execute(
                            """
                            INSERT INTO pack_metrics (
                                ts, snapshot_id, pack_id, cell_delta_mv,
                                highest_cell, highest_cell_v, lowest_cell, lowest_cell_v
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (now, snapshot_id, pack_id, delta, high_cell, high_v, low_cell, low_v),
                        )
                    con.commit()
                finally:
                    con.close()

                with patch("bms_notify.datetime") as dt_mock:
                    dt_mock.now.return_value = report_now
                    dt_mock.combine.side_effect = datetime.combine
                    dt_mock.fromtimestamp.side_effect = datetime.fromtimestamp
                    with patch("bms_notify.telegram_send") as send:
                        state._send_delta_report(2)

        message = send.call_args.args[1]
        self.assertIn("Pack 01:", message)
        self.assertIn("Worst delta: 180.0 mV", message)
        self.assertIn("Highest: Cell 06 3.550 V", message)
        self.assertIn("Lowest: Cell 07 3.370 V", message)
        self.assertIn("Pack 02:", message)
        self.assertIn("Worst delta: 90.0 mV", message)

    def test_delta_report_uses_previous_overnight_sqlite_window_after_midnight(self):
        state = bms_notify.NotifyState({"notify_delta_window_start": "22:00", "notify_delta_window_end": "02:00"})

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pacebms_metrics.db"
            with patch("bms_notify.HISTORY_DB_PATH", db_path):
                bms_notify.init_history_db(db_path)
                report_now = datetime(2026, 5, 20, 1, 30)
                in_window = int(datetime(2026, 5, 19, 23, 30).timestamp())
                future_window = int(datetime(2026, 5, 20, 23, 30).timestamp())
                con = sqlite3.connect(db_path)
                try:
                    for ts, snapshot_id, delta in [
                        (in_window, 1, 150.0),
                        (future_window, 2, 300.0),
                    ]:
                        con.execute(
                            """
                            INSERT INTO pack_metrics (
                                ts, snapshot_id, pack_id, cell_delta_mv,
                                highest_cell, highest_cell_v, lowest_cell, lowest_cell_v
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (ts, snapshot_id, "01", delta, "08", 3.55, "09", 3.40),
                        )
                    con.commit()
                finally:
                    con.close()

                with patch("bms_notify.datetime") as dt_mock:
                    dt_mock.now.return_value = report_now
                    dt_mock.combine.side_effect = datetime.combine
                    dt_mock.fromtimestamp.side_effect = datetime.fromtimestamp
                    with patch("bms_notify.telegram_send") as send:
                        state._send_delta_report(1)

        message = send.call_args.args[1]
        self.assertIn("Worst delta: 150.0 mV", message)
        self.assertNotIn("300.0 mV", message)

    def test_delta_report_includes_sqlite_pack_ids_beyond_runtime_pack_count(self):
        state = bms_notify.NotifyState({"notify_delta_window_start": "00:00", "notify_delta_window_end": "23:59"})

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "pacebms_metrics.db"
            with patch("bms_notify.HISTORY_DB_PATH", db_path):
                bms_notify.init_history_db(db_path)
                report_now = datetime(2026, 5, 20, 12, 0)
                now = int(report_now.timestamp())
                con = sqlite3.connect(db_path)
                try:
                    con.execute(
                        """
                        INSERT INTO pack_metrics (
                            ts, snapshot_id, pack_id, cell_delta_mv,
                            highest_cell, highest_cell_v, lowest_cell, lowest_cell_v
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (now, 1, "03", 210.0, "10", 3.56, "11", 3.35),
                    )
                    con.commit()
                finally:
                    con.close()

                with patch("bms_notify.datetime") as dt_mock:
                    dt_mock.now.return_value = report_now
                    dt_mock.combine.side_effect = datetime.combine
                    dt_mock.fromtimestamp.side_effect = datetime.fromtimestamp
                    with patch("bms_notify.telegram_send") as send:
                        state._send_delta_report(1)

        message = send.call_args.args[1]
        self.assertIn("Pack 03:", message)
        self.assertIn("Worst delta: 210.0 mV", message)


class HealthEndpointTests(unittest.TestCase):
    def setUp(self):
        web_config.clear_live_snapshot_cache()

    def tearDown(self):
        web_config.clear_live_snapshot_cache()

    def _form_from_options(self, options):
        form = {}
        for keys in web_config.GROUPS.values():
            for key in keys:
                value = options.get(key, web_config.DEFAULT_OPTION_VALUES.get(key, ""))
                if isinstance(value, bool):
                    if value:
                        form[key] = "on"
                elif key in web_config.SENSITIVE_KEYS:
                    form[key] = ""
                else:
                    form[key] = str(value)
        return form

    def _operational_live_snapshot(self):
        return {
            "ok": True,
            "source": "live_serial",
            "data_source": "Live serial",
            "snapshot_id": 123456789,
            "availability": "online",
            "monitor_state": "running",
            "stale": "OFF",
            "stale_reason": "Fresh",
            "last_analog_read": "2026-05-21 12:00:00",
            "last_warn_read": "2026-05-21 12:00:01",
            "analog_age_seconds": 1,
            "warn_age_seconds": 1,
            "overall_status": "Healthy",
            "overall_class": "healthy",
            "layout": "2 pack(s), 26 cells total - Pack 01: 13 cells, Pack 02: 13 cells",
            "bms_sn": "HL2107001569",
            "bms_version": "P13S120A-12290-2.50",
            "base_topic": "pacebms",
            "fetched_at": "2026-05-21 12:00:02",
            "error": "",
            "severity_summary": {"Normal": 2},
            "pack_count": 2,
            "total_cells": 26,
            "warning_count": 0,
            "packs": [
                {
                    "id": "01",
                    "cell_count": 13,
                    "role": "Master",
                    "serial": "HL2107001569",
                    "soc": "94.96",
                    "soh": "88.54",
                    "cycles": "992",
                    "remaining_capacity_ah": "84",
                    "full_capacity_ah": "89",
                    "design_capacity_ah": "100",
                    "voltage": "52.972",
                    "current": "-18.71",
                    "power_kw": "-0.99",
                    "delta": "33",
                    "temperatures": [26.7],
                    "warnings": "Normal",
                    "severity_class": "healthy",
                    "severity_label": "Normal",
                    "highest_cell": {"number": "08", "voltage": "4.092"},
                    "lowest_cell": {"number": "01", "voltage": "4.059"},
                    "cell_high_ref": "4.20",
                    "cell_low_ref": "3.00",
                    "pack_high_ref": "54.60",
                    "pack_low_ref": "39.00",
                    "charge_fet": "ON",
                    "discharge_fet": "ON",
                    "fully": "OFF",
                    "cells": [
                        {"number": f"{idx:02d}", "voltage": f"{4.060 + idx / 1000:.3f}", "labels": [], "class": "cell-normal"}
                        for idx in range(1, 14)
                    ],
                    "reference_checks": ["No active BMS warning."],
                },
                {
                    "id": "02",
                    "cell_count": 13,
                    "role": "Slave",
                    "serial": "N/A",
                    "soc": "97.58",
                    "soh": "90.07",
                    "cycles": "511",
                    "remaining_capacity_ah": "88",
                    "full_capacity_ah": "90",
                    "design_capacity_ah": "100",
                    "voltage": "53.004",
                    "current": "-17.08",
                    "power_kw": "-0.91",
                    "delta": "45",
                    "temperatures": [26.4],
                    "warnings": "Normal",
                    "severity_class": "healthy",
                    "severity_label": "Normal",
                    "highest_cell": {"number": "01", "voltage": "4.088"},
                    "lowest_cell": {"number": "13", "voltage": "4.043"},
                    "cell_high_ref": "4.20",
                    "cell_low_ref": "3.00",
                    "pack_high_ref": "54.60",
                    "pack_low_ref": "39.00",
                    "charge_fet": "ON",
                    "discharge_fet": "ON",
                    "fully": "OFF",
                    "cells": [
                        {"number": f"{idx:02d}", "voltage": f"{4.040 + idx / 1000:.3f}", "labels": [], "class": "cell-normal"}
                        for idx in range(1, 14)
                    ],
                    "reference_checks": ["No active BMS warning."],
                },
            ],
        }

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
            "notify_warning_repeat_critical_seconds": 1800,
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
        self.assertIn(b"Local History Storage", response.data)
        history_pos = response.data.find(b"Local History Storage")
        tests_pos = response.data.find(b"Setup Tests")
        checklist_pos = response.data.find(b"Setup Checklist")
        self.assertTrue(history_pos < tests_pos < checklist_pos)
        self.assertIn(b"Refresh setup", response.data)
        self.assertIn(b"setup-refresh-marker", response.data)

    def test_config_page_renders_battery_reference_table(self):
        options = dict(web_config.DEFAULT_OPTION_VALUES)
        live = {
            "ok": True,
            "availability": "online",
            "monitor_state": "running",
            "stale": "OFF",
            "overall_status": "Healthy",
            "overall_class": "healthy",
            "layout": "1 pack(s), 16 cells total",
            "bms_sn": "TEST",
            "base_topic": "pacebms",
            "fetched_at": "now",
            "error": "",
            "packs": [{
                "id": "01",
                "cell_count": 16,
                "highest_cell": {"number": "08", "voltage": "3.440"},
                "lowest_cell": {"number": "01", "voltage": "3.390"},
                "delta": "50",
                "temperatures": [28.0, 29.0],
            }],
        }

        with (
            patch("web_config.load_options", return_value=(options, "")),
            patch("web_config.get_page_live_snapshot", return_value=live),
            patch("web_config.load_events", return_value=[]),
        ):
            response = web_config.app.test_client().get("/?tab=config")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Battery Profile & Alert References", response.data)
        self.assertIn(b"Profile reference", response.data)
        self.assertIn(b"Measured", response.data)
        self.assertIn(b"User defined", response.data)
        self.assertIn(b"Telegram alert", response.data)
        self.assertIn(b"notify_bms_warning_policy", response.data)
        self.assertIn(b"notify_alert_cell_high_voltage", response.data)
        self.assertIn(b"Pack high voltage", response.data)
        self.assertIn(b"FET Notifications", response.data)
        self.assertIn(b"Scheduled Reports", response.data)

    def test_config_page_renders_every_config_group_field(self):
        options = dict(web_config.DEFAULT_OPTION_VALUES)
        live = {
            "ok": True,
            "availability": "online",
            "monitor_state": "running",
            "stale": "OFF",
            "overall_status": "Healthy",
            "overall_class": "healthy",
            "layout": "1 pack(s), 13 cells total",
            "bms_sn": "TEST",
            "base_topic": "pacebms",
            "fetched_at": "now",
            "error": "",
            "packs": [{
                "id": "01",
                "cell_count": 13,
                "highest_cell": {"number": "08", "voltage": "4.100"},
                "lowest_cell": {"number": "01", "voltage": "4.000"},
                "delta": "100",
                "temperatures": [28.0],
            }],
        }

        with (
            patch("web_config.load_options", return_value=(options, "")),
            patch("web_config.get_page_live_snapshot", return_value=live),
            patch("web_config.load_events", return_value=[]),
        ):
            response = web_config.app.test_client().get("/?tab=config")

        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")
        missing = []
        for keys in web_config.GROUPS.values():
            for key in keys:
                if f'name="{key}"' not in html:
                    missing.append(key)
        self.assertEqual(missing, [])

    def test_config_info_buttons_have_help_for_every_card(self):
        missing_fallback = [group for group in web_config.GROUPS if group not in web_config.CARD_HELP]
        self.assertEqual(missing_fallback, [])

        template = Path("templates/index.html").read_text(encoding="utf-8")
        missing_modal = []
        for group in web_config.GROUPS:
            if f'"{group}": {{' not in template:
                missing_modal.append(group)

        self.assertEqual(missing_modal, [])
        self.assertIn("History & Live Data Settings", template)
        self.assertIn("monitor-owned serial snapshot", template)
        self.assertNotIn("latest retained MQTT value from the BMS", template)

    def test_build_options_from_form_adds_upgraded_defaults_and_preserves_secrets(self):
        current_options = dict(web_config.DEFAULT_OPTION_VALUES)
        current_options["telegram_bot_token"] = "123456:real-token"
        current_options["telegram_chat_id"] = "987654"
        current_options.pop("battery_profile", None)
        current_options.pop("daily_energy_current_deadband_a", None)
        form = self._form_from_options(dict(web_config.DEFAULT_OPTION_VALUES))
        form["telegram_bot_token"] = ""
        form["telegram_chat_id"] = ""
        form["scan_interval"] = "12"
        form["daily_energy_current_deadband_a"] = "0.4"

        new_options = web_config.build_options_from_form(form, current_options)

        self.assertEqual(new_options["telegram_bot_token"], "123456:real-token")
        self.assertEqual(new_options["telegram_chat_id"], "987654")
        self.assertEqual(new_options["battery_profile"], web_config.DEFAULT_OPTION_VALUES["battery_profile"])
        self.assertEqual(new_options["daily_energy_current_deadband_a"], 0.4)
        self.assertEqual(new_options["scan_interval"], 12)

    def test_build_options_from_form_accepts_decimal_comma_fields(self):
        current_options = dict(web_config.DEFAULT_OPTION_VALUES)
        form = self._form_from_options(current_options)
        form["daily_energy_current_deadband_a"] = "0,2"
        form["notify_cell_high_warn_voltage"] = "4,20"
        form["notify_cell_low_warn_voltage"] = "3,00"

        new_options = web_config.build_options_from_form(form, current_options)

        self.assertEqual(new_options["daily_energy_current_deadband_a"], 0.2)
        self.assertEqual(new_options["notify_cell_high_warn_voltage"], 4.2)
        self.assertEqual(new_options["notify_cell_low_warn_voltage"], 3.0)

    def test_percentage_threshold_fields_remain_integer_schema_values(self):
        current_options = dict(web_config.DEFAULT_OPTION_VALUES)
        form = self._form_from_options(current_options)
        form["notify_soc_high_threshold"] = "99"
        form["notify_soc_high_reset"] = "96"
        form["notify_soh_threshold"] = "94"

        new_options = web_config.build_options_from_form(form, current_options)

        self.assertEqual(new_options["notify_soc_high_threshold"], 99)
        self.assertEqual(new_options["notify_soc_high_reset"], 96)
        self.assertEqual(new_options["notify_soh_threshold"], 94)

    def test_config_yaml_options_schema_and_form_groups_stay_aligned(self):
        with Path("config.yaml").open(encoding="utf-8") as handle:
            config = web_config.yaml.safe_load(handle)

        options = set((config.get("options") or {}).keys())
        schema = set((config.get("schema") or {}).keys())
        grouped = []
        for keys in web_config.GROUPS.values():
            grouped.extend(keys)
        grouped_set = set(grouped)

        self.assertEqual(sorted(options - schema), [])
        self.assertEqual(sorted(schema - options), [])
        self.assertEqual(sorted(options - grouped_set - web_config.DEPRECATED_OPTION_KEYS), [])
        self.assertEqual(sorted(grouped_set - options), [])
        self.assertEqual(sorted([key for key in grouped_set if grouped.count(key) > 1]), [])

    def test_all_config_fields_round_trip_from_form(self):
        current_options = dict(web_config.DEFAULT_OPTION_VALUES)
        sample_values = {
            "connection_type": "Serial",
            "bms_serial": "/dev/ttyUSB-test",
            "bms_baudrate": "19200",
            "scan_interval": "9",
            "mqtt_host": "192.168.1.20",
            "mqtt_port": "1884",
            "mqtt_user": "new-user",
            "mqtt_password": "new-password",
            "mqtt_base_topic": "pacebms_test",
            "mqtt_ha_discovery_topic": "homeassistant_test",
            "state_force_republish_seconds": "301",
            "warn_force_republish_seconds": "302",
            "debug_output": "1",
            "zero_pad_number_cells": "3",
            "zero_pad_number_packs": "3",
            "telegram_bot_token": "123456:new-token",
            "telegram_chat_id": "123456789",
            "notify_soc_low_thresholds": "80,60,40,20",
            "notify_soc_high_threshold": "99",
            "notify_soc_high_reset": "96",
            "notify_soh_threshold": "94",
            "notify_retry_count": "2",
            "notify_stale_data_seconds": "180",
            "notify_stale_data_repeat_seconds": "1900",
            "notify_warning_repeat_seconds": "1900",
            "notify_warning_repeat_caution_seconds": "22000",
            "notify_warning_repeat_warning_seconds": "3700",
            "notify_warning_repeat_critical_seconds": "1000",
            "notify_daily_summary_time": "18:30",
            "notify_delta_report_time": "11:15",
            "notify_delta_window_start": "01:00",
            "notify_delta_window_end": "11:00",
            "daily_energy_current_deadband_a": "0,3",
            "battery_profile": "custom",
            "notify_bms_warning_policy": "user_reference_only",
            "notify_cell_high_warn_voltage": "4,10",
            "notify_cell_low_warn_voltage": "3,10",
            "notify_cell_delta_warn_mv": "120",
            "notify_temp_high_warn_c": "50",
            "notify_temp_low_warn_c": "5",
        }
        expected = {
            "daily_energy_current_deadband_a": 0.3,
            "notify_cell_high_warn_voltage": 4.1,
            "notify_cell_low_warn_voltage": 3.1,
        }

        for key in [item for keys in web_config.GROUPS.values() for item in keys]:
            with self.subTest(key=key):
                form = self._form_from_options(current_options)
                current_value = current_options.get(key, web_config.DEFAULT_OPTION_VALUES.get(key, ""))

                if isinstance(current_value, bool):
                    if current_value:
                        form.pop(key, None)
                        expected_value = False
                    else:
                        form[key] = "on"
                        expected_value = True
                else:
                    form[key] = sample_values.get(key, str(current_value))
                    expected_value = expected.get(key, web_config.parse_form_value(key, form[key], current_value))

                new_options = web_config.build_options_from_form(form, current_options)

                self.assertEqual(new_options[key], expected_value)
                self.assertEqual(web_config.validate_config_options(new_options), [])

    def test_debug_output_is_limited_to_supported_choices(self):
        current_options = dict(web_config.DEFAULT_OPTION_VALUES)
        current_options["debug_output"] = -1
        form = self._form_from_options(current_options)
        form["debug_output"] = "-1"

        new_options = web_config.build_options_from_form(form, current_options)

        self.assertEqual(new_options["debug_output"], 0)
        self.assertEqual(sorted(web_config.DEBUG_OUTPUT_CHOICES.keys()), [0, 1, 2, 3])
        self.assertEqual(web_config.INTEGER_FIELDS["debug_output"], (0, 3))

    def test_save_config_redirects_with_restart_message_after_successful_save(self):
        options = dict(web_config.DEFAULT_OPTION_VALUES)
        form = self._form_from_options(options)
        form["scan_interval"] = "14"

        with tempfile.TemporaryDirectory() as tmpdir:
            pending_path = str(Path(tmpdir) / "options.pending.json")
            with (
                patch("web_config.PENDING_OPTIONS_PATH", pending_path),
                patch("web_config.load_options", return_value=(options, "")),
                patch("web_config.create_config_backup", return_value=(True, "backup ok", "before-save.json")),
                patch("web_config.save_addon_options", return_value=(True, "Configuration saved to Home Assistant add-on options.")),
                patch("web_config.append_event"),
            ):
                response = web_config.app.test_client().post("/save-config", data=form)

        self.assertEqual(response.status_code, 303)
        location = response.headers["Location"]
        self.assertIn("tab=config", location)
        self.assertIn("Restart%20required%20for%20monitor%20runtime%20changes%20to%20apply", location)

    def test_save_config_stacks_pending_options_before_restart(self):
        runtime_options = dict(web_config.DEFAULT_OPTION_VALUES)
        pending_options = dict(runtime_options)
        pending_options["scan_interval"] = 14
        form = self._form_from_options(pending_options)
        form["bms_baudrate"] = "19200"

        with tempfile.TemporaryDirectory() as tmpdir:
            pending_path = str(Path(tmpdir) / "options.pending.json")
            with (
                patch("web_config.PENDING_OPTIONS_PATH", pending_path),
                patch("web_config.load_options", return_value=(runtime_options, "")),
                patch("web_config.create_config_backup", return_value=(True, "backup ok", "before-save.json")),
                patch("web_config.save_addon_options", return_value=(True, "Configuration saved to Home Assistant add-on options.")) as save_options,
                patch("web_config.append_event"),
            ):
                self.assertTrue(web_config.save_pending_options(pending_options))
                response = web_config.app.test_client().post("/save-config", data=form)

        self.assertEqual(response.status_code, 303)
        saved_options = save_options.call_args.args[0]
        self.assertEqual(saved_options["scan_interval"], 14)
        self.assertEqual(saved_options["bms_baudrate"], 19200)

    def test_config_tab_shows_pending_options_but_live_badge_uses_runtime(self):
        runtime_options = dict(web_config.DEFAULT_OPTION_VALUES)
        pending_options = dict(runtime_options)
        pending_options["scan_interval"] = 14
        live_snapshot = {
            "ok": True,
            "data_source": "Live serial",
            "packs": [],
            "pack_count": 0,
            "total_cells": 0,
            "warning_count": 0,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            pending_path = str(Path(tmpdir) / "options.pending.json")
            with (
                patch("web_config.PENDING_OPTIONS_PATH", pending_path),
                patch("web_config.load_options", return_value=(runtime_options, "")),
                patch("web_config.get_page_live_snapshot", return_value=live_snapshot),
            ):
                self.assertTrue(web_config.save_pending_options(pending_options))
                response = web_config.app.test_client().get("/?tab=config")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Pending saved options are being shown", response.data)
        self.assertIn(b"Live Serial", response.data)
        self.assertNotIn(b"No Live Data", response.data)
        self.assertIn(b'value="14"', response.data)

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
            "notify_warning_repeat_critical_seconds": 1800,
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
        self.assertNotIn(b"Technician live view", response.data)
        self.assertNotIn(b"Monitoring Health", response.data)
        self.assertNotIn(b"Live Status", response.data)
        self.assertNotIn(b"Refresh Status", response.data)
        self.assertNotIn(b"Open Setup", response.data)
        self.assertNotIn(b"Tech Status auto-refresh runs every 15 seconds", response.data)
        self.assertIn(b"Refresh tech status", response.data)
        self.assertIn(b"Operating State", response.data)
        self.assertIn(b"Charging", response.data)
        self.assertIn(b"Charging at 0.05 kW", response.data)
        self.assertIn(b"Warning Intelligence", response.data)
        self.assertIn(b"pack-quick-icon", response.data)
        self.assertIn(b"pack-detail-rows", response.data)
        self.assertIn(b"Remaining Capacity", response.data)
        self.assertIn(b"Full Capacity", response.data)
        self.assertIn(b"Projected Runtime", response.data)
        self.assertIn(b"Power", response.data)
        self.assertIn(b"BMS Control State", response.data)
        self.assertIn(b"Pack SOC Comparison", response.data)
        self.assertIn(b"Highest vs Lowest Cell", response.data)
        self.assertNotIn(b"BMS internal warning active:", response.data)
        self.assertNotIn(b"Not reported separately", response.data)

    def test_live_tab_uses_cached_snapshot_without_blocking_on_mqtt(self):
        options = {
            "connection_type": "Serial",
            "bms_serial": "/dev/ttyUSB0",
            "scan_interval": 5,
            "mqtt_host": "192.168.1.10",
            "mqtt_port": 1883,
            "mqtt_base_topic": "pacebms",
            "notify_enabled": False,
        }
        live = {
            "ok": True,
            "availability": "online",
            "monitor_state": "running",
            "stale": "OFF",
            "stale_reason": "Fresh",
            "last_analog_read": "2026-05-18 18:20:00",
            "last_warn_read": "2026-05-18 18:20:00",
            "analog_age_seconds": 1,
            "warn_age_seconds": 1,
            "overall_status": "Healthy",
            "overall_class": "healthy",
            "layout": "1 pack(s), 13 cells total",
            "bms_sn": "CACHE-SN",
            "base_topic": "pacebms",
            "pack_count": 1,
            "total_cells": 13,
            "fetched_at": "2026-05-18 18:20:00",
            "error": "",
            "severity_summary": {},
            "packs": [],
        }
        web_config.update_live_snapshot_cache(options, live)

        with (
            patch("web_config.load_options", return_value=(options, "")),
            patch("web_config.fetch_mqtt_snapshot") as fetch_snapshot,
            patch("web_config.load_events", return_value=[]),
        ):
            response = web_config.app.test_client().get("/?tab=dashboard")

        self.assertEqual(response.status_code, 200)
        fetch_snapshot.assert_not_called()
        self.assertIn(b"CACHE-SN", response.data)

    def test_warning_intelligence_calculates_reference_margins(self):
        pack = {
            "highest_cell": {"number": "08", "voltage": "4.200"},
            "lowest_cell": {"number": "01", "voltage": "4.163"},
            "delta": "37",
        }
        details = web_config.build_warning_intelligence(
            pack,
            "cell 2 Above upper limit | cell 8 Above upper limit | Above cell volt warn | Above total volt warn",
            [(1, 4.163), (2, 4.176), (8, 4.200)],
            54.377,
            4.20,
            3.00,
            54.60,
            39.00,
            cell_delta_ref=100,
            alert_toggles={
                "notify_alert_cell_high_voltage": True,
                "notify_alert_pack_high_voltage": True,
            },
        )

        self.assertEqual(details["groups"][0]["title"], "Above upper limit")
        self.assertEqual(details["groups"][0]["rows"][0]["label"], "Cell 02")
        self.assertEqual(details["groups"][0]["rows"][0]["status"], "BMS caution")
        self.assertEqual(details["groups"][0]["rows"][0]["reference_status"], "Not exceeded")
        self.assertEqual(details["groups"][0]["rows"][1]["label"], "Cell 08")
        self.assertEqual(details["groups"][0]["rows"][1]["status"], "At reference")
        self.assertTrue(any(group["title"] == "Pack voltage" for group in details["groups"]))
        self.assertIn("user_reference_rows", details)
        self.assertTrue(any(row["label"].startswith("High cell voltage") for row in details["user_reference_rows"]))
        self.assertFalse(any(row["label"] == "Cell delta" for row in details["user_reference_rows"]))
        self.assertFalse(any(row["label"] == "Pack high voltage" for row in details["user_reference_rows"]))
        self.assertIn("Telegram filtered", details["telegram_decision"])
        self.assertIn("BMS warning is active below configured reference.", details["reference_checks"])
        self.assertIn("BMS internal threshold appears lower than the configured user reference.", details["reference_checks"])
        self.assertIn("BMS warning is active even though", details["interpretation"])

    def test_warning_intelligence_hides_safe_high_delta_and_pack_rows(self):
        pack = {
            "highest_cell": {"number": "08", "voltage": "4.157"},
            "lowest_cell": {"number": "01", "voltage": "4.122"},
            "delta": "35",
        }
        details = web_config.build_warning_intelligence(
            pack,
            "cell 8 Above upper limit | Above cell volt warn | Above total volt warn",
            [(1, 4.122), (8, 4.157)],
            53.822,
            4.20,
            3.00,
            54.60,
            39.00,
            cell_delta_ref=100,
            alert_toggles={
                "notify_alert_cell_high_voltage": True,
                "notify_alert_cell_delta": True,
                "notify_alert_pack_high_voltage": True,
            },
        )

        self.assertTrue(details["groups"])
        high_group = next(group for group in details["groups"] if group["title"] == "Above upper limit")
        pack_group = next(group for group in details["groups"] if group["title"] == "Pack voltage")
        self.assertEqual(high_group["rows"][0]["value"], "4.157 V")
        self.assertEqual(high_group["rows"][0]["ref"], "4.20 V")
        self.assertEqual(high_group["rows"][0]["margin"], "0.043 V below ref")
        self.assertEqual(high_group["rows"][0]["status"], "BMS caution")
        self.assertEqual(pack_group["rows"][0]["value"], "53.822 V")
        self.assertEqual(pack_group["rows"][0]["ref"], "54.60 V")
        self.assertEqual(pack_group["rows"][0]["status"], "BMS caution")
        self.assertFalse(details["user_reference_rows"])
        self.assertFalse(details["show_user_reference_details"])
        self.assertEqual(details["user_reference_summary"], "All configured user alert references are within limits.")
        self.assertIn("BMS warning is active below configured reference.", details["reference_checks"])

    def test_warning_intelligence_shows_high_delta_and_pack_rows_above_reference(self):
        pack = {
            "highest_cell": {"number": "08", "voltage": "4.157"},
            "lowest_cell": {"number": "01", "voltage": "4.022"},
            "delta": "135",
        }
        details = web_config.build_warning_intelligence(
            pack,
            "Above total volt warn",
            [(1, 4.022), (8, 4.157)],
            58.822,
            4.20,
            3.00,
            54.60,
            39.00,
            cell_delta_ref=100,
            alert_toggles={
                "notify_alert_cell_delta": True,
                "notify_alert_pack_high_voltage": True,
            },
        )

        delta_row = next(row for row in details["user_reference_rows"] if row["label"] == "Cell delta")
        pack_row = next(row for row in details["user_reference_rows"] if row["label"] == "Pack high voltage")
        self.assertEqual(delta_row["margin"], "35 mV above ref")
        self.assertEqual(delta_row["status"], "Exceeded")
        self.assertEqual(pack_row["margin"], "4.222 V above ref")
        self.assertEqual(pack_row["status"], "Exceeded")
        self.assertEqual(details["groups"][0]["title"], "Pack voltage")
        self.assertEqual(details["groups"][0]["rows"][0]["status"], "Exceeded")

    def test_warning_intelligence_hides_low_cell_ok_rows(self):
        pack = {
            "highest_cell": {"number": "08", "voltage": "4.160"},
            "lowest_cell": {"number": "01", "voltage": "4.123"},
            "delta": "36",
        }
        details = web_config.build_warning_intelligence(
            pack,
            "cell 1 Below lower limit | Low cell voltage | Low power warning",
            [(1, 4.123), (8, 4.160)],
            53.855,
            4.20,
            3.00,
            54.60,
            39.00,
            cell_delta_ref=100,
            alert_toggles={
                "notify_alert_cell_low_voltage": True,
                "notify_alert_pack_low_voltage": True,
            },
        )

        low_group = next(group for group in details["groups"] if group["title"] == "Below lower limit")
        self.assertEqual(low_group["rows"][0]["value"], "4.123 V")
        self.assertEqual(low_group["rows"][0]["ref"], "3.00 V")
        self.assertEqual(low_group["rows"][0]["margin"], "1.123 V above ref")
        self.assertEqual(low_group["rows"][0]["status"], "BMS caution")
        self.assertFalse(any(row["label"].startswith("Low cell voltage") for row in details["user_reference_rows"]))
        self.assertFalse(any(row["label"] == "Pack low voltage" for row in details["user_reference_rows"]))
        self.assertIn("BMS warning is active below configured reference.", details["reference_checks"])
        self.assertIn("BMS warning is active even though", details["interpretation"])

    def test_warning_intelligence_shows_low_cell_exceeded_rows(self):
        pack = {
            "highest_cell": {"number": "06", "voltage": "3.465"},
            "lowest_cell": {"number": "07", "voltage": "2.984"},
            "delta": "481",
        }
        details = web_config.build_warning_intelligence(
            pack,
            "cell 7 Below lower limit | Low cell voltage | Low power warning",
            [(6, 3.465), (7, 2.984)],
            44.474,
            4.20,
            3.00,
            54.60,
            39.00,
            cell_delta_ref=100,
            alert_toggles={"notify_alert_cell_low_voltage": True},
        )

        low_group = next(group for group in details["groups"] if group["title"] == "Below lower limit")
        self.assertEqual(low_group["rows"][0]["label"], "Cell 07")
        self.assertEqual(low_group["rows"][0]["status"], "Exceeded")
        low_reference = next(row for row in details["user_reference_rows"] if row["label"].startswith("Low cell voltage"))
        self.assertEqual(low_reference["status"], "Exceeded")

    def test_warning_intelligence_explains_critical_bms_telegram_decision(self):
        pack = {
            "highest_cell": {"number": "08", "voltage": "4.184"},
            "lowest_cell": {"number": "01", "voltage": "4.147"},
            "delta": "37",
        }
        details = web_config.build_warning_intelligence(
            pack,
            "cell 8 Above upper limit | Protection State 1: Above cell volt protect | Above total volt protect",
            [(1, 4.147), (8, 4.184)],
            54.174,
            4.20,
            3.00,
            54.60,
            39.00,
            cell_delta_ref=100,
            alert_toggles={
                "notify_alert_cell_high_voltage": True,
                "notify_alert_pack_high_voltage": True,
            },
            telegram_policy="user_reference_or_critical",
        )

        self.assertIn("Telegram will send", details["telegram_decision"])
        self.assertIn("critical/protection text", details["telegram_decision"])
        self.assertEqual(details["telegram_decision_class"], "critical")

    def test_warning_intelligence_shows_user_reference_without_bms_warning(self):
        pack = {
            "highest_cell": {"number": "06", "voltage": "3.649"},
            "lowest_cell": {"number": "07", "voltage": "3.592"},
            "delta": "57",
        }

        details = web_config.build_warning_intelligence(
            pack,
            "Normal",
            [(6, 3.649), (7, 3.592)],
            47.307,
            4.20,
            3.00,
            54.60,
            39.00,
            cell_delta_ref=50,
            alert_toggles={"notify_alert_cell_delta": True},
            telegram_policy="user_reference_or_critical",
        )

        delta_row = next(row for row in details["user_reference_rows"] if row["label"] == "Cell delta")
        self.assertEqual(delta_row["status"], "Exceeded")
        self.assertEqual(delta_row["margin"], "7 mV above ref")
        self.assertIn("No BMS warning is active", details["telegram_decision"])
        self.assertIn("app-side watch condition", details["interpretation"])

    def test_bms_warning_cell_labels_identify_triggered_cells(self):
        labels = web_config._warning_cell_label_map(
            "cell 7 Below lower limit | cell 13 Below lower limit | cell 2 Above upper limit"
        )

        self.assertEqual(labels[2], ["BMS High Warning"])
        self.assertEqual(labels[7], ["BMS Low Warning"])
        self.assertEqual(labels[13], ["BMS Low Warning"])

    def test_generic_bms_warning_labels_fallback_to_cell_extremes(self):
        labels = web_config._warning_cell_label_map(
            "Warning State 1: Above cell volt warn | Above total volt warn",
            highest_cell_num=8,
            lowest_cell_num=1,
        )

        self.assertEqual(labels[8], ["BMS High Warning"])
        self.assertNotIn(1, labels)

        labels = web_config._warning_cell_label_map(
            "Low cell voltage | Low power warning",
            highest_cell_num=8,
            lowest_cell_num=7,
        )

        self.assertEqual(labels[7], ["BMS Low Warning"])
        self.assertNotIn(8, labels)

    def test_live_snapshot_marks_generic_bms_warning_cell_extreme(self):
        pack = types.SimpleNamespace(
            pack_number=1,
            cells=3,
            v_cells=[4125, 4145, 4160],
            t_cells=[],
            v_pack=53855,
            i_pack=0,
            i_remain_cap=88000,
            i_full_cap=89000,
            i_design_cap=100000,
            cycles=992,
            soc=99.77,
            soh=88.54,
            cell_max_diff=35,
        )
        analog_data = types.SimpleNamespace(pack_data=[pack])
        warn = types.SimpleNamespace(pack_number=1, warnings="Warning State 1: Above cell volt warn | Above total volt warn")

        snapshot = bms_live.build_live_snapshot({}, analog_data=analog_data, warn_list=[warn])

        cells = snapshot["packs"][0]["cells"]
        self.assertIn("BMS High Warning", cells[2]["labels"])
        self.assertEqual(cells[2]["class"], "cell-caution")
        self.assertNotIn("BMS High Warning", cells[0]["labels"])

    def test_live_snapshot_clears_bms_warning_after_normal_warn_read(self):
        options = dict(web_config.DEFAULT_OPTION_VALUES)
        pack = types.SimpleNamespace(
            pack_number=1,
            cells=3,
            v_cells=[4059, 4078, 4092],
            t_cells=[],
            v_pack=52972,
            i_pack=-1871,
            i_remain_cap=84000,
            i_full_cap=89000,
            i_design_cap=100000,
            cycles=992,
            soc=94.96,
            soh=88.54,
            cell_max_diff=33,
        )
        analog_data = types.SimpleNamespace(pack_data=[pack])
        warning = types.SimpleNamespace(
            pack_number=1,
            warnings="Warning State 1: Above cell volt warn | Above total volt warn",
            charge_fet=1,
            discharge_fet=1,
            fully=0,
        )
        normal = types.SimpleNamespace(
            pack_number=1,
            warnings="",
            charge_fet=1,
            discharge_fet=1,
            fully=0,
        )

        warning_snapshot = web_config.attach_monitoring_health(
            options,
            bms_live.build_live_snapshot(options, analog_data=analog_data, warn_list=[warning]),
        )
        cleared_snapshot = web_config.attach_monitoring_health(
            options,
            bms_live.build_live_snapshot(options, analog_data=analog_data, warn_list=[normal]),
        )

        self.assertEqual(warning_snapshot["warning_count"], 1)
        self.assertNotEqual(warning_snapshot["warning_signature"], cleared_snapshot["warning_signature"])
        self.assertEqual(cleared_snapshot["warning_count"], 0)
        self.assertEqual(cleared_snapshot["overall_status"], "Healthy")
        self.assertEqual(cleared_snapshot["user_summary"]["warning_summary"], "No active warnings")
        pack_after_clear = cleared_snapshot["packs"][0]
        self.assertEqual(pack_after_clear["warnings"], "Normal")
        self.assertEqual(pack_after_clear["severity_label"], "Normal")
        self.assertEqual(pack_after_clear["severity_class"], "healthy")
        self.assertFalse(pack_after_clear["warning_intelligence"]["groups"])
        for cell in pack_after_clear["cells"]:
            self.assertNotIn("BMS High Warning", cell["labels"])

    def test_live_ui_marks_bms_warning_below_references_as_caution(self):
        options = dict(web_config.DEFAULT_OPTION_VALUES)
        options.update({
            "notify_cell_high_warn_voltage": 4.20,
            "notify_cell_low_warn_voltage": 3.00,
            "notify_cell_delta_warn_mv": 50,
            "notify_bms_warning_policy": "user_reference_or_critical",
        })
        live = {
            "ok": True,
            "availability": "online",
            "monitor_state": "running",
            "stale": "OFF",
            "analog_age_seconds": 1,
            "warn_age_seconds": 1,
            "pack_count": 1,
            "total_cells": 13,
            "warning_count": 1,
            "packs": [{
                "id": "01",
                "cell_count": 13,
                "role": "Master",
                "serial": "PACK01",
                "soc": "99.37",
                "soh": "88.54",
                "cycles": "992",
                "remaining_capacity_ah": "88",
                "full_capacity_ah": "89",
                "design_capacity_ah": "100",
                "voltage": "53.825",
                "current": "0.00",
                "power_kw": "0.00",
                "delta": "35",
                "warnings": "Warning State 1: Above cell volt warn | Above total volt warn",
                "severity_class": "warning",
                "severity_label": "Warning",
                "highest_cell": {"number": "08", "voltage": "4.157"},
                "lowest_cell": {"number": "01", "voltage": "4.122"},
                "cell_high_ref": "4.20",
                "cell_low_ref": "3.00",
                "pack_high_ref": "54.60",
                "pack_low_ref": "39.00",
                "cells": [
                    {"number": "01", "voltage": "4.122", "labels": ["Lowest"], "class": "cell-highlow"},
                    {"number": "08", "voltage": "4.157", "labels": ["Highest", "BMS High Warning"], "class": "cell-caution"},
                ],
            }],
        }

        with (
            patch("web_config.load_monitor_health", return_value={
                "updated_at": 1000,
                "state": "running",
                "health_timeout_seconds": 60,
            }),
            patch("web_config.time.time", return_value=1001),
        ):
            normalized = web_config.attach_monitoring_health(options, live)
        pack = normalized["packs"][0]

        self.assertEqual(pack["severity_class"], "caution")
        self.assertEqual(pack["severity_label"], "BMS Caution")
        self.assertFalse(pack["warning_intelligence"]["user_reference_rows"])
        self.assertTrue(pack["warning_intelligence"]["groups"])
        self.assertEqual(pack["warning_intelligence"]["groups"][0]["rows"][0]["status"], "BMS caution")
        self.assertEqual(normalized["overall_status"], "BMS Caution")
        self.assertEqual(normalized["overall_class"], "caution")
        self.assertEqual(normalized["user_summary"]["status"], "BMS Caution")
        self.assertEqual(normalized["user_summary"]["class"], "caution")
        self.assertEqual(normalized["user_summary"]["power_state"], "Idle")
        self.assertEqual(normalized["user_summary"]["power_state_class"], "healthy")
        self.assertEqual(normalized["user_summary"]["warning_class"], "caution")
        self.assertIn("highest severity: BMS Caution", normalized["user_summary"]["warning_summary"])
        self.assertEqual(normalized["monitoring_health"]["status"], "Watching With Caution")
        self.assertEqual(normalized["monitoring_health"]["class"], "caution")

    def test_log_classifier_keeps_web_access_noise_at_debug_level_3(self):
        level, category = web_config.classify_log_line(
            '172.30.32.2 - - [18/May/2026 18:47:33] "GET /api/status HTTP/1.1" 200 -',
            "web",
        )

        self.assertEqual(level, 3)
        self.assertEqual(category, "Web UI")

    def test_log_classifier_keeps_duplicate_suppression_out_of_alerts(self):
        level, category = web_config.classify_log_line(
            "2026-05-18 20:21:47,273 [DEBUG] [monitor] BMS caution warning duplicate suppressed for Pack 01",
            "monitor",
        )

        self.assertEqual(level, 2)
        self.assertEqual(category, "Warnings")

    def test_log_view_builds_filtered_support_rows(self):
        options = {"debug_output": 2}
        monitor_lines = [
            "2026-05-18 18:46:15,123 [INFO] Analog read OK: packs=2",
            "2026-05-18 18:46:20,981 [INFO] Warn read OK: pack_1: warnings=no warnings",
            "2026-05-18 18:47:18,595 [WARNING] Telegram not configured",
        ]
        web_lines = [
            '172.30.32.2 - - [18/May/2026 18:47:33] "GET /api/status HTTP/1.1" 200 -',
        ]

        def fake_tail(path, limit=web_config.MAX_LOG_VIEW_LINES):
            if path == web_config.MONITOR_LOG_PATH:
                return monitor_lines
            if path == web_config.WEB_LOG_PATH:
                return web_lines
            return []

        with patch("web_config.read_log_tail", side_effect=fake_tail):
            log_view = web_config.build_log_view(options)

        self.assertEqual(log_view["debug_output"], 2)
        self.assertEqual(log_view["default_view"], "battery")
        self.assertEqual(log_view["visible_at_default"], 3)
        analog_row = next(row for row in log_view["rows"] if "Analog read OK" in row["message"])
        warn_row = next(row for row in log_view["rows"] if "Warn read OK" in row["message"])
        web_row = next(row for row in log_view["rows"] if "GET /api/status" in row["message"])
        self.assertEqual(analog_row["level"], 2)
        self.assertEqual(analog_row["category"], "Monitor")
        self.assertTrue(analog_row["battery"])
        self.assertFalse(analog_row["important"])
        self.assertTrue(warn_row["battery"])
        self.assertTrue(warn_row["important"])
        self.assertEqual(web_row["level"], 3)
        self.assertEqual(web_row["category"], "Web UI")
        self.assertFalse(web_row["battery"])
        self.assertTrue(web_row["everything"])
        self.assertEqual(log_view["oldest_time"], "2026-05-18 18:46:15,123")
        self.assertEqual(log_view["newest_time"], "2026-05-18 18:47:33")

    def test_config_group_order_keeps_profile_references_last(self):
        group_names = list(web_config.GROUPS.keys())
        grouped_keys = [key for keys in web_config.GROUPS.values() for key in keys]

        self.assertEqual(group_names[-1], "Battery Profile & References")
        self.assertNotIn("Battery Layout & Fallbacks", group_names)
        self.assertIn("expected_pack_count", web_config.GROUPS["Battery Profile & References"])
        self.assertLess(
            web_config.GROUPS["Battery Profile & References"].index("expected_pack_count"),
            web_config.GROUPS["Battery Profile & References"].index("notify_cell_high_warn_voltage"),
        )
        self.assertEqual(web_config.GROUPS["Scheduled Reports"][-1], "daily_energy_current_deadband_a")
        self.assertEqual(len(grouped_keys), len(set(grouped_keys)))
        self.assertIn("notify_fet", web_config.GROUPS["FET Notifications"])
        self.assertNotIn("notify_fet", web_config.GROUPS["Notifications"])

    def test_config_page_uses_friendly_field_labels(self):
        options = dict(web_config.DEFAULT_OPTION_VALUES)

        with patch("web_config.load_options", return_value=(options, "")), \
            patch("web_config.get_page_live_snapshot", return_value={"packs": []}), \
            patch("web_config.load_events", return_value=[]):
            response = web_config.app.test_client().get("/?tab=config")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Low SOC thresholds", response.data)
        self.assertIn(b"notify_soc_low_thresholds", response.data)
        self.assertIn(b"FET state alerts", response.data)
        self.assertIn(b"Battery Profile & Alert References", response.data)
        self.assertIn(b"Expected pack count", response.data)

    def test_capacity_fallback_is_used_only_when_bms_capacity_is_missing(self):
        options = dict(web_config.DEFAULT_OPTION_VALUES)
        options.update({
            "capacity_fallback_enabled": True,
            "capacity_per_pack_ah": 100,
        })
        live = {
            "packs": [
                {"voltage": "50", "current": "-10", "soc": "50", "soh": "90", "warnings": "Normal", "fully": "OFF", "temperatures": [25]},
            ],
            "warning_count": 0,
            "stale": "OFF",
            "availability": "online",
            "total_cells": 13,
            "fetched_at": "now",
        }

        summary = web_config._calculate_user_summary(options, live)

        self.assertEqual(summary["remaining_capacity_ah"], "50 Ah")
        self.assertEqual(summary["full_capacity_ah"], "100 Ah")
        self.assertIn("fallback used", summary["capacity_detail"])
        self.assertNotEqual(summary["runtime_remaining"], "Unknown")

    def test_capacity_fallback_does_not_override_bms_capacity(self):
        options = dict(web_config.DEFAULT_OPTION_VALUES)
        options.update({
            "capacity_fallback_enabled": True,
            "capacity_per_pack_ah": 100,
        })
        live = {
            "packs": [
                {
                    "voltage": "50",
                    "current": "-10",
                    "soc": "50",
                    "soh": "90",
                    "remaining_capacity_ah": "80",
                    "full_capacity_ah": "160",
                    "design_capacity_ah": "160",
                    "warnings": "Normal",
                    "fully": "OFF",
                    "temperatures": [25],
                },
            ],
            "warning_count": 0,
            "stale": "OFF",
            "availability": "online",
            "total_cells": 13,
            "fetched_at": "now",
        }

        summary = web_config._calculate_user_summary(options, live)

        self.assertEqual(summary["remaining_capacity_ah"], "80 Ah")
        self.assertEqual(summary["full_capacity_ah"], "160 Ah")
        self.assertNotIn("fallback used", summary["capacity_detail"])

    def test_logs_page_uses_simple_show_filter(self):
        options = dict(web_config.DEFAULT_OPTION_VALUES)

        with patch("web_config.load_options", return_value=(options, "")), \
            patch("web_config.read_log_tail", return_value=[
                "2026-05-18 18:46:15,123 [INFO] Analog read OK: packs=2",
                "2026-05-18 18:47:18,595 [WARNING] Telegram not configured",
            ]), \
            patch("web_config.load_events", return_value=[]):
            response = web_config.app.test_client().get("/?tab=logs")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="log-show-filter"', html)
        self.assertIn("Battery reads", html)
        self.assertIn("Everything", html)
        self.assertNotIn('id="log-category-filter"', html)
        self.assertNotIn("View detail", html)

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
            "notify_warning_repeat_critical_seconds": 1800,
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
        self.assertIn(b"pack-comparison-subtitle", response.data)
        self.assertIn(b"pack-detail-rows", response.data)
        self.assertIn(b"data-pack-field=\"01-status-pill\"", response.data)
        self.assertIn(b"Projected Runtime", response.data)
        self.assertIn(b"Full Capacity", response.data)
        self.assertIn(b"Highest Cell", response.data)
        self.assertIn(b"Battery Power", response.data)
        self.assertIn(b"Charge Time Estimate", response.data)
        self.assertIn(b"Last Updated", response.data)
        self.assertIn(b"Remaining Capacity", response.data)
        self.assertNotIn(b"Monitoring Snapshot", response.data)
        self.assertNotIn(b"Warning Summary", response.data)

    def test_live_pages_render_with_partial_retained_pack_snapshot(self):
        options = dict(web_config.DEFAULT_OPTION_VALUES)
        live = {
            "ok": True,
            "availability": "online",
            "monitor_state": "running",
            "stale": "OFF",
            "stale_reason": "Fresh",
            "last_analog_read": "2026-05-19 12:00:00",
            "last_warn_read": "2026-05-19 12:00:01",
            "analog_age_seconds": 1,
            "warn_age_seconds": 1,
            "overall_status": "Healthy",
            "overall_class": "healthy",
            "layout": "Partial retained snapshot",
            "bms_sn": "TEST",
            "base_topic": "pacebms",
            "fetched_at": "now",
            "error": "",
            "severity_summary": {},
            "pack_count": 2,
            "total_cells": 13,
            "warning_count": 0,
            "packs": [
                {"cell_count": 13},
                {"id": "02", "soc": "99.1", "highest_cell": {}, "warnings": "no warnings"},
            ],
        }

        with (
            patch("web_config.load_options", return_value=(options, "")),
            patch("web_config.get_page_live_snapshot", return_value=live),
            patch("web_config.load_events", return_value=[]),
        ):
            client = web_config.app.test_client()
            for tab in ("dashboard", "history", "status", "diagnostics", "setup", "config", "events", "backups", "logs"):
                with self.subTest(tab=tab):
                    response = client.get(f"/?tab={tab}")
                    self.assertEqual(response.status_code, 200)
                    if tab == "history":
                        self.assertIn(b'data-history-pack="all"', response.data)
                        self.assertIn(b'data-history-pack="01"', response.data)
                        self.assertIn(b'data-history-pack="02"', response.data)
                        self.assertIn(b"historyControlsInitialized", response.data)
                        self.assertIn(b'event.target.closest("[data-history-pack]")', response.data)
                        self.assertIn(b"panelHasCharts(currentPanel) || panelHasCharts(nextPanel)", response.data)

    def test_all_main_tab_buttons_point_to_renderable_tabs(self):
        options = dict(web_config.DEFAULT_OPTION_VALUES)
        live = self._operational_live_snapshot()

        with (
            patch("web_config.load_options", return_value=(options, "")),
            patch("web_config.get_page_live_snapshot", return_value=live),
            patch("web_config.load_events", return_value=[]),
            patch("web_config.list_config_backups", return_value=[]),
        ):
            client = web_config.app.test_client()
            response = client.get("/")
            html = response.get_data(as_text=True)
            expected_tabs = ["dashboard", "status", "diagnostics", "history", "setup", "config", "events", "backups", "logs"]

            self.assertIn(f"Version {web_config.ADDON_VERSION}", html)

            for tab in expected_tabs:
                self.assertIn(f'href="?tab={tab}"', html)

            tab_positions = [html.find(f'href="?tab={tab}"') for tab in expected_tabs]
            self.assertEqual(tab_positions, sorted(tab_positions))

            for tab in expected_tabs:
                with self.subTest(tab=tab):
                    tab_response = client.get(f"/?tab={tab}")
                    self.assertEqual(tab_response.status_code, 200)
                    self.assertIn('class="tab-panel active"', tab_response.get_data(as_text=True))

    def test_operational_ui_routes_links_and_forms_are_reachable(self):
        options = dict(web_config.DEFAULT_OPTION_VALUES)
        options["mqtt_enabled"] = False
        live = self._operational_live_snapshot()
        expected_tabs = {"dashboard", "status", "diagnostics", "history", "setup", "config", "events", "backups", "logs"}

        with (
            patch("web_config.load_options", return_value=(options, "")),
            patch("web_config.get_page_live_snapshot", return_value=live),
            patch("web_config.refresh_live_snapshot_cache_once", return_value=live),
            patch("web_config.load_events", return_value=[]),
            patch("web_config.list_config_backups", return_value=[]),
            patch("web_config.build_log_view", return_value={"debug_output": 0, "rows": []}),
        ):
            client = web_config.app.test_client()
            html_by_tab = {}
            for tab in sorted(expected_tabs):
                response = client.get(f"/?tab={tab}")
                self.assertEqual(response.status_code, 200)
                html_by_tab[tab] = response.get_data(as_text=True)

            rendered = "\n".join(html_by_tab.values())
            tab_links = set(re.findall(r'href="\?tab=([^"]+)"', rendered))
            self.assertEqual(tab_links, expected_tabs)

            rules = {rule.rule.lstrip("/") for rule in web_config.app.url_map.iter_rules() if "<" not in rule.rule}
            routes_to_ignore = {"", "#"}
            for attr in ("href", "action"):
                targets = re.findall(rf'{attr}="([^"]+)"', rendered)
                for target in targets:
                    with self.subTest(attr=attr, target=target):
                        if target.startswith(("?", "#", "http:", "https:", "mailto:", "javascript:")):
                            continue
                        path = target.split("?", 1)[0].strip("/")
                        if path in routes_to_ignore:
                            continue
                        self.assertIn(path, rules)

            get_routes = [
                "export-config.yaml",
                "download-logs.txt",
                "export-events.json",
                "export-events.csv",
                "download-all-config-backups.zip",
                "download-diagnostics.json",
                "download-support-bundle.zip",
                "api/status",
                "api/live",
                "api/history",
                "api/history/pack/01",
                "api/history/cells/01",
                "api/events",
            ]
            for route in get_routes:
                with self.subTest(route=route):
                    response = client.get(f"/{route}")
                    self.assertLess(response.status_code, 500)

            with (
                patch("web_config.test_telegram", return_value=(True, "Telegram OK")),
                patch("web_config.test_mqtt", return_value=(True, "MQTT OK")),
                patch("web_config.test_full_monitoring", return_value=(True, "Full monitoring OK")),
                patch("web_config.create_config_backup", return_value=(True, "backup ok", "options-backup-manual.json")),
                patch("web_config.restart_addon", return_value=(True, "restart requested")),
                patch("web_config.append_event"),
            ):
                post_routes = [
                    "test-telegram",
                    "test-mqtt",
                    "test-full-monitoring",
                    "create-config-backup",
                    "restart-addon",
                ]
                for route in post_routes:
                    with self.subTest(route=route):
                        response = client.post(f"/{route}")
                        self.assertLess(response.status_code, 500)

    def test_api_status_payload_supports_full_soft_refresh_data(self):
        options = dict(web_config.DEFAULT_OPTION_VALUES)
        live = self._operational_live_snapshot()

        with (
            patch("web_config.load_options", return_value=(options, "")),
            patch("web_config.refresh_live_snapshot_cache_once", return_value=live),
            patch("web_config.load_monitor_health", return_value={
                "updated_at": 1000,
                "state": "running",
                "health_timeout_seconds": 60,
            }),
            patch("web_config.time.time", return_value=1001),
        ):
            response = web_config.app.test_client().get("/api/status")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["overall_status"], "Healthy")
        self.assertEqual(payload["packs"][0]["id"], "01")
        self.assertEqual(payload["packs"][0]["soc"], "94.96")
        self.assertEqual(payload["packs"][0]["highest_cell"]["voltage"], "4.092")
        self.assertIn("monitoring_health", payload)
        self.assertIn("user_summary", payload)
        self.assertEqual(payload["user_summary"]["last_updated"], "2026-05-21 12:00:02")

    def test_api_refresh_payload_contract_covers_live_tab_fields(self):
        options = dict(web_config.DEFAULT_OPTION_VALUES)
        live = self._operational_live_snapshot()

        with (
            patch("web_config.load_options", return_value=(options, "")),
            patch("web_config.refresh_live_snapshot_cache_once", return_value=live),
            patch("web_config.load_monitor_health", return_value={
                "updated_at": 1000,
                "state": "running",
                "health_timeout_seconds": 60,
            }),
            patch("web_config.time.time", return_value=1001),
        ):
            client = web_config.app.test_client()
            status_payload = client.get("/api/status").get_json()
            live_payload = client.get("/api/live").get_json()

        for payload in (status_payload, live_payload):
            with self.subTest(source=payload.get("source")):
                for key in (
                    "ok", "source", "data_source", "snapshot_id", "overall_status", "overall_class",
                    "availability", "monitor_state", "stale", "stale_reason", "layout",
                    "bms_sn", "bms_version", "base_topic", "fetched_at", "last_analog_read",
                    "last_warn_read", "analog_age_seconds", "warn_age_seconds", "pack_count",
                    "total_cells", "warning_count", "warning_signature", "monitoring_health",
                    "user_summary", "packs",
                ):
                    self.assertIn(key, payload)

                summary = payload["user_summary"]
                for key in (
                    "status", "class", "power_state", "power_state_class", "summary",
                    "combined_soc", "combined_soh", "total_power_kw", "power_flow",
                    "power_detail", "power_class", "pack_voltage", "battery_current",
                    "remaining_capacity_ah", "remaining_energy_kwh", "full_capacity_ah",
                    "capacity_detail", "runtime_remaining", "runtime_detail", "active_warnings",
                    "warning_summary", "warning_class", "last_updated",
                ):
                    self.assertIn(key, summary)

                self.assertEqual(payload["pack_count"], 2)
                self.assertEqual(payload["total_cells"], 26)
                self.assertEqual(payload["warning_count"], 0)
                self.assertEqual(summary["power_state"], "Discharging")
                self.assertEqual(summary["combined_soc"], "96.3%")
                self.assertEqual(summary["remaining_capacity_ah"], "172 Ah")
                self.assertEqual(summary["battery_current"], "-35.79 A")
                self.assertEqual(summary["warning_summary"], "No active warnings")

                first_pack = payload["packs"][0]
                for key in (
                    "id", "role", "serial", "cell_count", "soc", "soh", "cycles",
                    "remaining_capacity_ah", "full_capacity_ah", "design_capacity_ah",
                    "voltage", "current", "power_kw", "delta", "warnings", "severity_class",
                    "severity_label", "highest_cell", "lowest_cell", "cells", "warning_intelligence",
                    "reference_checks", "charge_fet", "discharge_fet", "fully",
                ):
                    self.assertIn(key, first_pack)
                self.assertEqual(first_pack["warnings"], "Normal")
                self.assertEqual(first_pack["severity_label"], "Normal")
                self.assertEqual(first_pack["highest_cell"]["voltage"], "4.092")
                self.assertEqual(len(first_pack["cells"]), 13)

    def test_operational_tabs_render_same_live_serial_values(self):
        options = dict(web_config.DEFAULT_OPTION_VALUES)
        live = self._operational_live_snapshot()

        with (
            patch("web_config.load_options", return_value=(options, "")),
            patch("web_config.get_page_live_snapshot", return_value=live),
            patch("web_config.load_events", return_value=[]),
            patch("web_config.list_config_backups", return_value=[]),
        ):
            client = web_config.app.test_client()
            pages = {
                tab: client.get(f"/?tab={tab}").get_data(as_text=True)
                for tab in ("dashboard", "status", "diagnostics")
            }

        for tab, html in pages.items():
            with self.subTest(tab=tab):
                self.assertIn("Live serial", html)
                self.assertIn("HL2107001569", html)
                self.assertIn("94.96", html)
                self.assertIn("97.58", html)
                self.assertIn("52.972", html)
                self.assertIn("53.004", html)
                self.assertIn("-18.71", html)
                self.assertIn("-17.08", html)
                self.assertIn("33", html)
                self.assertIn("45", html)
                self.assertIn("No active BMS warning", html)

        self.assertIn("P13S120A-12290-2.50", pages["diagnostics"])
        self.assertIn("Operating State", pages["status"])
        self.assertIn("Discharging", pages["status"])
        self.assertIn("Operating State", pages["diagnostics"])
        self.assertIn("Discharging", pages["diagnostics"])
        self.assertNotIn("retained MQTT snapshot", "\n".join(pages.values()))

    def test_discovery_topics_and_unique_ids_are_unique_for_default_padding(self):
        class FakeMqttClient:
            def __init__(self):
                self.published = []

            def publish(self, topic, payload, qos=0, retain=False):
                self.published.append((topic, payload, qos, retain))

        options = dict(web_config.DEFAULT_OPTION_VALUES)
        options.update({
            "mqtt_base_topic": "pacebms",
            "mqtt_ha_discovery": True,
            "mqtt_ha_discovery_topic": "homeassistant",
            "zero_pad_number_packs": 2,
            "zero_pad_number_cells": 2,
        })
        analog_data = bms_monitor.AnalogData(
            packs=2,
            pack_data=[
                bms_monitor.PackData(pack_number=1, cells=13, temps=2, v_cells=[3300] * 13, t_cells=[25, 26]),
                bms_monitor.PackData(pack_number=2, cells=13, temps=2, v_cells=[3301] * 13, t_cells=[25, 26]),
            ],
        )
        client = FakeMqttClient()

        bms_monitor.publish_ha_discovery(client, options, "HL2107001569", "P13S120A-12290-2.50", analog_data)

        topics = [topic for topic, _payload, _qos, _retain in client.published]
        payloads = [json.loads(payload) for _topic, payload, _qos, _retain in client.published]
        unique_ids = [payload["unique_id"] for payload in payloads]

        self.assertEqual(len(topics), len(set(topics)))
        self.assertEqual(len(unique_ids), len(set(unique_ids)))
        self.assertIn("homeassistant/sensor/BMS-HL2107001569/Pack_01_Cell_01_Voltage/config", topics)
        self.assertIn("bmspace_HL2107001569_pack_01_v_cell_01", unique_ids)
        self.assertIn("pacebms/pack_01/v_cells/cell_01", [payload["state_topic"] for payload in payloads])
        self.assertTrue(all(retain for _topic, _payload, _qos, retain in client.published))

    def test_discovery_topics_unique_across_padding_edge_cases(self):
        class FakeMqttClient:
            def __init__(self):
                self.published = []

            def publish(self, topic, payload, qos=0, retain=False):
                self.published.append((topic, payload, qos, retain))

        analog_data = bms_monitor.AnalogData(
            packs=2,
            pack_data=[
                bms_monitor.PackData(pack_number=1, cells=16, temps=4, v_cells=[3300] * 16, t_cells=[25] * 4),
                bms_monitor.PackData(pack_number=2, cells=16, temps=4, v_cells=[3301] * 16, t_cells=[26] * 4),
            ],
        )

        for pack_padding in (0, 1, 2, 3, "bad", None):
            for cell_padding in (0, 1, 2, 3, "bad", None):
                with self.subTest(pack_padding=pack_padding, cell_padding=cell_padding):
                    options = dict(web_config.DEFAULT_OPTION_VALUES)
                    options.update({
                        "mqtt_base_topic": "pacebms",
                        "mqtt_ha_discovery": True,
                        "mqtt_ha_discovery_topic": "homeassistant",
                        "zero_pad_number_packs": pack_padding,
                        "zero_pad_number_cells": cell_padding,
                    })
                    client = FakeMqttClient()

                    bms_monitor.publish_ha_discovery(
                        client,
                        options,
                        "HL2107001569",
                        "P13S120A-12290-2.50",
                        analog_data,
                    )

                    topics = [topic for topic, _payload, _qos, _retain in client.published]
                    payloads = [json.loads(payload) for _topic, payload, _qos, _retain in client.published]
                    unique_ids = [payload["unique_id"] for payload in payloads]
                    state_topics = [payload["state_topic"] for payload in payloads]

                    self.assertEqual(len(topics), len(set(topics)))
                    self.assertEqual(len(unique_ids), len(set(unique_ids)))
                    self.assertEqual(len(state_topics), len(set(state_topics)))

    def test_discovery_state_topics_match_serial_mqtt_publishers(self):
        class FakeMqttClient:
            def __init__(self):
                self.published = []

            def publish(self, topic, payload, qos=0, retain=False):
                self.published.append((topic, payload, qos, retain))

        options = dict(web_config.DEFAULT_OPTION_VALUES)
        options.update({
            "mqtt_base_topic": "pacebms",
            "mqtt_ha_discovery": True,
            "mqtt_ha_discovery_topic": "homeassistant",
            "zero_pad_number_packs": 2,
            "zero_pad_number_cells": 2,
            "mqtt_retain_state": True,
        })
        analog_data = bms_monitor.AnalogData(
            packs=1,
            pack_data=[
                bms_monitor.PackData(
                    pack_number=1,
                    cells=13,
                    temps=2,
                    v_cells=[3300] * 13,
                    t_cells=[25, 26],
                    i_pack=-12.5,
                    v_pack=53.2,
                    i_remain_cap=88000,
                    i_full_cap=90000,
                    i_design_cap=100000,
                    cycles=123,
                    soc=97.5,
                    soh=91.2,
                    cell_max_diff=35,
                ),
            ],
        )
        capacity = bms_monitor.PackCapacity(
            remain_cap=88000,
            full_cap=90000,
            design_cap=100000,
            soc=97.5,
            soh=91.2,
        )
        warn_list = [
            bms_monitor.WarnData(
                pack_number=1,
                warnings="Normal",
                balancing1="",
                balancing2="",
                prot_short_circuit=0,
                prot_discharge_current=0,
                prot_charge_current=0,
                fully=0,
                current_limit=0,
                charge_fet=1,
                discharge_fet=1,
                pack_indicate=0,
                reverse=0,
                ac_in=0,
                heart=0,
            )
        ]

        discovery_client = FakeMqttClient()
        state_client = FakeMqttClient()
        bms_monitor.publish_ha_discovery(
            discovery_client,
            options,
            "HL2107001569",
            "P13S120A-12290-2.50",
            analog_data,
        )
        bms_monitor.publish_analog_data(state_client, options, analog_data, force=True)
        bms_monitor.publish_pack_capacity(state_client, options, capacity, force=True)
        bms_monitor.publish_warn_data(state_client, options, warn_list, force=True)

        discovery_state_topics = {
            json.loads(payload)["state_topic"]
            for _topic, payload, _qos, _retain in discovery_client.published
        }
        published_state_topics = {
            topic
            for topic, _payload, _qos, _retain in state_client.published
        }

        self.assertTrue(discovery_state_topics)
        self.assertTrue(discovery_state_topics.issubset(published_state_topics))

    def test_serial_poll_helpers_use_only_read_only_cid2_commands(self):
        with patch("bms_monitor.bms_request", return_value=(False, "skip")) as request:
            bms_monitor.bms_get_version(object(), {})
            bms_monitor.bms_get_serial(object(), {})
            bms_monitor.bms_get_analog_data(object(), {})
            bms_monitor.bms_get_pack_capacity(object(), {})
            bms_monitor.bms_get_warn_info(object(), {}, packs=1)

        requested_cid2 = [call.kwargs["cid2"] for call in request.call_args_list]
        self.assertEqual(
            requested_cid2,
            [
                bms_monitor.constants.cid2SoftwareVersion,
                bms_monitor.constants.cid2SerialNumber,
                bms_monitor.constants.cid2PackAnalogData,
                bms_monitor.constants.cid2PackCapacity,
                bms_monitor.constants.cid2WarnInfo,
            ],
        )

    def test_config_advanced_help_warns_about_entity_sensitive_padding(self):
        options = dict(web_config.DEFAULT_OPTION_VALUES)
        live = {
            "ok": True,
            "availability": "online",
            "monitor_state": "running",
            "stale": "OFF",
            "overall_status": "Healthy",
            "overall_class": "healthy",
            "layout": "1 pack(s), 13 cells total",
            "bms_sn": "TEST",
            "base_topic": "pacebms",
            "fetched_at": "now",
            "error": "",
            "packs": [],
        }

        with (
            patch("web_config.load_options", return_value=(options, "")),
            patch("web_config.get_page_live_snapshot", return_value=live),
            patch("web_config.load_events", return_value=[]),
        ):
            response = web_config.app.test_client().get("/?tab=config")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Pack number padding (entity-sensitive)", html)
        self.assertIn("Cell number padding (entity-sensitive)", html)
        self.assertIn("Changing padding changes MQTT state topics", html)

    def test_web_runtime_constants_are_defined_before_app_run(self):
        source = Path("web_config.py").read_text(encoding="utf-8")
        self.assertLess(
            source.index("WARNING_TELEGRAM_POLICY_CHOICES ="),
            source.index('if __name__ == "__main__":'),
        )

    def test_monitor_history_writes_are_interval_limited(self):
        source = Path("bms_monitor.py").read_text(encoding="utf-8")
        self.assertNotIn("update_serial_live_snapshot(include_history=True)", source)
        self.assertIn("history_sample_seconds", source)
        self.assertIn("history_cell_sample_seconds", source)

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
            "notify_warning_repeat_critical_seconds": 1800,
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
            "notify_warning_repeat_critical_seconds": 1800,
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
        self.assertNotIn(b"Technician / support proof view", response.data)
        self.assertNotIn(b"Health Checks", response.data)
        self.assertNotIn(b"Refresh Diagnostics", response.data)
        self.assertNotIn(b"Open Status", response.data)
        self.assertNotIn(b"Open Backups", response.data)
        self.assertNotIn(b"Read-Only Safety", response.data)
        self.assertNotIn(b"Diagnostics loaded from current retained MQTT values. Auto-refresh runs every 15 seconds", response.data)
        self.assertIn(b"Refresh diagnostics", response.data)
        self.assertIn(b"Operating State", response.data)
        self.assertIn(b"Charging", response.data)
        self.assertIn(b"Charging at 0.05 kW", response.data)

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
