import logging
from datetime import datetime

import numpy as np

from pyjamaz import settings
from pyjamaz.hashing import blake2b_256_hash
from pyjamaz.pvm import PVMInterpreter
from pyjamaz.pvm.constants import OpcodeNames
from pyjamaz.pvm.invocation import PVMLogger


import math
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


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

    # Backfill schema for older databases lacking total_time column
    info = conn.execute("PRAGMA table_info(opcode_timing_samples)").fetchall()
    has_total_time = any(row[1] == 'total_time' for row in info)
    if not has_total_time:
        conn.execute("ALTER TABLE opcode_timing_samples ADD COLUMN total_time REAL NOT NULL DEFAULT 0.0")


def _record_opcode_timing_summary(
        source: str,
        total_iterations,
        opcode_counts,
        opcode_time_total,
        opcode_time_min,
        opcode_time_max) -> int:
    total_iters = int(total_iterations[0]) if len(total_iterations) > 0 else 0
    total_time = float(np.sum(opcode_time_total))
    avg_time_per_instr = total_time / float(total_iters) if total_iters > 0 else 0.0

    rows = []
    for idx in range(len(opcode_counts)):
        count = int(opcode_counts[idx])
        if count <= 0:
            continue

        name = OpcodeNames.get(idx, f"opcode_{idx}")

        total_op_time = float(opcode_time_total[idx])
        avg_time = (total_op_time / float(total_iters)) if total_iters > 0 else 0.0
        mean_time = total_op_time / float(count)
        min_time = float(opcode_time_min[idx])
        if math.isinf(min_time) or math.isnan(min_time):
            min_time = 0.0
        max_time = float(opcode_time_max[idx])

        rows.append((
            idx,
            name,
            count,
            total_op_time,
            float(avg_time),
            float(mean_time),
            float(min_time),
            float(max_time),
        ))

    # Sort rows by hottest opcodes first (mean desc, then max desc, then opcode asc)
    rows.sort(key=lambda item: (-item[5], -item[7], item[0]))

    timestamp = datetime.utcnow().isoformat(timespec='microseconds')
    source_label = source if source else 'unknown'

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
                (timestamp, source_label, total_iters, float(total_time), float(avg_time_per_instr))
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
                            run_id,
                            int(opcode),
                            str(name),
                            int(count),
                            float(total_time),
                            float(avg_time),
                            float(mean_time),
                            float(min_time),
                            float(max_time)
                        )
                        for opcode, name, count, total_time, avg_time, mean_time, min_time, max_time in rows
                    ]
                )
            conn.commit()
            return int(run_id)
    except sqlite3.Error as exc:
        print(f"[opcode_timing] failed to record stats: {exc}", file=sys.stderr)

    return -1


@njit(cache=NUMBA_CACHE)
def _finalize_iteration(
        timing_enabled,
        start_time,
        opcode_index,
        opcode_counts,
        opcode_time_total,
        opcode_time_min,
        opcode_time_max,
        total_iterations):
    if opcode_index < 0:
        return

    opcode_counts[opcode_index] += 1

    if timing_enabled and start_time > 0.0:
        with objmode(tend='float64'):
            tend = _pytime.perf_counter()
        elapsed = tend - start_time
        opcode_time_total[opcode_index] += elapsed
        if elapsed < opcode_time_min[opcode_index]:
            opcode_time_min[opcode_index] = elapsed
        if elapsed > opcode_time_max[opcode_index]:
            opcode_time_max[opcode_index] = elapsed

    total_iterations[0] += 1


@njit(cache=NUMBA_CACHE)
def _store_opcode_stats(
        opcode_counts,
        opcode_time_total,
        opcode_time_min,
        opcode_time_max,
        opcode_counts_out,
        opcode_time_total_out,
        opcode_time_min_out,
        opcode_time_max_out):
    for idx in range(len(opcode_counts_out)):
        opcode_counts_out[idx] = opcode_counts[idx]
    for idx in range(len(opcode_time_total_out)):
        opcode_time_total_out[idx] = opcode_time_total[idx]
        opcode_time_min_out[idx] = opcode_time_min[idx]
        opcode_time_max_out[idx] = opcode_time_max[idx]


