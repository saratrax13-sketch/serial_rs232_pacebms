import unittest
import importlib.util
import json
import os
import sys
import tempfile
import types
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
import web_config


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
        self.assertIn("BMS Warning Details", message)
        self.assertIn("- Cell 02: 4.176 V | Ref: 4.20 V | Margin: 0.024 V below ref | Not exceeded | Notify: On", message)
        self.assertIn("- Cell 08: 4.200 V | Ref: 4.20 V | Margin: 0.000 V below ref | At reference | Notify: On", message)
        self.assertIn("- Pack: 54.377 V | Ref: 54.60 V | Margin: 0.223 V below ref | Not exceeded | Notify: On", message)
        self.assertIn("Battery profile: P13S / Hubble AM2 51V", message)
        self.assertIn("Reference Check", message)
        self.assertIn("Interpretation", message)
        self.assertIn("Suggested Action", message)

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
        self.assertIn("- Pack: 55.000 V | Ref: 56.16 V", message)


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
        state = bms_notify.NotifyState({})
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

        with (
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
        self.assertIn(b"Energy & Health", response.data)
        self.assertIn(b"Capacity", response.data)
        self.assertIn(b"Power", response.data)
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
        )

        self.assertEqual(details["groups"][0]["title"], "Above upper limit")
        self.assertEqual(details["groups"][0]["rows"][0]["label"], "Cell 02")
        self.assertEqual(details["groups"][0]["rows"][0]["margin"], "0.024 V below ref")
        self.assertEqual(details["groups"][0]["rows"][0]["status"], "Not exceeded")
        self.assertEqual(details["groups"][0]["rows"][1]["status"], "At reference")
        self.assertEqual(details["groups"][1]["title"], "Pack voltage")
        self.assertEqual(details["groups"][1]["rows"][0]["margin"], "0.223 V below ref")
        self.assertIn("BMS warning is active below configured reference.", details["reference_checks"])
        self.assertIn("BMS warning is active even though", details["interpretation"])

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

    def test_option1_route_renders_light_dashboard_without_replacing_current_ui(self):
        options = dict(web_config.DEFAULT_OPTION_VALUES)
        options.update({
            "scan_interval": 5,
            "notify_cell_high_warn_voltage": 4.20,
            "notify_cell_delta_warn_mv": 100,
            "notify_enabled": True,
        })
        live = {
            "ok": True,
            "availability": "online",
            "monitor_state": "running",
            "stale": "OFF",
            "stale_reason": "Fresh",
            "last_analog_read": "2026-05-19 12:00:00",
            "last_warn_read": "2026-05-19 12:00:01",
            "analog_age_seconds": 4,
            "warn_age_seconds": 5,
            "overall_status": "Healthy",
            "overall_class": "healthy",
            "layout": "1 pack(s), 13 cells total",
            "bms_sn": "TEST",
            "base_topic": "pacebms",
            "fetched_at": "2026-05-19 12:00:05",
            "error": "",
            "severity_summary": {},
            "pack_count": 1,
            "total_cells": 13,
            "warning_count": 1,
            "packs": [{
                "id": "01",
                "role": "Master",
                "cell_count": 13,
                "soc": "100",
                "soh": "90.3",
                "cycles": "987",
                "remaining_capacity_ah": "88.86",
                "full_capacity_ah": "100",
                "design_capacity_ah": "100",
                "voltage": "54.09",
                "current": "-2.4",
                "power_kw": "-0.13",
                "delta": "36",
                "temperatures": [28],
                "warnings": "Warning State 1: Above cell volt warn",
                "severity_class": "caution",
                "severity_label": "Caution",
                "highest_cell": {"number": "08", "voltage": "4.178"},
                "lowest_cell": {"number": "01", "voltage": "4.142"},
                "cells": [
                    {"number": "01", "voltage": "4.142", "labels": ["Lowest"], "class": "cell-highlow"},
                    {"number": "08", "voltage": "4.178", "labels": ["Highest"], "class": "cell-highlow"},
                ],
                "cell_high_ref": "4.20",
                "cell_low_ref": "3.00",
            }],
        }

        with (
            patch("web_config.load_options", return_value=(options, "")),
            patch("web_config.get_page_live_snapshot", return_value=live),
            patch("web_config.load_events", return_value=[]),
        ):
            client = web_config.app.test_client()
            response = client.get("/option1")
            query_response = client.get("/?ui=option1&tab=packs")
            default_response = client.get("/")
            legacy_response = client.get("/classic")
            legacy_query_response = client.get("/?ui=classic&tab=dashboard")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(query_response.status_code, 200)
        self.assertIn(b"Battery Packs", query_response.data)
        self.assertIn("Clean Operations Dashboard", html)
        self.assertIn("Overview", html)
        self.assertIn("Packs", html)
        self.assertIn("Cells", html)
        self.assertIn("Warnings", html)
        self.assertIn("Diagnostics", html)
        self.assertIn("Raw Data", html)
        self.assertIn("Settings", html)
        self.assertIn("Watch condition", html)
        self.assertIn("C08", html)
        self.assertIn("54.09 V", html)
        self.assertIn("?ui=option1&tab=packs", html)
        self.assertNotIn('href="/option1', html)
        self.assertNotIn('href="/classic', html)
        self.assertEqual(default_response.status_code, 200)
        self.assertIn(b"Clean Operations Dashboard", default_response.data)
        self.assertEqual(legacy_response.status_code, 200)
        self.assertIn(b"Battery Confidence", legacy_response.data)
        self.assertEqual(legacy_query_response.status_code, 200)
        self.assertIn(b"Battery Confidence", legacy_query_response.data)

    def test_option1_display_rules_show_missing_and_invalid_values(self):
        self.assertEqual(web_config.option1_display(None), "No data")
        self.assertEqual(web_config.option1_display("Unknown"), "No data")
        self.assertEqual(web_config.option1_display(float("nan")), "Invalid")
        self.assertEqual(web_config.option1_display("4.2", " V"), "4.2 V")

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
            for tab in ("dashboard", "status", "diagnostics", "setup", "config", "logs"):
                with self.subTest(tab=tab):
                    response = client.get(f"/?tab={tab}")
                    self.assertEqual(response.status_code, 200)

    def test_web_runtime_constants_are_defined_before_app_run(self):
        source = Path("web_config.py").read_text(encoding="utf-8")
        self.assertLess(
            source.index("WARNING_TELEGRAM_POLICY_CHOICES ="),
            source.index('if __name__ == "__main__":'),
        )

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
        self.assertIn(b"Clean Operations Dashboard", response.data)
        self.assertIn(b"Overview", response.data)

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
