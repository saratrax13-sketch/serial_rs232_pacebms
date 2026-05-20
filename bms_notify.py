# =============================================================================
# bms_notify.py — Notification Engine for Pace BMS Monitor
# Version : 1.2.0
# Changed : 2026-05-16
# Changes :
#   - Disconnect alert now uses retry_count >= threshold and logs skipped alerts
#   - Detailed warning messages use latest analog data and configured thresholds
#   - Charge FET OFF can be ignored when pack is fully charged
#   - Fixed duplicate SOC high notifications caused by startup/midnight reset
#   - Shortened Telegram warning detail and startup version text
#   - Added startup suppression options for SOC-high and SOH alerts
#   - Telegram logs now show the message title only
# Handles all Telegram notifications directly from Python.
# No dependency on HA automations.
# =============================================================================

import time
import json
import logging
import urllib.request
import re
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional

from battery_profiles import effective_warning_references

log = logging.getLogger("bmspace")

TELEGRAM_PLACEHOLDER_VALUES = {
    "",
    "YOUR_TELEGRAM_BOT_TOKEN",
    "YOUR_TELEGRAM_CHAT_ID",
}


def telegram_value_configured(value: str) -> bool:
    """Return True when a Telegram field contains a real user-provided value."""
    return str(value or "").strip() not in TELEGRAM_PLACEHOLDER_VALUES


# ─── Telegram sender ──────────────────────────────────────────────────────────

def telegram_send(config: dict, message: str):
    """Send a Telegram message directly via Bot API."""
    if not config.get('notify_enabled', True):
        return
    token   = str(config.get('telegram_bot_token', '') or '').strip()
    chat_id = str(config.get('telegram_chat_id', '') or '').strip()
    if not telegram_value_configured(token) or not telegram_value_configured(chat_id):
        log.warning("Telegram not configured — skipping notification")
        return
    try:
        url     = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": message}).encode()
        req     = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        title = str(message or "").splitlines()[0].strip() or "<empty>"
        log.info("Telegram sent: %s", title)
    except Exception as e:
        log.warning("Telegram failed: %s", type(e).__name__)


# ─── Notification state ───────────────────────────────────────────────────────