@njit(uint32(
    uint64[::1],  # reg
    uint64[::1],  # registers_out
    int64[::1],   # state_out
    int64,        # status
    int64,        # pc
    int64,        # gas
    int64,        # inst_nr
    int64,        # exit_value
    uint32,       # skip_len
    uint32,       # error_code
    boolean,      # timing_enabled
    float64,      # start_time
    int64,        # opcode_index
    int64[::1],   # opcode_counts
    float64[::1], # opcode_time_total
    float64[::1], # opcode_time_min
    float64[::1], # opcode_time_max
    int64[::1],   # total_iterations
    int64[::1],   # opcode_counts_out
    float64[::1], # opcode_time_total_out
    float64[::1], # opcode_time_min_out
    float64[::1], # opcode_time_max_out
    int64[::1]    # total_iterations_out
), cache=NUMBA_CACHE)
def return_with_stats(
        reg,
        registers_out,
        state_out,
        status,
        pc,
        gas,
        inst_nr,
        exit_value,
        skip_len,
        error_code,
        timing_enabled,
        start_time,
        opcode_index,
        opcode_counts,
        opcode_time_total,
        opcode_time_min,
        opcode_time_max,
        total_iterations,
        opcode_counts_out,
        opcode_time_total_out,
        opcode_time_min_out,
        opcode_time_max_out,
        total_iterations_out):

    _finalize_iteration(
        timing_enabled,
        start_time,
        opcode_index,
        opcode_counts,
        opcode_time_total,
        opcode_time_min,
        opcode_time_max,
        total_iterations
    )
    _store_opcode_stats(
        opcode_counts,
        opcode_time_total,
        opcode_time_min,
        opcode_time_max,
        opcode_counts_out,
        opcode_time_total_out,
        opcode_time_min_out,
        opcode_time_max_out
    )
    total_iterations_out[0] = total_iterations[0]

    return sync_state_and_return(
        reg,
        registers_out,
        state_out,
        status,
        pc,
        gas,
        inst_nr,
        exit_value,
        skip_len,
        error_code
    )



