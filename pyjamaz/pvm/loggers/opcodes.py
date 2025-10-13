import logging
import math
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Optional

from pyjamaz import settings
from pyjamaz.pvm.constants import OpcodeNames
from pyjamaz.pvm.loggers.debug_logger import PVMDebugLog


STATS_DB_FILENAME = "opcode_timing_stats.sqlite3"


def _get_stats_db_path() -> Path:
    return Path.cwd() / STATS_DB_FILENAME


def _ensure_opcode_stats_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS opcode_timing_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            source TEXT NOT NULL,
            total_iterations INTEGER NOT NULL,
            total_time REAL NOT NULL,
            avg_time_per_instr REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS opcode_timing_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            opcode INTEGER NOT NULL,
            opcode_name TEXT NOT NULL,
            count INTEGER NOT NULL,
            total_time REAL NOT NULL,
            avg_time REAL NOT NULL,
            mean_time REAL NOT NULL,
            min_time REAL NOT NULL,
            max_time REAL NOT NULL,
            FOREIGN KEY(run_id) REFERENCES opcode_timing_runs(id) ON DELETE CASCADE
        )
        """
    )

    info = conn.execute("PRAGMA table_info(opcode_timing_samples)").fetchall()
    has_total_time = any(row[1] == "total_time" for row in info)
    if not has_total_time:
        conn.execute(
            "ALTER TABLE opcode_timing_samples ADD COLUMN total_time REAL NOT NULL DEFAULT 0.0"
        )


class _OpcodeTimingAccumulator:
    __slots__ = (
        "size",
        "counts",
        "total_times",
        "min_times",
        "max_times",
        "total_instructions",
        "total_time",
        "dirty",
    )

    def __init__(self, size: int) -> None:
        self.size = size
        self.reset()

    def reset(self) -> None:
        self.counts = [0] * self.size
        self.total_times = [0.0] * self.size
        self.min_times = [math.inf] * self.size
        self.max_times = [0.0] * self.size
        self.total_instructions = 0
        self.total_time = 0.0
        self.dirty = False

    def record(self, opcode: int, elapsed: float) -> None:
        if opcode < 0 or opcode >= self.size:
            return
        if not math.isfinite(elapsed) or elapsed < 0.0:
            return
        self.counts[opcode] += 1
        self.total_times[opcode] += elapsed
        self.total_instructions += 1
        self.total_time += elapsed
        if elapsed < self.min_times[opcode]:
            self.min_times[opcode] = elapsed
        if elapsed > self.max_times[opcode]:
            self.max_times[opcode] = elapsed
        self.dirty = True

    def has_data(self) -> bool:
        return self.dirty and self.total_instructions > 0

    def iter_samples(self):
        for opcode in range(self.size):
            count = self.counts[opcode]
            if count == 0:
                continue
            total_time = self.total_times[opcode]
            mean_time = total_time / count
            min_time = self.min_times[opcode]
            if math.isinf(min_time):
                min_time = 0.0
            max_time = self.max_times[opcode]
            yield opcode, count, total_time, mean_time, min_time, max_time


def _record_opcode_timing_summary(source: str, stats: _OpcodeTimingAccumulator) -> int:
    if not stats.has_data():
        return -1

    total_iters = stats.total_instructions
    total_time = stats.total_time
    avg_time_per_instr = total_time / total_iters if total_iters else 0.0

    rows = []
    for opcode, count, total_op_time, mean_time, min_time, max_time in stats.iter_samples():
        avg_time = total_op_time / total_iters if total_iters else 0.0
        name = OpcodeNames.get(opcode, f"opcode_{opcode}")
        rows.append(
            (
                opcode,
                name,
                count,
                float(total_op_time),
                float(avg_time),
                float(mean_time),
                float(min_time),
                float(max_time),
            )
        )

    rows.sort(key=lambda item: (-item[5], -item[7], item[0]))
    timestamp = datetime.utcnow().isoformat(timespec="microseconds")
    source_label = source if source else "unknown"

    try:
        db_path = _get_stats_db_path().resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            _ensure_opcode_stats_schema(conn)
            cursor = conn.execute(
                """
                INSERT INTO opcode_timing_runs (created_at, source, total_iterations, total_time, avg_time_per_instr)
                VALUES (?, ?, ?, ?, ?)
                """,
                (timestamp, source_label, int(total_iters), float(total_time), float(avg_time_per_instr)),
            )
            run_id = cursor.lastrowid

            if rows:
                conn.executemany(
                    """
                    INSERT INTO opcode_timing_samples
                        (run_id, opcode, opcode_name, count, total_time, avg_time, mean_time, min_time, max_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            int(run_id),
                            int(opcode),
                            str(name),
                            int(count),
                            float(total_time),
                            float(avg_time),
                            float(mean_time),
                            float(min_time),
                            float(max_time),
                        )
                        for opcode, name, count, total_time, avg_time, mean_time, min_time, max_time in rows
                    ],
                )
            conn.commit()
            return int(run_id)
    except sqlite3.Error as exc:
        print(f"[opcode_timing] failed to record stats: {exc}", file=sys.stderr)

    return -1


