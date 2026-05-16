# =============================================================================
# bms_notify.py — Notification Engine for Pace BMS Monitor
# Version : 1.0.0
# Changed : 2026-05-16
# Handles all Telegram notifications directly from Python.
# No dependency on HA automations.
# =============================================================================

import time
import json
import logging
import urllib.request
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("bmspace")


# ─── Telegram sender ──────────────────────────────────────────────────────────

def telegram_send(config: dict, message: str):
    """Send a Telegram message directly via Bot API."""
    if not config.get('notify_enabled', True):
        return
    token   = config.get('telegram_bot_token', '')
    chat_id = config.get('telegram_chat_id', '')
    if not token or not chat_id:
        log.warning("Telegram not configured — skipping notification")
        return
    try:
        url     = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": message}).encode()
        req     = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        log.info("Telegram sent: %s", message[:60])
    except Exception as e:
        log.warning("Telegram failed: %s", e)


# ─── Notification state ───────────────────────────────────────────────────────

class NotifyState:
    """Tracks all notification state to prevent duplicates and manage thresholds."""

    def __init__(self, config: dict):
        self.config = config

        # SOC threshold tracking — per pack, per threshold
        self.soc_thresholds_hit   = {}   # {pack_num: set of thresholds already notified}
        self.soc_high_notified    = {}   # {pack_num: bool}
        self.soc_high_reset_ready = {}   # {pack_num: bool} — True once SOC drops below reset level

        # Warning tracking — per pack
        self.last_warnings        = {}   # {pack_num: str} — last warning string sent

        # FET tracking — per pack
        self.last_charge_fet      = {}   # {pack_num: str} ON/OFF
        self.last_discharge_fet   = {}   # {pack_num: str} ON/OFF
        self.fet_notified         = {}   # {pack_num: bool} — suppresses repeat FET alerts

        # SOH tracking — per pack
        self.soh_notified         = {}   # {pack_num: bool}

        # Disconnect tracking
        self.disconnect_time      = None
        self.retry_count          = 0
        self.disconnect_notified  = False  # True after retry threshold hit
        self.recovery_notified    = False

        # Energy tracking — per pack
        self.kwh_charged          = {}   # {pack_num: float}
        self.kwh_discharged       = {}   # {pack_num: float}
        self.energy_reset_day     = None  # date of last midnight reset

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

    def _midnight_reset(self):
        today = datetime.now().date()
        if self.energy_reset_day != today:
            self.energy_reset_day      = today
            self.kwh_charged           = {}
            self.kwh_discharged        = {}
            self.worst_cell_dev        = {}
            self.soc_thresholds_hit    = {}
            self.soc_high_notified     = {}
            self.soc_high_reset_ready  = {}
            self.daily_summary_sent_today = False
            self.delta_reported_today  = False
            log.info("Midnight reset: energy, SOC thresholds, daily summary flags cleared")

    # ── Startup / Shutdown ────────────────────────────────────────────────────

    def on_startup(self, bms_sn: str, bms_version: str, restarted: bool = False):
        if not self._notify_enabled('notify_startup'):
            return
        label = "Restarted" if restarted else "Started"
        telegram_send(self.config,
            f"BMS Monitor {label}\n"
            f"SN: {bms_sn}\n"
            f"Version: {bms_version}\n"
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
        if not self._notify_enabled('notify_disconnect'):
            return
        threshold = int(self.config.get('notify_retry_count', 3))
        if retry_count == threshold and not self.disconnect_notified:
            self.disconnect_notified = True
            telegram_send(self.config,
                f"BMS Disconnected\n"
                f"Offline: {offline_str}\n"
                f"Retries: {retry_count}\n"
                f"Time: {datetime.now().strftime('%H:%M:%S')}")

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
        if not self._notify_enabled('notify_soc_low') and not self._notify_enabled('notify_soc_high'):
            return

        # Parse thresholds
        raw        = str(self.config.get('notify_soc_low_thresholds', '75,50,25,10'))
        thresholds = sorted([int(x.strip()) for x in raw.split(',')], reverse=True)
        high_thr   = float(self.config.get('notify_soc_high_threshold', 98))
        high_reset = float(self.config.get('notify_soc_high_reset', 95))

        if pack_num not in self.soc_thresholds_hit:
            self.soc_thresholds_hit[pack_num]    = set()
            self.soc_high_notified[pack_num]     = False
            self.soc_high_reset_ready[pack_num]  = True

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
            if soc >= high_thr and self.soc_high_reset_ready[pack_num] and not self.soc_high_notified[pack_num]:
                self.soc_high_notified[pack_num]    = True
                self.soc_high_reset_ready[pack_num] = False
                telegram_send(self.config,
                    f"Battery Fully Charged — Pack {pack_num:02d}\n"
                    f"SOC: {soc:.1f}%\n"
                    f"Time: {datetime.now().strftime('%H:%M:%S')}")

    # ── Warning flags ─────────────────────────────────────────────────────────

    def on_warnings_update(self, pack_num: int, warnings: str):
        if not self._notify_enabled('notify_warnings'):
            return
        normal_states = {'Normal', '', 'None'}
        # Strip known non-alarm states
        ignore = {'Control State: Buzzer warn function enabled', 'Fault State: Undefined'}
        parts   = [w.strip() for w in warnings.split(',') if w.strip() not in ignore]
        cleaned = ', '.join(parts) if parts else 'Normal'

        prev = self.last_warnings.get(pack_num, 'Normal')
        if cleaned != prev and cleaned != 'Normal':
            self.last_warnings[pack_num] = cleaned
            telegram_send(self.config,
                f"BMS Warning — Pack {pack_num:02d}\n"
                f"{cleaned}\n"
                f"Time: {datetime.now().strftime('%H:%M:%S')}")
        elif cleaned == 'Normal' and prev != 'Normal':
            self.last_warnings[pack_num] = 'Normal'
            telegram_send(self.config,
                f"BMS Warning Cleared — Pack {pack_num:02d}\n"
                f"Time: {datetime.now().strftime('%H:%M:%S')}")

    # ── FET alerts ────────────────────────────────────────────────────────────

    def on_fet_update(self, pack_num: int, charge_fet: str, discharge_fet: str):
        if not self._notify_enabled('notify_fet'):
            return
        prev_chg  = self.last_charge_fet.get(pack_num)
        prev_dchg = self.last_discharge_fet.get(pack_num)

        alerts = []
        if prev_chg == 'ON' and charge_fet == 'OFF':
            alerts.append('Charge FET turned OFF unexpectedly')
        if prev_dchg == 'ON' and discharge_fet == 'OFF':
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
        if soh < threshold and not self.soh_notified.get(pack_num, False):
            self.soh_notified[pack_num] = True
            telegram_send(self.config,
                f"SOH Degradation Alert — Pack {pack_num:02d}\n"
                f"SOH: {soh:.1f}% (threshold: {threshold}%)\n"
                f"Time: {datetime.now().strftime('%H:%M:%S')}")

    # ── Energy tracking ───────────────────────────────────────────────────────

    def on_energy_update(self, pack_num: int, voltage: float, current: float, scan_interval: float):
        """Accumulate kWh. Call every poll cycle."""
        power_w   = voltage * current                         # W (negative = charging)
        kwh_delta = abs(power_w) * (scan_interval / 3600) / 1000  # kWh this interval

        if pack_num not in self.kwh_charged:
            self.kwh_charged[pack_num]    = 0.0
            self.kwh_discharged[pack_num] = 0.0

        if current < 0:
            self.kwh_charged[pack_num]    += kwh_delta
        elif current > 0:
            self.kwh_discharged[pack_num] += kwh_delta

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
            lines.append(
                f"\nPack {p:02d}:\n"
                f"  Charged:    {chg:.3f} kWh\n"
                f"  Discharged: {dchg:.3f} kWh\n"
            )
            if wc:
                lines.append(
                    f"  Worst cell: Cell {wc['cell']:02d} "
                    f"({wc['dev']} mV from avg) at {wc['time']}\n"
                    f"  Cell V: {wc['volt']}V  Avg: {wc['avg']}V"
                )
            else:
                lines.append("  Worst cell: No data")
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