class PVMOpcodeLogger(PVMLogger):

    def __init__(self, pvm, log_opcode_calls=True, log_opcode_calls_if_zero=False):
        np.seterr(over='ignore')
        self._pvm = pvm
        self._pvm_id = self._pvm.name
        self._initial_gas = pvm.gas  # TODO: sla op in logger!
        self._initial_pc = pvm.pc
        self.log_opcodes = {}
        self.log_opcode_calls = log_opcode_calls
        self.log_opcode_calls_if_zero = log_opcode_calls_if_zero

    def dump_code(self):
        with open(f"code-spi-{datetime.now().strftime('%H:%M:%S')}.bin", "wb") as binary_file:
            data=self._pvm.program.to_serialized_bytes()
            binary_file.write(data) #program_bytes)

    def dump_test_vector(self):
        import json

        initial_page_map = []
        initial_memory = []

        mem_segments = [
            self._pvm.program.memory._rom,
            self._pvm.program.memory._heap,
            self._pvm.program.memory._stack,
            self._pvm.program.memory._args
        ]

        for mem in mem_segments:
            if mem and mem.size > 0:
                initial_page_map.append({
                    "address": int(mem.address),
                    "length": int(mem.size),
                    "is-writable": mem.writable,
                })

                #end_idx = 0
                for idx, value in enumerate(mem.contents):
                    #if value > 0:
                    initial_memory.append({
                        "address": mem.address+idx,
                        "contents": [int(value)]
                    })
                #     if value != 0:
                #         end_idx = idx
                # if end_idx != 0:
                #     initial_memory.append({
                #         "address": int(mem.address),
                #         "contents": [int(x) for x in mem.contents[:end_idx]]
                #     })

        with open(f"code-testvector-{datetime.now().strftime('%H-%M-%S')}.json", 'w') as fp:
            tt = {
                "name": "gas_basic_consume_all",
                "initial-regs": self._pvm.program.registers,
                "initial-pc": int(self._pvm._initial_pc),
                "initial-page-map": initial_page_map,
                "initial-memory": initial_memory,
                "initial-gas": int(self._pvm._initial_gas),
                "program": [x for x in self._pvm.program.to_serialized_bytes()],
                "expected-status": "panic",
                "expected-regs": [
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0
                ],
                "expected-pc": 1,#TODO
                "expected-memory": [],#TODO
                "expected-gas": 0#TODO
            }
            json.dump(tt, fp)


    def hc_regs(self, msg: str, phase: str) -> None:
        #TODO: set phase from pvm invoke, hardcoded accumulate for now
        msg = f"{self._pvm_id}_{phase}: {msg}"
        regs = self._pvm.get_registers()
        reg_msg = f"reg={str(regs)}"
        logging.debug(
            f"{msg}\n{reg_msg}"
        )

    def hc_debug(self, log_lvl: int, log_lvl_name: str, core_idx: int, service_id: int, target_msg: str, message: str) -> None:
        logging.log(log_lvl, f"{log_lvl_name}@{core_idx}#{service_id} {target_msg} {message}")

    def pvm_hash(self):
        bytez = bytes()
        for x in range(len(self._pvm.reg)):
            bytez += int(self._pvm.reg[x]).to_bytes(length=8, byteorder="little")

        bytez += int(self._pvm.gas).to_bytes(length=8, byteorder="little")

        rom = self._pvm.mem._rom
        heap = self._pvm.mem._heap
        stack = self._pvm.mem._stack
        arguments = self._pvm.mem._args
        mem_segments = [m for m in (rom, heap, stack, arguments) if m]
        for seg in mem_segments:
            if seg.tail > 0:
                page_begin_addr = seg.address
                page_end_addr = seg.paged_tail
                nr_pages = (page_end_addr-page_begin_addr) // 4096 + 1
                for xx in range(nr_pages):
                    bytez += int(seg.address // 4096).to_bytes(length=4, byteorder="little")
                    offset = xx*4096
                    bytez += bytes(seg.contents[offset:offset+4096])

        return blake2b_256_hash(bytez)

    def pvm_counters(self):
        logging.debug(f"GAS: {self._pvm.gas} PC: {self._pvm.pc}")

    def pvm_header(self):
        pass

    def pvm_regs(self, msg):
        regs = self._pvm.get_registers()
        reg_msg = f"reg={str(regs)}"
        logging.debug(f"{msg} {reg_msg}")

    def sbrk(self, cur_size, new_size, growth, alloc_mem):
        print(f"SBRK GROWN FROM {cur_size} TO {new_size} (growth {growth}, alloc mem: {alloc_mem})")

    def acl(self, cur_size, new_size, growth):
        print(f"ACL GROWN FROM {cur_size} TO {new_size} (growth: {growth})")

    def exc(self, exc_str):
        print(f"PVM EXCEPTION:\n{exc_str}")

    def __call__(self, reg1=None, reg2=None, reg3=None, imm1=None, imm2=None, off1=None, off2=None, context=None):
        if not settings.PVM_DEBUG_OPCODES:
            return

        mem_info = ""
        if settings.PVM_DEBUG_MEMORY:
            if hasattr(self._pvm, "mem_sections"):
                mem = self._pvm.mem_sections
                if mem is not None and len(mem) >= 2 and mem[1] is not None:
                    heap_hash = hash_memory_segment(mem[1])
                    mem_info += f"heap_hash:{heap_hash}"
                if mem is not None and len(mem) >= 3 and mem[2] is not None:
                    stack_hash = hash_memory_segment(mem[2])
                    mem_info += f" stack_hash:{stack_hash}"
            elif hasattr(self._pvm, "mem"):
                mem = [x for x in [self._pvm.mem._rom, self._pvm.mem._heap, self._pvm.mem._stack, self._pvm.mem._args] if x]
                if mem is not None and len(mem) >= 2:
                    heap_hash = hash_memory_segment(mem[1].contents)
                    mem_info += f"heap_hash:{heap_hash}"
                if mem is not None and len(mem) >= 3:
                    stack_hash = hash_memory_segment(mem[2].contents)
                    mem_info += f" stack_hash:{stack_hash}"

        name_str = OpcodeNames[self._pvm.opcode]
        name_pad = 22 - len(name_str)
        if name_pad > 0:
            name_str = name_str + (" " * name_pad)

        regs = [int(x) for x in self._pvm.get_registers()]
        regs_str = ""
        for i in range(len(regs)):
            s = str(regs[i])
            pad = 21 - len(s)
            if pad > 0:
                regs_str += (" " * pad) + s
            else:
                regs_str += s
            if i != len(regs) - 1:
                regs_str += " "

        # Fixed width for inst_nr and pc (4 chars each, right-aligned)
        inst_str = str(self._pvm.inst_nr)
        if len(inst_str) < 4:
            inst_str = (" " * (4 - len(inst_str))) + inst_str

        pc_str = str(self._pvm.pc)
        if len(pc_str) < 4:
            pc_str = (" " * (4 - len(pc_str))) + pc_str

        tt = " ".join([str(inst_str), pc_str, name_str, str(self._pvm.gas), regs_str, mem_info])
        logging.info(tt)


    def hc_log(self, msg, data):
        msg = f"{self._pvm_id}: {msg}"
        spacing = " " * (51 - len(str(msg)))
        logging.debug(
            f"{msg}"
            f"{spacing}"
            f"{data}"
        )