class NotifyState:
    """Tracks all notification state to prevent duplicates and manage thresholds."""

    def __init__(self, config: dict):
        self.config = config

        # SOC threshold tracking — per pack, per threshold
        self.soc_thresholds_hit   = {}   # {pack_num: set of thresholds already notified}
        self.soc_low_initialized  = {}   # {pack_num: bool} suppresses startup-only low SOC replay
        self.soc_high_notified    = {}   # {pack_num: bool}
        self.soc_high_reset_ready = {}   # {pack_num: bool} — True once SOC drops below reset level

        # Warning tracking — per pack
        self.last_warnings        = {}   # {pack_num: str} — last warning string sent

        # FET tracking — per pack
        self.last_charge_fet      = {}   # {pack_num: str} ON/OFF
        self.last_discharge_fet   = {}   # {pack_num: str} ON/OFF
        self.fet_notified         = {}   # {pack_num: bool} — suppresses repeat FET alerts
        self.last_fet_alert_sent  = {}   # {(pack_num, fet_name): epoch seconds}

        # SOH tracking — per pack
        self.soh_notified         = {}   # {pack_num: bool}
        self.soh_initialized      = {}   # {pack_num: bool} — used to suppress startup-only SOH noise

        # Startup/noise suppression tracking
        self.soc_high_initialized = {}   # {pack_num: bool} — used to suppress startup-only full alerts

        # Disconnect tracking
        self.disconnect_time      = None
        self.retry_count          = 0
        self.disconnect_notified  = False  # True after retry threshold hit
        self.recovery_notified    = False

        # Energy tracking — per pack
        self.kwh_charged          = {}   # {pack_num: float}
        self.kwh_discharged       = {}   # {pack_num: float}
        self.last_energy_update    = {}   # {pack_num: epoch seconds}
        self.energy_reset_day     = datetime.now().date()  # date of last midnight reset
        self.soc_start            = {}   # {pack_num: first SOC of day}
        self.soc_latest           = {}   # {pack_num: latest SOC of day}
        self.daily_warning_families = {} # {pack_num: set of warning lines observed today}

        # Worst cell deviation tracking — per pack (for 19:00 report)
        self.worst_cell_dev       = {}   # {pack_num: {'cell': n, 'dev': float, 'time': str}}

        # Delta window tracking — per pack (12:00 AM - 10:00 AM)
        self.worst_delta          = {}   # {pack_num: {'delta': float, 'time': str}}
        self.delta_window_active  = False
        self.delta_reported_today = False

        # Daily summary tracking
        self.daily_summary_sent_today = False

        # Schedule tracking
        self._last_minute_checked = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _notify_enabled(self, key: str) -> bool:
        return self.config.get('notify_enabled', True) and self.config.get(key, True)

    def _warning_references(self, pack=None, cell_count=None) -> dict:
        if cell_count is None and pack is not None:
            raw_cells = getattr(pack, 'v_cells', []) or []
            cell_count = int(getattr(pack, 'cells', len(raw_cells)) or len(raw_cells))
        return effective_warning_references(self.config, cell_count)

    def _parse_time(self, key: str, default: str) -> tuple:
        t = self.config.get(key, default)
        try:
            h, m = t.split(':')
            return int(h), int(m)
        except Exception:
            d = default.split(':')
            return int(d[0]), int(d[1])

    def _time_matches(self, hour: int, minute: int) -> bool:
        now = datetime.now()
        return now.hour == hour and now.minute == minute

    def _clean_bms_version(self, version: str) -> str:
        """Shorten long Pace/Hubble version strings for Telegram."""
        clean = str(version or "unknown").replace('\x00', '').strip()
        # Many Pace version strings include repeated pack serial fields after '*'.
        # Keep the firmware part only for a clean startup message.
        if '*' in clean:
            clean = clean.split('*', 1)[0].strip()
        return clean[:60] if clean else "unknown"

    def _friendly_warning_lines(self, warning_text: str) -> list[str]:
        """Convert raw BMS warning strings into shorter operator-friendly lines."""
        replacements = {
            'Warning State 1:': '',
            'Warning State 2:': '',
            'Above cell volt warn': 'Above cell voltage',
            'Lower cell volt warn': 'Low cell voltage',
            'Above total volt warn': 'Above total voltage',
            'Lower total volt warn': 'Low total voltage',
            'Charge current warn': 'Charge current warning',
            'Discharge current warn': 'Discharge current warning',
            'Above charge temp warn': 'High charge temperature',
            'Above discharge temp warn': 'High discharge temperature',
            'Low charge temp warn': 'Low charge temperature',
            'Low discharge temp warn': 'Low discharge temperature',
            'High env temp warn': 'High environment temperature',
            'Low env temp warn': 'Low environment temperature',
            'High MOS temp warn': 'High MOS temperature',
            'Low power warn': 'Low power warning',
        }
        items = []
        for part in str(warning_text or '').replace(',', '|').split('|'):
            text = part.strip()
            for old, new in replacements.items():
                text = text.replace(old, new)
            text = text.strip(' :-')
            if text and text not in items:
                items.append(text)
        return items or [warning_text]

    def _midnight_reset(self):
        today = datetime.now().date()
        if self.energy_reset_day != today:
            self.energy_reset_day      = today
            self.kwh_charged           = {}
            self.kwh_discharged        = {}
            self.last_energy_update    = {}
            self.soc_start             = {}
            self.soc_latest            = {}
            self.daily_warning_families = {}
            self.worst_cell_dev        = {}
            # Reset low-SOC threshold notifications daily so a battery that remains
            # low can alert again the next day.
            self.soc_thresholds_hit    = {}

            # Do NOT reset high-SOC notification state here. High-SOC alerts
            # must reset only after SOC drops below notify_soc_high_reset.
            # Resetting this at startup/midnight caused duplicate "Battery
            # Fully Charged" Telegram messages while the pack was still full.
            self.daily_summary_sent_today = False
            self.delta_reported_today  = False
            log.info("Midnight reset: energy, SOC thresholds, daily summary flags cleared")

    # ── Startup / Shutdown ────────────────────────────────────────────────────

    def on_startup(self, bms_sn: str, bms_version: str, restarted: bool = False):
        if not self._notify_enabled('notify_startup'):
            return
        label = "Restarted" if restarted else "Started"
        clean_version = self._clean_bms_version(bms_version)
        telegram_send(self.config,
            f"BMS Monitor {label}\n"
            f"SN: {bms_sn}\n"
            f"Version: {clean_version}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def on_shutdown(self, bms_sn: str):
        if not self._notify_enabled('notify_startup'):
            return
        telegram_send(self.config,
            f"BMS Monitor Stopped\n"
            f"SN: {bms_sn}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ── Disconnect / Recovery ─────────────────────────────────────────────────

    def on_disconnect(self, retry_count: int, offline_str: str):
        """Send one disconnect notification once the retry threshold is reached.

        Uses >= instead of == so a missed/interrupted retry cannot skip the alert.
        Also logs why an alert is not sent, which helps diagnose config issues.
        """
        if not self._notify_enabled('notify_disconnect'):
            log.warning(
                "Disconnect notification skipped: notify_enabled=%s, notify_disconnect=%s",
                self.config.get('notify_enabled', True),
                self.config.get('notify_disconnect', True),
            )
            return

        try:
            threshold = int(self.config.get('notify_retry_count', 3))
        except Exception:
            threshold = 3

        threshold = max(1, threshold)

        if self.disconnect_notified:
            log.debug("Disconnect notification already sent; retry=%s", retry_count)
            return

        if retry_count >= threshold:
            self.disconnect_notified = True
            log.info(
                "Disconnect notification threshold reached: retry=%s threshold=%s",
                retry_count,
                threshold,
            )
            telegram_send(self.config,
                f"BMS Disconnected\n"
                f"Offline: {offline_str}\n"
                f"Retries: {retry_count}\n"
                f"Time: {datetime.now().strftime('%H:%M:%S')}")
        else:
            log.info(
                "Disconnect notification waiting: retry=%s threshold=%s",
                retry_count,
                threshold,
            )

    def on_recovery(self, retry_count: int, offline_str: str):
        if not self._notify_enabled('notify_disconnect'):
            return
        if self.disconnect_notified:
            self.disconnect_notified = False
            telegram_send(self.config,
                f"BMS Reconnected\n"
                f"Was offline: {offline_str}\n"
                f"Took {retry_count} retries\n"
                f"Time: {datetime.now().strftime('%H:%M:%S')}")

    # ── SOC alerts ────────────────────────────────────────────────────────────

    def on_soc_update(self, pack_num: int, soc: float):
        try:
            self.soc_start.setdefault(pack_num, float(soc))
            self.soc_latest[pack_num] = float(soc)
        except Exception:
            pass

        if not self._notify_enabled('notify_soc_low') and not self._notify_enabled('notify_soc_high'):
            return

        # Parse thresholds
        raw        = str(self.config.get('notify_soc_low_thresholds', '75,50,25,10'))
        thresholds = sorted([int(x.strip()) for x in raw.split(',') if x.strip()], reverse=True)
        high_thr   = float(self.config.get('notify_soc_high_threshold', 98))
        high_reset = float(self.config.get('notify_soc_high_reset', 95))

        if pack_num not in self.soc_thresholds_hit:
            self.soc_thresholds_hit[pack_num] = set()

        # Low-SOC startup suppression. If the monitor starts/restarts while a
        # pack is already below one or more low-SOC thresholds, mark those
        # thresholds as handled so Telegram does not replay 75/50/25/10 in one
        # burst. New lower thresholds can still alert later as SOC falls.
        if pack_num not in self.soc_low_initialized:
            self.soc_low_initialized[pack_num] = True
            already_below = {thr for thr in thresholds if soc <= thr}
            if already_below:
                self.soc_thresholds_hit[pack_num].update(already_below)
                log.info(
                    "Low SOC startup alert suppressed for Pack %02d: SOC %.1f%% already below threshold(s) %s",
                    pack_num,
                    soc,
                    ",".join(str(thr) for thr in sorted(already_below, reverse=True)),
                )

        # High-SOC startup suppression. If the monitor starts while the battery
        # is already full, mark it as already notified instead of sending a
        # fresh "Battery Fully Charged" message on every add-on restart.
        if pack_num not in self.soc_high_initialized:
            self.soc_high_initialized[pack_num] = True
            if (
                not bool(self.config.get('notify_soc_high_on_startup', False))
                and soc >= high_thr
            ):
                self.soc_high_notified[pack_num] = True
                self.soc_high_reset_ready[pack_num] = False
                log.info(
                    "High SOC startup alert suppressed for Pack %02d: SOC %.1f%% >= %.1f%%",
                    pack_num, soc, high_thr
                )
            else:
                self.soc_high_notified[pack_num] = False
                self.soc_high_reset_ready[pack_num] = True

        # Low SOC alerts
        if self._notify_enabled('notify_soc_low'):
            for thr in thresholds:
                if soc <= thr and thr not in self.soc_thresholds_hit[pack_num]:
                    self.soc_thresholds_hit[pack_num].add(thr)
                    telegram_send(self.config,
                        f"Low Battery Alert — Pack {pack_num:02d}\n"
                        f"SOC: {soc:.1f}% (threshold: {thr}%)\n"
                        f"Time: {datetime.now().strftime('%H:%M:%S')}")

        # High SOC alert
        if self._notify_enabled('notify_soc_high'):
            if soc <= high_reset:
                self.soc_high_reset_ready[pack_num] = True
                self.soc_high_notified[pack_num]    = False
            if soc >= high_thr and self.soc_high_reset_ready.get(pack_num, True) and not self.soc_high_notified.get(pack_num, False):
                self.soc_high_notified[pack_num]    = True
                self.soc_high_reset_ready[pack_num] = False
                telegram_send(self.config,
                    f"Battery Fully Charged — Pack {pack_num:02d}\n"
                    f"SOC: {soc:.1f}%\n"
                    f"Time: {datetime.now().strftime('%H:%M:%S')}")

    # ── Warning flags ─────────────────────────────────────────────────────────

    def _clean_warning_text(self, warnings: str) -> str:
        """Remove non-actionable status strings from the BMS warning text."""
        ignore = {
            'Control State: Buzzer warn function enabled',
            'Fault State: Undefined',
            'Normal',
            '',
            'None',
        }
        parts = [w.strip() for w in str(warnings or '').split(',') if w.strip() not in ignore]
        return ', '.join(parts) if parts else 'Normal'

    def _format_cells_over_under(self, cells_v: list[float], threshold: float, mode: str) -> list[str]:
        """Return formatted cell lines above or below a voltage threshold."""
        matches = []
        for i, v in enumerate(cells_v, start=1):
            if mode == 'above' and v > threshold:
                matches.append(f"Cell {i:02d}: {v:.3f} V")
            elif mode == 'below' and v < threshold:
                matches.append(f"Cell {i:02d}: {v:.3f} V")
        return matches

    def _warning_cell_numbers(self, warning_text: str, phrase: str) -> list[int]:
        numbers = []
        for part in re.split(r"[\n|,;]+", str(warning_text or "")):
            if phrase not in part.lower():
                continue
            match = re.search(r"\bcell\s*0*(\d+)\b", part, re.IGNORECASE)
            if match:
                numbers.append(int(match.group(1)))
        return sorted(set(numbers))

    def _has_high_cell_warning(self, warning_text: str) -> bool:
        low = str(warning_text or "").lower()
        return (
            ("above cell" in low and "volt" in low)
            or ("above upper limit" in low and "cell" in low)
            or ("cell" in low and "volt protect" in low and "above" in low)
        )

    def _has_low_cell_warning(self, warning_text: str) -> bool:
        low = str(warning_text or "").lower()
        return (
            (("lower cell" in low or "low cell" in low or "below cell" in low) and "volt" in low)
            or ("below lower limit" in low and "cell" in low)
            or ("cell" in low and "volt protect" in low and ("lower" in low or "below" in low))
        )

    def _has_high_pack_warning(self, warning_text: str) -> bool:
        low = str(warning_text or "").lower()
        return (
            ("above total" in low and "volt" in low)
            or ("above pack" in low and "volt" in low)
            or ("total voltage" in low and ("above" in low or "upper" in low))
        )

    def _has_low_pack_warning(self, warning_text: str) -> bool:
        low = str(warning_text or "").lower()
        return (
            ("lower total" in low and "volt" in low)
            or ("low total" in low and "volt" in low)
            or ("below pack" in low and "volt" in low)
            or ("total voltage" in low and ("below" in low or "lower" in low))
        )

    def _reference_margin(self, value: Optional[float], reference: Optional[float], direction: str) -> tuple[str, str]:
        if value is None or reference is None:
            return "Unknown", "Unknown"
        if direction == "above":
            margin = reference - value
            if margin > 0.0005:
                return f"{margin:.3f} V below ref", "Not exceeded"
            if margin < -0.0005:
                return f"{abs(margin):.3f} V above ref", "Exceeded"
            return "0.000 V below ref", "At reference"
        margin = value - reference
        if margin > 0.0005:
            return f"{margin:.3f} V above ref", "Not exceeded"
        if margin < -0.0005:
            return f"{abs(margin):.3f} V below ref", "Exceeded"
        return "0.000 V above ref", "At reference"

    def _warning_detail_row(self, label: str, value: Optional[float], reference: Optional[float], direction: str, notify_key: str = None) -> tuple[str, str]:
        margin, status = self._reference_margin(value, reference, direction)
        value_text = f"{value:.3f} V" if value is not None else "Unknown"
        ref_text = f"{reference:.2f} V" if reference is not None else "Unknown"
        notify_text = "On" if self._notify_enabled('notify_warnings') and (not notify_key or self.config.get(notify_key, True)) else "Off"
        return f"- {label}: {value_text} | Ref: {ref_text} | Margin: {margin} | {status} | Notify: {notify_text}", status

    def _build_warning_detail(self, pack_num: int, cleaned: str, pack=None) -> str:
        """Build a concise Telegram warning message using latest analog data.

        The BMS warning frame tells us the internal warning type. The analog
        frame gives the current cell voltages, pack voltage, temperatures, SOC
        and SOH. Configured thresholds are read-only reference values for the
        Telegram message only; they do not write to or configure the BMS.
        """
        if not self.config.get('notify_warning_detail_enabled', True) or pack is None:
            return cleaned

        try:
            temp_high = float(self.config.get('notify_temp_high_warn_c', 55))
            temp_low  = float(self.config.get('notify_temp_low_warn_c', 0))

            raw_cells = getattr(pack, 'v_cells', []) or []
            cells_v = [float(v) / 1000.0 for v in raw_cells if v is not None and float(v) > 0]
            temps = [float(t) for t in (getattr(pack, 't_cells', []) or []) if t is not None]
            pack_v = float(getattr(pack, 'v_pack', 0.0) or 0.0)
            soc = float(getattr(pack, 'soc', 0.0) or 0.0)
            soh = float(getattr(pack, 'soh', 0.0) or 0.0)
            cell_count = int(getattr(pack, 'cells', len(cells_v)) or len(cells_v))
            delta_mv = float(getattr(pack, 'cell_max_diff', 0.0) or 0.0)
            refs = self._warning_references(pack, cell_count)
            cell_high = refs["cell_high"]
            cell_low = refs["cell_low"]

            friendly = self._friendly_warning_lines(cleaned)
            lines = ["BMS internal warning active:"]
            lines.extend(friendly)

            high_idx = low_idx = None
            high_v = low_v = None
            if cells_v and self.config.get('notify_include_highest_and_lowest_cell', True):
                high_idx, high_v = max(enumerate(cells_v, start=1), key=lambda x: x[1])
                low_idx, low_v = min(enumerate(cells_v, start=1), key=lambda x: x[1])
                lines.extend([
                    "",
                    "Quick Metrics",
                    f"Highest Cell: Cell {high_idx:02d} = {high_v:.3f} V",
                    f"Lowest Cell: Cell {low_idx:02d} = {low_v:.3f} V",
                    f"Delta: {delta_mv:.0f} mV",
                    f"Pack Voltage: {pack_v:.3f} V",
                    f"SOC: {soc:.1f}%",
                    f"SOH: {soh:.1f}%",
                ])
                cycles = getattr(pack, 'cycles', None)
                if cycles is not None:
                    lines.append(f"Cycles: {cycles}")

            exceeded = False
            detail_added = False
            lines.extend(["", "BMS Warning Details"])
            cell_map = {idx: value for idx, value in enumerate(cells_v, start=1)}

            if cells_v:
                if self._has_high_cell_warning(cleaned):
                    candidates = self._warning_cell_numbers(cleaned, "above upper limit")
                    if self.config.get('notify_include_all_cells_above_threshold', True):
                        candidates.extend(idx for idx, value in cell_map.items() if value >= cell_high)
                    if not candidates and high_idx is not None:
                        candidates = [high_idx]
                    candidates = sorted(set(candidates))
                    lines.append("Above upper limit:")
                    for cell_num in candidates:
                        row, status = self._warning_detail_row(f"Cell {cell_num:02d}", cell_map.get(cell_num), cell_high, "above", "notify_alert_cell_high_voltage")
                        lines.append(row)
                        exceeded = exceeded or status == "Exceeded"
                    detail_added = True

                if self._has_low_cell_warning(cleaned):
                    candidates = self._warning_cell_numbers(cleaned, "below lower limit")
                    if self.config.get('notify_include_all_cells_below_threshold', True):
                        candidates.extend(idx for idx, value in cell_map.items() if value <= cell_low)
                    if not candidates and low_idx is not None:
                        candidates = [low_idx]
                    candidates = sorted(set(candidates))
                    lines.append("Below lower limit:")
                    for cell_num in candidates:
                        row, status = self._warning_detail_row(f"Cell {cell_num:02d}", cell_map.get(cell_num), cell_low, "below", "notify_alert_cell_low_voltage")
                        lines.append(row)
                        exceeded = exceeded or status == "Exceeded"
                    detail_added = True

            if self.config.get('notify_include_pack_voltage', True):
                pack_high = cell_high * cell_count if cell_count else 0.0
                pack_low = cell_low * cell_count if cell_count else 0.0
                if self._has_high_pack_warning(cleaned):
                    lines.extend(["", "Pack voltage:"])
                    row, status = self._warning_detail_row("Pack", pack_v, pack_high, "above", "notify_alert_pack_high_voltage")
                    lines.append(row)
                    exceeded = exceeded or status == "Exceeded"
                    detail_added = True
                if self._has_low_pack_warning(cleaned):
                    lines.extend(["", "Low pack voltage:"])
                    row, status = self._warning_detail_row("Pack", pack_v, pack_low, "below", "notify_alert_pack_low_voltage")
                    lines.append(row)
                    exceeded = exceeded or status == "Exceeded"
                    detail_added = True

            if not detail_added:
                lines.append("No configured reference comparison matched this warning text.")

            lines.extend([
                "",
                "Reference Check",
                f"- Cell high reference: {cell_high:.2f} V",
                f"- Pack high reference: {refs['pack_high']:.2f} V" if refs.get("pack_high") is not None else "- Pack high reference: Unknown",
                f"- Battery profile: {refs['profile_label']}",
                f"- Reference source: {'battery profile defaults' if refs.get('source') == 'profile' else 'user custom settings'}",
            ])
            if exceeded:
                lines.append("- One or more measured values exceed the configured reference.")
            else:
                lines.append("- BMS warning is active below configured reference.")

            if temps and 'temp' in cleaned.lower():
                high_t_idx, high_t = max(enumerate(temps, start=1), key=lambda x: x[1])
                low_t_idx, low_t = min(enumerate(temps, start=1), key=lambda x: x[1])
                lines.extend([
                    "",
                    f"Highest temp: Temp {high_t_idx} = {high_t:.1f} °C",
                    f"Lowest temp: Temp {low_t_idx} = {low_t:.1f} °C",
                    f"Temperature references: high {temp_high:.0f} °C / low {temp_low:.0f} °C",
                ])

            lines.extend(["", "Interpretation"])
            if exceeded:
                lines.append("BMS warning is active and at least one current measured value exceeds the configured reference.")
            else:
                lines.append("BMS warning is active even though the configured reference has not been exceeded. This usually means the BMS internal threshold is lower than the dashboard reference, or the warning was triggered briefly before the latest retained reading.")

            lines.extend(["", "Suggested Action"])
            if exceeded:
                lines.append("Review immediately and compare against the battery manufacturer limits.")
            else:
                lines.append("Watch top-of-charge and verify the BMS internal high-cell and pack-voltage thresholds against the configured references.")

            return '\n'.join(lines)
        except Exception as e:
            log.warning("Could not build detailed warning message for pack %s: %s", pack_num, e)
            return cleaned

    def _build_warning_reminder(self, cleaned: str, pack=None) -> str:
        """Build a shorter reminder for an already-active warning."""
        lines = ["Still active:"]
        lines.extend(self._friendly_warning_lines(cleaned))

        if pack is not None:
            try:
                raw_cells = getattr(pack, 'v_cells', []) or []
                cells_v = [float(v) / 1000.0 for v in raw_cells if v is not None and float(v) > 0]
                pack_v = float(getattr(pack, 'v_pack', 0.0) or 0.0)
                soc = float(getattr(pack, 'soc', 0.0) or 0.0)
                delta_mv = float(getattr(pack, 'cell_max_diff', 0.0) or 0.0)
                if cells_v:
                    high_idx, high_v = max(enumerate(cells_v, start=1), key=lambda x: x[1])
                    low_idx, low_v = min(enumerate(cells_v, start=1), key=lambda x: x[1])
                    lines.append(f"Highest: Cell {high_idx:02d} {high_v:.3f} V")
                    lines.append(f"Lowest: Cell {low_idx:02d} {low_v:.3f} V")
                    lines.append(f"Delta: {delta_mv:.0f} mV")
                if pack_v:
                    lines.append(f"Pack voltage: {pack_v:.3f} V")
                lines.append(f"SOC: {soc:.1f}%")
            except Exception:
                pass

        return "\n".join(lines)

    def on_warnings_update(self, pack_num: int, warnings: str, pack=None, severity: str = None, repeat: bool = False):
        if not self._notify_enabled('notify_warnings'):
            return

        cleaned = self._clean_warning_text(warnings)
        self.on_daily_warning_observed(pack_num, cleaned)
        prev = self.last_warnings.get(pack_num, 'Normal')

        if cleaned != prev and cleaned != 'Normal':
            self.last_warnings[pack_num] = cleaned
            if repeat:
                detail = self._build_warning_reminder(cleaned, pack)
                label = "BMS Warning Reminder"
            else:
                detail = self._build_warning_detail(pack_num, cleaned, pack)
                label = "BMS Warning"
            severity_text = f" ({str(severity).title()})" if severity else ""
            telegram_send(self.config,
                f"{label}{severity_text} — Pack {pack_num:02d}\n"
                f"{detail}\n"
                f"Time: {datetime.now().strftime('%H:%M:%S')}")
        elif cleaned == 'Normal' and prev != 'Normal':
            self.last_warnings[pack_num] = 'Normal'
            telegram_send(self.config,
                f"BMS Warning Cleared — Pack {pack_num:02d}\n"
                f"Time: {datetime.now().strftime('%H:%M:%S')}")

    # ── FET alerts ────────────────────────────────────────────────────────────

    def on_fet_update(self, pack_num: int, charge_fet: str, discharge_fet: str, fully: bool = False):
        if not self._notify_enabled('notify_fet'):
            return
        prev_chg  = self.last_charge_fet.get(pack_num)
        prev_dchg = self.last_discharge_fet.get(pack_num)

        alerts = []
        ignore_charge_when_full = bool(self.config.get('notify_ignore_charge_fet_off_when_full', True))
        alert_discharge_off = bool(self.config.get('notify_alert_discharge_fet_off', True))
        try:
            repeat_seconds = max(60.0, float(self.config.get('notify_fet_repeat_seconds', 1800)))
        except Exception:
            repeat_seconds = 1800.0

        def allow_fet_alert(fet_name: str) -> bool:
            key = (pack_num, fet_name)
            now = time.time()
            last_sent = self.last_fet_alert_sent.get(key)
            if last_sent is None:
                self.last_fet_alert_sent[key] = now
                return True
            elapsed = now - float(last_sent or 0.0)
            if elapsed < repeat_seconds:
                log.info(
                    "%s FET OFF alert suppressed for Pack %02d: %.0fs since last send, cooldown %.0fs",
                    fet_name,
                    pack_num,
                    elapsed,
                    repeat_seconds,
                )
                return False
            self.last_fet_alert_sent[key] = now
            return True

        if prev_chg == 'ON' and charge_fet == 'OFF':
            if not (ignore_charge_when_full and fully):
                if allow_fet_alert('Charge'):
                    alerts.append('Charge FET turned OFF unexpectedly')
            else:
                log.info("Charge FET OFF ignored for Pack %02d because pack is fully charged", pack_num)

        if alert_discharge_off and prev_dchg == 'ON' and discharge_fet == 'OFF':
            if allow_fet_alert('Discharge'):
                alerts.append('Discharge FET turned OFF unexpectedly')

        if alerts:
            telegram_send(self.config,
                f"FET Alert — Pack {pack_num:02d}\n" +
                '\n'.join(alerts) +
                f"\nTime: {datetime.now().strftime('%H:%M:%S')}")

        self.last_charge_fet[pack_num]    = charge_fet
        self.last_discharge_fet[pack_num] = discharge_fet

    # ── SOH alert ─────────────────────────────────────────────────────────────

    def on_soh_update(self, pack_num: int, soh: float):
        if not self._notify_enabled('notify_soh'):
            return

        threshold = float(self.config.get('notify_soh_threshold', 95))

        # SOH is slow-moving. Suppress the startup-only alert by default if the
        # monitor starts and the pack is already below the threshold. This avoids
        # a Telegram message on every add-on restart for a known older battery.
        if pack_num not in self.soh_initialized:
            self.soh_initialized[pack_num] = True
            if not bool(self.config.get('notify_soh_on_startup', False)) and soh < threshold:
                self.soh_notified[pack_num] = True
                log.info(
                    "SOH startup alert suppressed for Pack %02d: SOH %.1f%% < %.1f%%",
                    pack_num, soh, threshold
                )
                return

        if soh >= threshold:
            self.soh_notified[pack_num] = False
            return

        if soh < threshold and not self.soh_notified.get(pack_num, False):
            self.soh_notified[pack_num] = True
            telegram_send(self.config,
                f"SOH Degradation Alert — Pack {pack_num:02d}\n"
                f"SOH: {soh:.1f}% (threshold: {threshold:.1f}%)\n"
                f"Time: {datetime.now().strftime('%H:%M:%S')}")

    # ── Energy tracking ───────────────────────────────────────────────────────

    def on_energy_update(self, pack_num: int, voltage: float, current: float, scan_interval: float = 0):
        """Accumulate kWh using actual elapsed time between successful reads."""
        now = time.time()
        last_update = self.last_energy_update.get(pack_num)
        self.last_energy_update[pack_num] = now

        if last_update is None:
            return

        elapsed_seconds = max(0.0, now - last_update)
        if scan_interval:
            elapsed_seconds = min(elapsed_seconds, max(float(scan_interval) * 3, float(scan_interval)))

        power_w   = voltage * current                         # W (positive = charging)
        kwh_delta = abs(power_w) * (elapsed_seconds / 3600) / 1000  # kWh this interval
        current_deadband = float(self.config.get("daily_energy_current_deadband_a", 0.2) or 0.2)

        if pack_num not in self.kwh_charged:
            self.kwh_charged[pack_num]    = 0.0
            self.kwh_discharged[pack_num] = 0.0

        if current > current_deadband:
            self.kwh_charged[pack_num]    += kwh_delta
        elif current < -current_deadband:
            self.kwh_discharged[pack_num] += kwh_delta

    def on_daily_warning_observed(self, pack_num: int, warnings: str):
        cleaned = self._clean_warning_text(warnings)
        if cleaned == "Normal":
            return
        bucket = self.daily_warning_families.setdefault(pack_num, set())
        for line in self._friendly_warning_lines(cleaned):
            if line and line != "Normal":
                bucket.add(line)

    # ── Cell deviation tracking ───────────────────────────────────────────────

    def on_cell_update(self, pack_num: int, cells: list):
        """Track worst cell deviation from pack average. Call every poll."""
        valid = [c for c in cells if c is not None and c > 0]
        if len(valid) < 2:
            return
        avg = sum(valid) / len(valid)
        for i, v in enumerate(valid):
            dev = abs(v - avg)
            prev = self.worst_cell_dev.get(pack_num, {}).get('dev', 0)
            if dev > prev:
                self.worst_cell_dev[pack_num] = {
                    'cell': i + 1,
                    'dev':  round(dev * 1000, 1),   # store as mV
                    'time': datetime.now().strftime('%H:%M'),
                    'volt': round(v, 3),
                    'avg':  round(avg, 3),
                }

    # ── Delta window tracking ─────────────────────────────────────────────────

    def on_delta_update(self, pack_num: int, delta_mv: float):
        """Track worst cell spread during configured window."""
        now  = datetime.now()
        wh, wm = self._parse_time('notify_delta_window_start', '00:00')
        eh, em = self._parse_time('notify_delta_window_end',   '10:00')
        window_start = now.replace(hour=wh, minute=wm, second=0, microsecond=0)
        window_end   = now.replace(hour=eh, minute=em, second=0, microsecond=0)

        if window_start <= now <= window_end:
            prev = self.worst_delta.get(pack_num, {}).get('delta', 0)
            if delta_mv > prev:
                self.worst_delta[pack_num] = {
                    'delta': round(delta_mv, 1),
                    'time':  now.strftime('%H:%M'),
                }

    # ── Scheduled reports ─────────────────────────────────────────────────────

    def check_scheduled(self, pack_count: int):
        """Call every poll cycle. Fires scheduled reports at configured times."""
        self._midnight_reset()
        now         = datetime.now()
        current_min = (now.hour, now.minute)

        if current_min == self._last_minute_checked:
            return
        self._last_minute_checked = current_min

        # ── 19:00 daily summary ───────────────────────────────────────────────
        if self._notify_enabled('notify_daily_summary'):
            sh, sm = self._parse_time('notify_daily_summary_time', '19:00')
            if now.hour == sh and now.minute == sm and not self.daily_summary_sent_today:
                self.daily_summary_sent_today = True
                self._send_daily_summary(pack_count)

        # ── Delta report ──────────────────────────────────────────────────────
        if self._notify_enabled('notify_delta_report'):
            rh, rm = self._parse_time('notify_delta_report_time', '10:15')
            if now.hour == rh and now.minute == rm and not self.delta_reported_today:
                self.delta_reported_today = True
                self._send_delta_report(pack_count)

    def _send_daily_summary(self, pack_count: int):
        lines = [f"Daily BMS Summary — {datetime.now().strftime('%Y-%m-%d')}"]
        for p in range(1, pack_count + 1):
            chg  = self.kwh_charged.get(p, 0.0)
            dchg = self.kwh_discharged.get(p, 0.0)
            wc   = self.worst_cell_dev.get(p, {})
            start_soc = self.soc_start.get(p)
            latest_soc = self.soc_latest.get(p)
            warnings_today = sorted(self.daily_warning_families.get(p, set()))
            lines.append(
                f"\nPack {p:02d}:\n"
            )
            if chg < 0.001 and dchg < 0.001:
                lines.append("  Energy movement: no measurable charge/discharge recorded today")
            else:
                lines.append(f"  Charged:    {chg:.3f} kWh")
                lines.append(f"  Discharged: {dchg:.3f} kWh")
            if start_soc is not None and latest_soc is not None:
                lines.append(f"  SOC: {start_soc:.1f}% -> {latest_soc:.1f}% ({latest_soc - start_soc:+.1f}%)")
            if wc:
                lines.append(
                    f"  Worst cell: Cell {wc['cell']:02d} "
                    f"({wc['dev']} mV from avg) at {wc['time']}\n"
                    f"  Cell V: {wc['volt']}V  Avg: {wc['avg']}V"
                )
            else:
                lines.append("  Worst cell: No data")
            lines.append("  Warnings today: " + (" | ".join(warnings_today[:6]) if warnings_today else "None"))
        telegram_send(self.config, '\n'.join(lines))

    def _send_delta_report(self, pack_count: int):
        wh, wm = self._parse_time('notify_delta_window_start', '00:00')
        eh, em = self._parse_time('notify_delta_window_end',   '10:00')
        lines  = [
            f"Cell Delta Report ({wh:02d}:{wm:02d}-{eh:02d}:{em:02d})\n"
            f"{datetime.now().strftime('%Y-%m-%d')}"
        ]
        for p in range(1, pack_count + 1):
            wd = self.worst_delta.get(p, {})
            if wd:
                lines.append(
                    f"\nPack {p:02d}:\n"
                    f"  Worst delta: {wd['delta']} mV at {wd['time']}"
                )
            else:
                lines.append(f"\nPack {p:02d}: No data in window")
        telegram_send(self.config, '\n'.join(lines))
