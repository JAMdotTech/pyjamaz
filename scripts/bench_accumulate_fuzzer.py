#!/usr/bin/env python3
"""Benchmark accumulation through the fuzzer trace target.

The benchmark is valid only when every configured trace batch exits cleanly and
all processed traces match their expected post-state roots. Target-reported
validation errors are recorded separately because some corpora intentionally
exercise rejected blocks whose expected post-state is the pre-state.
"""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import median


DEFAULT_BATCHES = ("fallback", "safrole", "storage", "fuzzy", "preimages")
SESSION_TIME_RE = re.compile(r"Fuzzer session finished in ([0-9.]+) seconds")


@dataclass(frozen=True)
class BatchResult:
    name: str
    traces: int
    cli_seconds: float | None
    wall_seconds: float
    exit_code: int
    successes: int
    mismatches: int
    target_errors: int
    tracebacks: int
    aborted: int
    diagnostics: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return (
            self.exit_code == 0
            and self.cli_seconds is not None
            and self.successes == self.traces
            and self.mismatches == 0
            and self.tracebacks == 0
            and self.aborted == 0
        )


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def python_executable(root: Path) -> Path:
    venv_python = root / ".venv" / "bin" / "python"
    if venv_python.exists():
        return venv_python
    return Path(sys.executable)


def count_trace_files(batch_dir: Path) -> int:
    return sum(
        1
        for path in batch_dir.rglob("*.bin")
        if path.name not in {"genesis.bin", "report.bin"}
    )


def run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> tuple[int, str, float]:
    start = time.perf_counter()
    process = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return process.returncode, process.stdout, time.perf_counter() - start


def wait_for_target(socket_path: Path, process: subprocess.Popen[str], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"target exited before socket was ready\n{output}")
        if socket_path.exists():
            return
        time.sleep(0.05)
    raise TimeoutError(f"target did not create {socket_path} within {timeout:.1f}s")


def start_target(
    python: Path,
    root: Path,
    socket_path: Path,
    env: dict[str, str],
    startup_timeout: float,
) -> subprocess.Popen[str]:
    if socket_path.exists():
        socket_path.unlink()

    process = subprocess.Popen(
        [
            str(python),
            "-m",
            "pyjamaz.cli",
            "fuzzer",
            "target",
            "--socket-path",
            str(socket_path),
        ],
        cwd=str(root),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )
    try:
        wait_for_target(socket_path, process, startup_timeout)
    except Exception:
        stop_target(process)
        raise
    return process


def stop_target(process: subprocess.Popen[str], timeout: float = 5.0) -> str:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGINT)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=timeout)
    return ""


def parse_batch_result(name: str, traces: int, exit_code: int, output: str, wall_seconds: float) -> BatchResult:
    session_match = SESSION_TIME_RE.search(output)
    cli_seconds = float(session_match.group(1)) if session_match else None
    lower_output = output.lower()
    diagnostic_lines = [
        line
        for line in output.splitlines()
        if (
            "state root mismatch" in line.lower()
            or "Traceback" in line
            or "Aborted!" in line
            or "Error:" in line
            or "Exception" in line
            or "Connection" in line
        )
    ]
    if exit_code != 0 and not diagnostic_lines:
        diagnostic_lines = output.splitlines()[-20:]

    return BatchResult(
        name=name,
        traces=traces,
        cli_seconds=cli_seconds,
        wall_seconds=wall_seconds,
        exit_code=exit_code,
        successes=output.count("successfully: State root matches"),
        mismatches=lower_output.count("state root mismatch"),
        target_errors=output.count("Target reported error"),
        tracebacks=output.count("Traceback"),
        aborted=output.count("Aborted!"),
        diagnostics=tuple(diagnostic_lines[:40]),
    )


def run_batch(
    python: Path,
    root: Path,
    traces_root: Path,
    socket_path: Path,
    env: dict[str, str],
    batch: str,
) -> BatchResult:
    batch_dir = traces_root / batch
    traces = count_trace_files(batch_dir)
    exit_code, output, wall_seconds = run_command(
        [
            str(python),
            "-m",
            "pyjamaz.cli",
            "fuzzer",
            "traces",
            str(batch_dir),
            "--socket-path",
            str(socket_path),
        ],
        cwd=root,
        env=env,
    )
    return parse_batch_result(batch, traces, exit_code, output, wall_seconds)


def print_matrix_header() -> None:
    print(
        "| batch | traces | cli_seconds | wall_seconds | exit | successes | mismatches | target_errors | valid |",
        flush=True,
    )
    print("|---|---:|---:|---:|---:|---:|---:|---:|---|", flush=True)


def print_matrix_row(result: BatchResult) -> None:
    cli_seconds = "" if result.cli_seconds is None else f"{result.cli_seconds:.6f}"
    print(
        f"| {result.name} | {result.traces} | {cli_seconds} | "
        f"{result.wall_seconds:.3f} | {result.exit_code} | {result.successes} | "
        f"{result.mismatches} | {result.target_errors} | {result.valid} |",
        flush=True,
    )
    if not result.valid and result.diagnostics:
        print(f"\nDiagnostics for {result.name}:", flush=True)
        for line in result.diagnostics:
            print(line, flush=True)
        print(flush=True)


def print_matrix(results: list[BatchResult]) -> None:
    print_matrix_header()
    for result in results:
        print_matrix_row(result)


def run_once(args: argparse.Namespace, python: Path, root: Path, env: dict[str, str]) -> list[BatchResult]:
    target = None
    socket_path = Path(args.socket_path)
    try:
        target = start_target(python, root, socket_path, env, args.startup_timeout)
        results = []
        print_matrix_header()
        for batch in args.batches:
            result = run_batch(python, root, args.traces_root, socket_path, env, batch)
            results.append(result)
            print_matrix_row(result)
        return results
    finally:
        if target is not None:
            stop_target(target)
        if socket_path.exists():
            socket_path.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--traces-root",
        type=Path,
        default=Path("/Users/arjan/Development/jam-test-vectors/traces"),
        help="Directory containing trace batch subdirectories.",
    )
    parser.add_argument("--socket-path", default="/tmp/jam_target.sock")
    parser.add_argument("--startup-timeout", type=float, default=30.0)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--batches", nargs="+", default=list(DEFAULT_BATCHES))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = repo_root()
    python = python_executable(root)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)

    totals: list[float] = []
    all_valid = True
    for repeat_index in range(args.repeat):
        if args.repeat > 1:
            print(f"\nrepeat {repeat_index + 1}/{args.repeat}")
        results = run_once(args, python, root, env)

        valid = all(result.valid for result in results)
        all_valid = all_valid and valid
        if valid:
            total = sum(result.cli_seconds or 0.0 for result in results)
            totals.append(total)
            print(f"total_cli_seconds={total:.6f}")
        else:
            print("total_cli_seconds=invalid")

    if totals:
        print(f"median_total_cli_seconds={median(totals):.6f}")

    return 0 if all_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
