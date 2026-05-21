"""SQLite history storage for Pace BMS Monitor.

History writes are queued so serial polling remains the highest-priority work.
"""

from __future__ import annotations

import os
import queue
import sqlite3
import threading
import time
import logging
from pathlib import Path
from typing import Any


DATA_DIR = Path(os.environ.get("PACEBMS_DATA_DIR", "/data"))
HISTORY_DB_PATH = DATA_DIR / "pacebms_metrics.db"
log = logging.getLogger("bmspace")


def bool_option(config: dict[str, Any], key: str, default: bool = True) -> bool:
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}


def int_option(config: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(float(str(config.get(key, default)).replace(",", ".")))
    except Exception:
        return default


def float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def init_history_db(db_path: Path = HISTORY_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS bank_metrics (
                ts INTEGER NOT NULL,
                snapshot_id INTEGER NOT NULL,
                source TEXT,
                pack_count INTEGER,
                total_cells INTEGER,
                avg_voltage REAL,
                total_current REAL,
                total_power_kw REAL,
                combined_soc REAL,
                combined_soh REAL,
                remaining_ah REAL,
                full_ah REAL,
                design_ah REAL,
                warning_count INTEGER
            );

            CREATE TABLE IF NOT EXISTS pack_metrics (
                ts INTEGER NOT NULL,
                snapshot_id INTEGER NOT NULL,
                pack_id TEXT NOT NULL,
                role TEXT,
                soc REAL,
                soh REAL,
                voltage REAL,
                current REAL,
                power_kw REAL,
                remaining_ah REAL,
                full_ah REAL,
                design_ah REAL,
                cycles INTEGER,
                cell_delta_mv REAL,
                highest_cell TEXT,
                highest_cell_v REAL,
                lowest_cell TEXT,
                lowest_cell_v REAL,
                warnings TEXT,
                severity TEXT,
                charge_fet TEXT,
                discharge_fet TEXT,
                fully TEXT
            );

            CREATE TABLE IF NOT EXISTS cell_metrics (
                ts INTEGER NOT NULL,
                snapshot_id INTEGER NOT NULL,
                pack_id TEXT NOT NULL,
                cell_number INTEGER NOT NULL,
                voltage REAL
            );

            CREATE TABLE IF NOT EXISTS temperature_metrics (
                ts INTEGER NOT NULL,
                snapshot_id INTEGER NOT NULL,
                pack_id TEXT NOT NULL,
                sensor_number INTEGER NOT NULL,
                temperature REAL
            );

            CREATE TABLE IF NOT EXISTS warning_events (
                ts INTEGER NOT NULL,
                snapshot_id INTEGER,
                pack_id TEXT,
                severity TEXT,
                title TEXT,
                message TEXT
            );

            CREATE TABLE IF NOT EXISTS system_events (
                ts INTEGER NOT NULL,
                source TEXT,
                severity TEXT,
                title TEXT,
                message TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_bank_metrics_ts ON bank_metrics(ts);
            CREATE INDEX IF NOT EXISTS idx_pack_metrics_ts_pack ON pack_metrics(ts, pack_id);
            CREATE INDEX IF NOT EXISTS idx_cell_metrics_ts_pack ON cell_metrics(ts, pack_id);
            CREATE INDEX IF NOT EXISTS idx_temp_metrics_ts_pack ON temperature_metrics(ts, pack_id);
            CREATE INDEX IF NOT EXISTS idx_warning_events_ts ON warning_events(ts);
            CREATE INDEX IF NOT EXISTS idx_system_events_ts ON system_events(ts);
            """
        )
        conn.commit()
    finally:
        conn.close()


def _combined_values(snapshot: dict[str, Any]) -> dict[str, float | int | None]:
    packs = snapshot.get("packs") if isinstance(snapshot, dict) else []
    packs = packs if isinstance(packs, list) else []
    voltages = []
    currents = []
    powers = []
    socs = []
    sohs = []
    remaining = []
    full = []
    design = []

    for pack in packs:
        voltage = float_or_none(pack.get("voltage"))
        current = float_or_none(pack.get("current"))
        power = float_or_none(pack.get("power_kw"))
        soc = float_or_none(pack.get("soc"))
        soh = float_or_none(pack.get("soh"))
        remain = float_or_none(pack.get("remaining_capacity_ah"))
        full_ah = float_or_none(pack.get("full_capacity_ah"))
        design_ah = float_or_none(pack.get("design_capacity_ah"))
        if voltage is not None:
            voltages.append(voltage)
        if current is not None:
            currents.append(current)
        if power is not None:
            powers.append(power)
        if soc is not None:
            socs.append(soc)
        if soh is not None:
            sohs.append(soh)
        if remain is not None:
            remaining.append(remain)
        if full_ah is not None:
            full.append(full_ah)
        if design_ah is not None:
            design.append(design_ah)

    return {
        "avg_voltage": sum(voltages) / len(voltages) if voltages else None,
        "total_current": sum(currents) if currents else None,
        "total_power_kw": sum(powers) if powers else None,
        "combined_soc": sum(socs) / len(socs) if socs else None,
        "combined_soh": sum(sohs) / len(sohs) if sohs else None,
        "remaining_ah": sum(remaining) if remaining else None,
        "full_ah": sum(full) if full else None,
        "design_ah": sum(design) if design else None,
    }


def write_snapshot(conn: sqlite3.Connection, snapshot: dict[str, Any], include_cells: bool = True) -> None:
    ts = int(snapshot.get("updated_at_epoch") or time.time())
    snapshot_id = int(snapshot.get("snapshot_id") or ts * 1000)
    combined = _combined_values(snapshot)
    packs = snapshot.get("packs") if isinstance(snapshot.get("packs"), list) else []

    conn.execute(
        """
        INSERT INTO bank_metrics (
            ts, snapshot_id, source, pack_count, total_cells, avg_voltage,
            total_current, total_power_kw, combined_soc, combined_soh,
            remaining_ah, full_ah, design_ah, warning_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ts,
            snapshot_id,
            snapshot.get("source"),
            int(snapshot.get("pack_count") or len(packs)),
            int(snapshot.get("total_cells") or 0),
            combined["avg_voltage"],
            combined["total_current"],
            combined["total_power_kw"],
            combined["combined_soc"],
            combined["combined_soh"],
            combined["remaining_ah"],
            combined["full_ah"],
            combined["design_ah"],
            int(snapshot.get("warning_count") or 0),
        ),
    )

    for pack in packs:
        pack_id = str(pack.get("id") or "")
        conn.execute(
            """
            INSERT INTO pack_metrics (
                ts, snapshot_id, pack_id, role, soc, soh, voltage, current,
                power_kw, remaining_ah, full_ah, design_ah, cycles,
                cell_delta_mv, highest_cell, highest_cell_v, lowest_cell,
                lowest_cell_v, warnings, severity, charge_fet, discharge_fet, fully
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                snapshot_id,
                pack_id,
                pack.get("role"),
                float_or_none(pack.get("soc")),
                float_or_none(pack.get("soh")),
                float_or_none(pack.get("voltage")),
                float_or_none(pack.get("current")),
                float_or_none(pack.get("power_kw")),
                float_or_none(pack.get("remaining_capacity_ah")),
                float_or_none(pack.get("full_capacity_ah")),
                float_or_none(pack.get("design_capacity_ah")),
                int(float_or_none(pack.get("cycles")) or 0),
                float_or_none(pack.get("delta")),
                (pack.get("highest_cell") or {}).get("number") if isinstance(pack.get("highest_cell"), dict) else None,
                float_or_none((pack.get("highest_cell") or {}).get("voltage") if isinstance(pack.get("highest_cell"), dict) else None),
                (pack.get("lowest_cell") or {}).get("number") if isinstance(pack.get("lowest_cell"), dict) else None,
                float_or_none((pack.get("lowest_cell") or {}).get("voltage") if isinstance(pack.get("lowest_cell"), dict) else None),
                pack.get("warnings"),
                pack.get("severity_label"),
                pack.get("charge_fet"),
                pack.get("discharge_fet"),
                pack.get("fully"),
            ),
        )

        if include_cells:
            for cell in pack.get("cells") or []:
                conn.execute(
                    "INSERT INTO cell_metrics (ts, snapshot_id, pack_id, cell_number, voltage) VALUES (?, ?, ?, ?, ?)",
                    (ts, snapshot_id, pack_id, int(cell.get("number") or 0), float_or_none(cell.get("voltage"))),
                )
            for idx, temp in enumerate(pack.get("temperatures") or [], start=1):
                conn.execute(
                    "INSERT INTO temperature_metrics (ts, snapshot_id, pack_id, sensor_number, temperature) VALUES (?, ?, ?, ?, ?)",
                    (ts, snapshot_id, pack_id, idx, float_or_none(temp)),
                )


def cleanup_history(conn: sqlite3.Connection, raw_retention_days: int, event_retention_days: int) -> None:
    now = int(time.time())
    raw_cutoff = now - max(1, raw_retention_days) * 86400
    event_cutoff = now - max(1, event_retention_days) * 86400
    for table in ("bank_metrics", "pack_metrics", "cell_metrics", "temperature_metrics"):
        conn.execute(f"DELETE FROM {table} WHERE ts < ?", (raw_cutoff,))
    for table in ("warning_events", "system_events"):
        conn.execute(f"DELETE FROM {table} WHERE ts < ?", (event_cutoff,))


class HistoryWriter:
    def __init__(self, config: dict[str, Any], db_path: Path = HISTORY_DB_PATH):
        self.enabled = bool_option(config, "metrics_enabled", True)
        self.raw_retention_days = int_option(config, "history_retention_days", 90)
        self.event_retention_days = int_option(config, "history_event_retention_days", 365)
        self.db_path = db_path
        self.queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=200)
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.last_cleanup = 0

    def start(self) -> None:
        if not self.enabled:
            return
        try:
            init_history_db(self.db_path)
        except Exception as exc:
            log.warning("History database initialization failed; continuing without history writer: %s", exc)
            self.enabled = False
            return
        self.thread = threading.Thread(target=self._run, name="pacebms-history-writer", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)

    def record_snapshot(self, snapshot: dict[str, Any], include_cells: bool = True) -> None:
        if not self.enabled or not snapshot:
            return
        try:
            self.queue.put_nowait(("snapshot", (dict(snapshot), bool(include_cells))))
        except queue.Full:
            log.warning("History writer queue full; dropped snapshot sample")

    def record_system_event(self, source: str, severity: str, title: str, message: str = "") -> None:
        if not self.enabled:
            return
        try:
            self.queue.put_nowait(("system_event", {
                "ts": int(time.time()),
                "source": source,
                "severity": severity,
                "title": title,
                "message": message,
            }))
        except queue.Full:
            log.warning("History writer queue full; dropped system event: %s", title)

    def record_warning_event(self, snapshot_id: int | None, pack_id: str, severity: str, title: str, message: str = "") -> None:
        if not self.enabled:
            return
        try:
            self.queue.put_nowait(("warning_event", {
                "ts": int(time.time()),
                "snapshot_id": snapshot_id,
                "pack_id": pack_id,
                "severity": severity,
                "title": title,
                "message": message,
            }))
        except queue.Full:
            log.warning("History writer queue full; dropped warning event for pack %s: %s", pack_id, title)

    def _run(self) -> None:
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
        except Exception as exc:
            log.warning("History writer could not open SQLite database; history disabled until restart: %s", exc)
            self.enabled = False
            return
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            while not self.stop_event.is_set():
                try:
                    item_type, payload = self.queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                try:
                    if item_type == "snapshot":
                        snapshot, include_cells = payload
                        write_snapshot(conn, snapshot, include_cells=include_cells)
                    elif item_type == "system_event":
                        conn.execute(
                            "INSERT INTO system_events (ts, source, severity, title, message) VALUES (?, ?, ?, ?, ?)",
                            (payload["ts"], payload["source"], payload["severity"], payload["title"], payload["message"]),
                        )
                    elif item_type == "warning_event":
                        conn.execute(
                            "INSERT INTO warning_events (ts, snapshot_id, pack_id, severity, title, message) VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                payload["ts"],
                                payload["snapshot_id"],
                                payload["pack_id"],
                                payload["severity"],
                                payload["title"],
                                payload["message"],
                            ),
                        )
                    if time.time() - self.last_cleanup > 86400:
                        cleanup_history(conn, self.raw_retention_days, self.event_retention_days)
                        self.last_cleanup = time.time()
                    conn.commit()
                except Exception as exc:
                    log.warning("History writer failed to store %s sample: %s", item_type, exc)
                    try:
                        conn.rollback()
                    except Exception:
                        pass
        finally:
            conn.close()


def query_history(range_seconds: int = 1800, db_path: Path = HISTORY_DB_PATH) -> dict[str, Any]:
    init_history_db(db_path)
    since = int(time.time()) - max(60, int(range_seconds))
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        bank_rows = conn.execute(
            """
            SELECT ts, avg_voltage, total_current, total_power_kw, combined_soc,
                   combined_soh, remaining_ah, full_ah, design_ah, warning_count
            FROM bank_metrics
            WHERE ts >= ?
            ORDER BY ts ASC
            """,
            (since,),
        ).fetchall()
        pack_rows = conn.execute(
            """
            SELECT ts, pack_id, soc, soh, voltage, current, power_kw, cell_delta_mv,
                   highest_cell_v, lowest_cell_v
            FROM pack_metrics
            WHERE ts >= ?
            ORDER BY ts ASC, pack_id ASC
            """,
            (since,),
        ).fetchall()
        warning_rows = conn.execute(
            """
            SELECT ts, snapshot_id, pack_id, severity, title, message
            FROM warning_events
            WHERE ts >= ?
            ORDER BY ts ASC
            """,
            (since,),
        ).fetchall()
        system_rows = conn.execute(
            """
            SELECT ts, source, severity, title, message
            FROM system_events
            WHERE ts >= ?
            ORDER BY ts ASC
            """,
            (since,),
        ).fetchall()
    finally:
        conn.close()
    return {
        "ok": True,
        "range_seconds": range_seconds,
        "bank": [dict(row) for row in bank_rows],
        "packs": [dict(row) for row in pack_rows],
        "warnings": [dict(row) for row in warning_rows],
        "system": [dict(row) for row in system_rows],
    }