class PVMOpcodeLogger(PVMDebugLog):
    def __init__(self, pvm, log_opcode_calls: bool = True, log_opcode_calls_if_zero: bool = False):
        super().__init__(pvm, log_opcode_calls=log_opcode_calls, log_opcode_calls_if_zero=log_opcode_calls_if_zero)
        opcode_space = max(256, max(OpcodeNames.keys(), default=0) + 1)
        self._stats = _OpcodeTimingAccumulator(opcode_space)
        self._current_opcode: Optional[int] = None
        self._current_start: Optional[float] = None
        module_name = type(pvm).__module__
        self._collect_stats = (
            settings.PVM_DEBUG_OPCODES
            and module_name.startswith("pyjamaz.pvm.interpreters.graypaper")
        )
        self._source_label = f"{type(pvm).__name__}:{pvm.name}"

    def before_opcode(self, opcode: int) -> None:
        if not self._collect_stats:
            return
        if self._current_opcode is not None:
            self._finalize_current_opcode()
        self._current_opcode = int(opcode)
        self._current_start = perf_counter()

    def _finalize_current_opcode(self) -> Optional[int]:
        opcode = self._current_opcode
        start = self._current_start
        self._current_opcode = None
        self._current_start = None
        if opcode is None:
            return None
        if self._collect_stats and start is not None:
            elapsed = perf_counter() - start
            if elapsed < 0.0:
                elapsed = 0.0
            self._stats.record(opcode, elapsed)
        return opcode

    def __call__(self, *args, **kwargs):
        opcode = self._finalize_current_opcode()
        if opcode is None:
            opcode = int(self._pvm.opcode)
        name = OpcodeNames.get(opcode, f"opcode_{opcode}")
        self.log_opcodes[name] = self.log_opcodes.get(name, 0) + 1
        return super().__call__(*args, **kwargs)

    def exc(self, exc_str):
        opcode = self._finalize_current_opcode()
        if opcode is None:
            opcode = int(self._pvm.opcode)
        name = OpcodeNames.get(opcode, f"opcode_{opcode}")
        self.log_opcodes[name] = self.log_opcodes.get(name, 0) + 1
        return super().exc(exc_str)

    def finalize_opcode_stats(self) -> Optional[int]:
        if not self._collect_stats:
            return None
        self._finalize_current_opcode()
        if not self._stats.has_data():
            return None
        run_id = _record_opcode_timing_summary(self._source_label, self._stats)
        if run_id >= 0:
            logging.getLogger(__name__).info(
                "Recorded opcode timing stats for %s (run_id=%s)",
                self._source_label,
                run_id,
            )
            self._stats.reset()
        return run_id

    def reset_opcode_stats(self) -> None:
        self._stats.reset()
        self._current_opcode = None
        self._current_start = None
