"""Live serial snapshot helpers for Pace BMS Monitor.

The monitor owns the serial connection and writes this snapshot for the web UI.
The web UI must never open the BMS serial port itself.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from battery_profiles import effective_warning_references


DATA_DIR = Path(os.environ.get("PACEBMS_DATA_DIR", "/data"))
LIVE_SNAPSHOT_PATH = DATA_DIR / "pacebms-live.json"


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically so readers never see a partial snapshot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    os.replace(tmp_path, path)


def load_live_snapshot(path: Path = LIVE_SNAPSHOT_PATH) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else None
    except FileNotFoundError:
        return None
    except Exception:
        return None


def write_live_snapshot(payload: dict[str, Any], path: Path = LIVE_SNAPSHOT_PATH) -> None:
    atomic_write_json(path, payload)


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _onoff(value: Any) -> str:
    return "ON" if bool(value) else "OFF"


def _format_cell_extreme(cell_values: list[tuple[int, float]], high: bool) -> dict[str, str]:
    if not cell_values:
        return {"number": "Unknown", "voltage": "Unknown"}
    cell_num, cell_v = (max if high else min)(cell_values, key=lambda item: item[1])
    return {"number": f"{cell_num:02d}", "voltage": f"{cell_v:.3f}"}


def _warning_map(warn_list: list[Any] | None) -> dict[int, Any]:
    result: dict[int, Any] = {}
    for item in warn_list or []:
        result[_safe_int(getattr(item, "pack_number", 0), 0)] = item
    return result


def _extract_warning_cell_numbers(warnings: str, phrase: str) -> list[int]:
    numbers = []
    for part in re.split(r"[\n|,;]+", str(warnings or "")):
        if phrase not in part.lower():
            continue
        match = re.search(r"\bcell\s*0*(\d+)\b", part, re.IGNORECASE)
        if match:
            numbers.append(int(match.group(1)))
    return sorted(set(numbers))


def _warning_cell_label_map(warnings: str) -> dict[int, list[str]]:
    labels: dict[int, list[str]] = {}
    for cell_num in _extract_warning_cell_numbers(warnings, "above upper limit"):
        labels.setdefault(cell_num, []).append("BMS High Warning")
    for cell_num in _extract_warning_cell_numbers(warnings, "below lower limit"):
        labels.setdefault(cell_num, []).append("BMS Low Warning")
    return labels


def _has_bms_high_cell_warning(warnings: str) -> bool:
    low = str(warnings or "").lower()
    return (
        ("above cell" in low and "volt" in low)
        or ("above upper limit" in low and "cell" in low)
        or ("cell" in low and "volt protect" in low and "above" in low)
    )


def _has_bms_low_cell_warning(warnings: str) -> bool:
    low = str(warnings or "").lower()
    return (
        (("lower cell" in low or "low cell" in low or "below cell" in low) and "volt" in low)
        or ("below lower limit" in low and "cell" in low)
        or ("cell" in low and "volt protect" in low and ("lower" in low or "below" in low))
    )


def _add_warning_fallback_labels(labels: dict[int, list[str]], warnings: str, highest_cell_num: int | None, lowest_cell_num: int | None) -> dict[int, list[str]]:
    if _has_bms_high_cell_warning(warnings) and highest_cell_num is not None:
        labels.setdefault(highest_cell_num, [])
        if "BMS High Warning" not in labels[highest_cell_num]:
            labels[highest_cell_num].append("BMS High Warning")
    if _has_bms_low_cell_warning(warnings) and lowest_cell_num is not None:
        labels.setdefault(lowest_cell_num, [])
        if "BMS Low Warning" not in labels[lowest_cell_num]:
            labels[lowest_cell_num].append("BMS Low Warning")
    return labels


def build_live_snapshot(
    config: dict[str, Any],
    analog_data: Any | None = None,
    capacity: Any | None = None,
    warn_list: list[Any] | None = None,
    *,
    bms_sn: str = "Unknown",
    pack_sn: str = "Unknown",
    bms_version: str = "Unknown",
    monitor_state: str = "running",
    availability: str = "online",
    stale: str = "OFF",
    stale_reason: str = "Fresh",
    last_analog_success: float | None = None,
    last_warn_success: float | None = None,
    source: str = "live_serial",
) -> dict[str, Any]:
    """Build a web-compatible live snapshot from validated BMS data."""
    now = time.time()
    last_analog_success = last_analog_success or now
    last_warn_success = last_warn_success or now
    warnings_by_pack = _warning_map(warn_list)

    packs = []
    total_cells = 0
    warning_count = 0
    severity_summary: dict[str, int] = {}

    for pack in getattr(analog_data, "pack_data", []) or []:
        pack_number = _safe_int(getattr(pack, "pack_number", 0), 0)
        pack_id = f"{pack_number:02d}" if pack_number else "Unknown"
        cell_count = _safe_int(getattr(pack, "cells", 0), 0)
        total_cells += cell_count

        refs = effective_warning_references(config, cell_count)
        cell_high_ref = _safe_float(refs.get("cell_high"))
        cell_low_ref = _safe_float(refs.get("cell_low"))
        pack_high_ref = _safe_float(refs.get("pack_high"))
        pack_low_ref = _safe_float(refs.get("pack_low"))

        raw_cells = list(getattr(pack, "v_cells", []) or [])
        cell_values = [(idx + 1, _safe_float(value, 0.0) / 1000.0) for idx, value in enumerate(raw_cells)]
        highest_cell = _format_cell_extreme(cell_values, high=True)
        lowest_cell = _format_cell_extreme(cell_values, high=False)
        warn = warnings_by_pack.get(pack_number)
        warning_text = str(getattr(warn, "warnings", "") or "Normal")
        high_num = _safe_int(highest_cell.get("number"), -1)
        low_num = _safe_int(lowest_cell.get("number"), -1)
        bms_cell_warning_labels = _add_warning_fallback_labels(
            _warning_cell_label_map(warning_text),
            warning_text,
            high_num if high_num > 0 else None,
            low_num if low_num > 0 else None,
        )

        detailed_cells = []
        for cell_num, cell_v in cell_values:
            labels = []
            if cell_num == high_num:
                labels.append("Highest")
            if cell_num == low_num:
                labels.append("Lowest")
            labels.extend(bms_cell_warning_labels.get(cell_num, []))
            if cell_high_ref is not None and cell_v > cell_high_ref:
                labels.append("Above high reference")
            if cell_low_ref is not None and cell_v < cell_low_ref:
                labels.append("Below low reference")
            detailed_cells.append({
                "number": f"{cell_num:02d}",
                "voltage": f"{cell_v:.3f}",
                "labels": labels,
                "class": "cell-alert" if any(("reference" in label or label.startswith("BMS ")) for label in labels) else ("cell-highlow" if labels else "cell-normal"),
            })

        has_warning = warning_text != "Normal"
        if has_warning:
            warning_count += 1
        severity_label = "Warning" if has_warning else "Normal"
        severity_class = "warning" if has_warning else "healthy"
        severity_summary[severity_label] = severity_summary.get(severity_label, 0) + 1

        pack_v = _safe_float(getattr(pack, "v_pack", None))
        pack_current = _safe_float(getattr(pack, "i_pack", None))
        pack_power_kw = (pack_v * pack_current / 1000.0) if pack_v is not None and pack_current is not None else None

        reference_checks = []
        if has_warning:
            reference_checks.append("BMS warning is active. Review measured values against configured references.")
        else:
            reference_checks.append("No active BMS warning.")

        is_master = pack_number == 1
        serial_display = str(pack_sn or bms_sn or "Unknown") if is_master else "N/A"

        packs.append({
            "id": pack_id,
            "role": "Master" if is_master else "Slave",
            "serial": serial_display,
            "serial_note": "Reported by BMS" if is_master else "Current BMS read does not expose a separate serial for this pack",
            "cell_count": cell_count,
            "soc": str(getattr(pack, "soc", "Unknown")),
            "soh": str(min(_safe_float(getattr(pack, "soh", 0), 0.0), 100.0)),
            "cycles": str(getattr(pack, "cycles", "Unknown")),
            "remaining_capacity_ah": str(int((_safe_float(getattr(pack, "i_remain_cap", 0), 0.0) / 1000.0) + 0.5)),
            "full_capacity_ah": str(int((_safe_float(getattr(pack, "i_full_cap", 0), 0.0) / 1000.0) + 0.5)),
            "design_capacity_ah": str(int((_safe_float(getattr(pack, "i_design_cap", 0), 0.0) / 1000.0) + 0.5)),
            "voltage": f"{pack_v:.3f}" if pack_v is not None else "Unknown",
            "current": f"{pack_current:.2f}" if pack_current is not None else "Unknown",
            "power_kw": f"{pack_power_kw:.2f}" if pack_power_kw is not None else "Unknown",
            "delta": str(getattr(pack, "cell_max_diff", "Unknown")),
            "temperatures": list(getattr(pack, "t_cells", []) or []),
            "warnings": warning_text,
            "has_warning": has_warning,
            "severity_class": severity_class,
            "severity_label": severity_label,
            "highest_cell": highest_cell,
            "lowest_cell": lowest_cell,
            "cells": detailed_cells,
            "cell_high_ref": f"{cell_high_ref:.2f}" if cell_high_ref is not None else "Unknown",
            "cell_low_ref": f"{cell_low_ref:.2f}" if cell_low_ref is not None else "Unknown",
            "pack_high_ref": f"{pack_high_ref:.2f}" if pack_high_ref is not None else "Unknown",
            "pack_low_ref": f"{pack_low_ref:.2f}" if pack_low_ref is not None else "Unknown",
            "battery_profile": refs.get("profile_label", "Unknown"),
            "reference_source": "battery profile defaults" if refs.get("source") == "profile" else "user custom settings",
            "reference_checks": reference_checks,
            "charge_fet": _onoff(getattr(warn, "charge_fet", False)) if warn is not None else "Unknown",
            "discharge_fet": _onoff(getattr(warn, "discharge_fet", False)) if warn is not None else "Unknown",
            "fully": _onoff(getattr(warn, "fully", False)) if warn is not None else "Unknown",
        })

    chart_data = []
    for pack in packs:
        highest_v = _safe_float(pack.get("highest_cell", {}).get("voltage"), 0.0)
        lowest_v = _safe_float(pack.get("lowest_cell", {}).get("voltage"), 0.0)
        chart_data.append({
            "pack": f"Pack {pack.get('id')}",
            "soc": _safe_float(pack.get("soc"), 0.0),
            "soh": _safe_float(pack.get("soh"), 0.0),
            "voltage": _safe_float(pack.get("voltage"), 0.0),
            "delta": _safe_float(pack.get("delta"), 0.0),
            "highest_cell": highest_v,
            "lowest_cell": lowest_v,
        })

    layout = "Unknown"
    if packs:
        cell_layout = ", ".join(f"Pack {p['id']}: {p['cell_count']} cells" for p in packs)
        layout = f"{len(packs)} pack(s), {total_cells} cells total - {cell_layout}"

    analog_age = max(0, int(now - last_analog_success))
    warn_age = max(0, int(now - last_warn_success))

    return {
        "ok": bool(packs),
        "source": source,
        "data_source": "Live serial",
        "snapshot_id": int(now * 1000),
        "updated_at_epoch": int(now),
        "fetched_at": datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S"),
        "base_topic": str(config.get("mqtt_base_topic", "pacebms")),
        "availability": availability,
        "monitor_state": monitor_state,
        "last_analog_read": datetime.fromtimestamp(last_analog_success).strftime("%Y-%m-%d %H:%M:%S"),
        "last_warn_read": datetime.fromtimestamp(last_warn_success).strftime("%Y-%m-%d %H:%M:%S"),
        "stale": stale,
        "stale_reason": stale_reason,
        "analog_age_seconds": analog_age,
        "warn_age_seconds": warn_age,
        "bms_status": "Live serial snapshot",
        "bms_error": "Not available",
        "bms_version": bms_version or "Unknown",
        "bms_sn": bms_sn or "Unknown",
        "pack_sn": pack_sn or "Unknown",
        "pack_count": len(packs),
        "total_cells": total_cells,
        "layout": layout,
        "overall_status": "Warning" if warning_count else ("Healthy" if packs else "Unknown"),
        "overall_class": "warning" if warning_count else ("healthy" if packs else "unknown"),
        "warning_count": warning_count,
        "severity_summary": severity_summary,
        "cell_high_ref": config.get("notify_cell_high_warn_voltage", 4.20),
        "cell_low_ref": config.get("notify_cell_low_warn_voltage", 3.00),
        "packs": packs,
        "chart_data": chart_data,
        "capacity": {
            "remain_cap_ah": int((_safe_float(getattr(capacity, "remain_cap", 0), 0.0) / 1000.0) + 0.5) if capacity else None,
            "full_cap_ah": int((_safe_float(getattr(capacity, "full_cap", 0), 0.0) / 1000.0) + 0.5) if capacity else None,
            "design_cap_ah": int((_safe_float(getattr(capacity, "design_cap", 0), 0.0) / 1000.0) + 0.5) if capacity else None,
            "soc": getattr(capacity, "soc", None) if capacity else None,
            "soh": getattr(capacity, "soh", None) if capacity else None,
        },
        "data_quality": {
            "valid": bool(packs),
            "invalid": False,
            "stale": stale == "ON",
            "source": source,
        },
    }
