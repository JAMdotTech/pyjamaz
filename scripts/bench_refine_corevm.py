#!/usr/bin/env python3
import argparse
import json
import os
import signal
import socket
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from datetime import datetime
import re


SEED = "0x" + ("00" * 32)
DEFAULT_BUILDER = "/Users/arjan/Development/jam-testnet/polkajam/v0.7.2-0.1.27/macos_aarch64/corevm-builder"
DEFAULT_SERVICE = "c36351c2"
LOG_TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
REPORT_RE = re.compile(r"Created work-report 0x([0-9a-fA-F.]+)")


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    idx = (len(ordered) - 1) * pct
    low = int(idx)
    high = min(low + 1, len(ordered) - 1)
    frac = idx - low
    return ordered[low] * (1 - frac) + ordered[high] * frac


def wait_for_tcp(host: str, port: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.2)
    raise TimeoutError(f"RPC server did not accept TCP connections on {host}:{port}: {last_error}")


def terminate(proc: subprocess.Popen[Any]) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGINT)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=10)


def run_command(cmd: list[str], cwd: Path, env: dict[str, str], log_path: Path, timeout: float | None = None) -> float:
    start = time.perf_counter()
    with log_path.open("w", encoding="utf-8") as log:
        subprocess.run(cmd, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout, check=True)
    return time.perf_counter() - start


def parse_node_log_refines(node_log_path: Path) -> list[dict[str, Any]]:
    if not node_log_path.exists():
        return []
    rows = []
    started_at: datetime | None = None
    for raw_line in node_log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = ANSI_RE.sub("", raw_line)
        ts_match = LOG_TS_RE.search(line)
        if ts_match is None:
            continue
        timestamp = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S.%f")
        if "Processing work-package" in line:
            started_at = timestamp
        elif started_at is not None and "Created work-report" in line:
            report_match = REPORT_RE.search(line)
            rows.append(
                {
                    "kind": "refine-log",
                    "wall_seconds": (timestamp - started_at).total_seconds(),
                    "report_hash": report_match.group(1) if report_match else None,
                }
            )
            started_at = None
    return rows


def count_profile_rows(profile_path: Path) -> int:
    if not profile_path.exists():
        return 0
    with profile_path.open("r", encoding="utf-8") as fp:
        return sum(1 for line in fp if line.strip())


def count_completed_refines(profile_path: Path, node_log_path: Path) -> int:
    profile_rows = count_profile_rows(profile_path)
    if profile_rows:
        return profile_rows
    return len(parse_node_log_refines(node_log_path))


def run_builder_command(
    cmd: list[str],
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
    profile_path: Path,
    node_log_path: Path,
    timeout: float | None,
    max_refines: int | None,
) -> tuple[float, bool]:
    start = time.perf_counter()
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + timeout if timeout is not None else None
            while True:
                ret = proc.poll()
                if ret is not None:
                    if ret != 0:
                        raise subprocess.CalledProcessError(ret, cmd)
                    return time.perf_counter() - start, False

                if max_refines is not None and count_completed_refines(profile_path, node_log_path) >= max_refines:
                    terminate(proc)
                    return time.perf_counter() - start, True

                if deadline is not None and time.monotonic() > deadline:
                    terminate(proc)
                    raise subprocess.TimeoutExpired(cmd, timeout)

                time.sleep(0.5)
        finally:
            terminate(proc)


def read_profiles(profile_path: Path) -> list[dict[str, Any]]:
    if not profile_path.exists():
        return []
    rows = []
    with profile_path.open("r", encoding="utf-8") as fp:
        for line in fp:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("kind") == "refine":
                rows.append(row)
    return rows


def summarize_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    wall = [float(row.get("wall_seconds", 0.0)) for row in rows]
    has_profile_metrics = any(row.get("kind") == "refine" for row in rows)
    pvm_setup = [float(row.get("timers", {}).get("pvm_setup", 0.0)) for row in rows]
    hostcall_total = []
    storage_reads = []
    report_hashes = set()
    export_roots = set()

    for row in rows:
        hostcall_total.append(sum(float(v.get("seconds", 0.0)) for v in row.get("hostcalls", {}).values()))
        counts = row.get("counts", {})
        storage_reads.append(
            int(counts.get("retrieve_service_account", 0)) +
            int(counts.get("retrieve_preimage", 0)) +
            int(counts.get("retrieve_preimage_availability", 0)) +
            int(counts.get("historical_preimage_lookup", 0))
        )
        if row.get("report_hash"):
            report_hashes.add(row["report_hash"])
        if row.get("exports_root"):
            export_roots.add(row["exports_root"])

    return {
        "refines": len(rows),
        "median_wall": statistics.median(wall) if wall else None,
        "p95_wall": percentile(wall, 0.95),
        "pvm_setup": sum(pvm_setup) if has_profile_metrics else None,
        "hostcall_total": sum(hostcall_total) if has_profile_metrics else None,
        "storage_reads": sum(storage_reads) if has_profile_metrics else None,
        "report_hashes": sorted(report_hashes),
        "export_roots": sorted(export_roots),
    }


def append_ledger(path: Path, stage: str, change: str, summary: dict[str, Any], speedup: float | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "| Stage | Change | Median wall | p95 wall | PVM setup | hostcall total | storage reads | report/root match | Speedup |\n"
            "|---|---|---:|---:|---:|---:|---:|---|---:|\n",
            encoding="utf-8",
        )

    hashes = summary.get("report_hashes") or []
    roots = summary.get("export_roots") or []
    match = "yes" if len(hashes) <= 1 and len(roots) <= 1 else "no"
    values = [
        stage,
        change,
        f"{summary.get('median_wall'):.6f}" if summary.get("median_wall") is not None else "TBD",
        f"{summary.get('p95_wall'):.6f}" if summary.get("p95_wall") is not None else "TBD",
        f"{summary.get('pvm_setup'):.6f}" if summary.get("pvm_setup") is not None else "TBD",
        f"{summary.get('hostcall_total'):.6f}" if summary.get("hostcall_total") is not None else "TBD",
        str(summary.get("storage_reads", "TBD")),
        match,
        f"{speedup:.2f}x" if speedup else "TBD",
    ]
    with path.open("a", encoding="utf-8") as fp:
        fp.write("| " + " | ".join(values) + " |\n")
    jsonl_row = {
        "stage": stage,
        "change": change,
        "speedup": speedup,
        "summary": summary,
    }
    with path.with_suffix(".jsonl").open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(jsonl_row, sort_keys=True) + "\n")


def run_one(args: argparse.Namespace, repo: Path, out_dir: Path, run_index: int, measured: bool) -> dict[str, Any]:
    run_dir = out_dir / f"{'run' if measured else 'warmup'}-{run_index:02d}"
    run_dir.mkdir(parents=True, exist_ok=True)
    db_path = run_dir / "db"
    profile_path = run_dir / "refine-profile.jsonl"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo)
    rpc_url = f"ws://{args.rpc_host}:{args.rpc_port}"
    env["JAM_RPC"] = rpc_url
    if args.profile:
        env["PYJAMAZ_REFINE_PROFILE"] = str(profile_path)

    init_cmd = [
        args.python,
        str(repo / "pyjamaz" / "cli.py"),
        "init",
        "--seed",
        args.seed,
        "--force-overwrite",
        "--db-path",
        str(db_path),
        "--import-trace",
        str(args.trace),
    ]
    run_cmd = [
        args.python,
        str(repo / "pyjamaz" / "cli.py"),
        "run",
        "--seed",
        args.seed,
        "--host",
        args.host,
        "--port",
        str(args.node_port),
        "--rpc-listen-ip",
        args.rpc_host,
        "--rpc-port",
        str(args.rpc_port),
        "--db-path",
        str(db_path),
    ]
    builder_cmd = [args.builder, "--rpc", rpc_url, args.service]

    init_seconds = run_command(init_cmd, repo, env, run_dir / "init.log", timeout=args.init_timeout)
    node_log_path = run_dir / "node.log"
    with node_log_path.open("w", encoding="utf-8") as node_log:
        node = subprocess.Popen(
            run_cmd,
            cwd=repo,
            env=env,
            stdout=node_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    try:
        wait_for_tcp(args.rpc_host, args.rpc_port, args.startup_timeout)
        builder_seconds, builder_capped = run_builder_command(
            builder_cmd,
            repo,
            env,
            run_dir / "builder.log",
            profile_path,
            node_log_path,
            timeout=args.builder_timeout,
            max_refines=args.max_refines_per_run,
        )
    finally:
        terminate(node)

    profile_rows = read_profiles(profile_path)
    if not profile_rows:
        profile_rows = parse_node_log_refines(node_log_path)
    summary = summarize_profile(profile_rows)
    summary.update(
        {
            "run_index": run_index,
            "measured": measured,
            "init_seconds": init_seconds,
            "builder_seconds": builder_seconds,
            "builder_capped": builder_capped,
            "profile_path": str(profile_path),
            "db_path": str(db_path),
        }
    )
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> None:
    script_repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Benchmark Python refine with the DOOM corevm builder workload.")
    parser.add_argument("--repo", type=Path, default=script_repo)
    parser.add_argument("--trace", type=Path, default=script_repo / "rustyjamaz" / "data" / "traces" / "doom-clean.bin")
    parser.add_argument("--builder", default=DEFAULT_BUILDER)
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    parser.add_argument("--seed", default=SEED)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--out-dir", type=Path, default=script_repo / "artifacts" / "refine-bench")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--no-profile", dest="profile", action="store_false")
    parser.set_defaults(profile=True)
    parser.add_argument("--stage", default="baseline")
    parser.add_argument("--change", default="current Python/settings")
    parser.add_argument("--baseline-median", type=float, default=None)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--node-port", type=int, default=9000)
    parser.add_argument("--rpc-host", default="127.0.0.1")
    parser.add_argument("--rpc-port", type=int, default=19800)
    parser.add_argument("--startup-timeout", type=float, default=60.0)
    parser.add_argument("--init-timeout", type=float, default=120.0)
    parser.add_argument("--builder-timeout", type=float, default=900.0)
    parser.add_argument("--max-refines-per-run", type=int, default=None)
    args = parser.parse_args()

    repo = args.repo.resolve()
    args.trace = args.trace.resolve()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "python": args.python,
        "builder": args.builder,
        "service": args.service,
        "trace": str(args.trace),
        "seed": args.seed,
        "stage": args.stage,
        "change": args.change,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (args.out_dir / f"{args.stage}-metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    for idx in range(args.warmups):
        run_one(args, repo, args.out_dir, idx + 1, measured=False)

    summaries = [run_one(args, repo, args.out_dir, idx + 1, measured=True) for idx in range(args.runs)]
    measured_wall = [s["median_wall"] for s in summaries if s.get("median_wall") is not None]
    stage_summary = {
        "runs": summaries,
        "median_wall": statistics.median(measured_wall) if measured_wall else None,
        "p95_wall": percentile(measured_wall, 0.95),
        "pvm_setup": sum(float(s.get("pvm_setup") or 0.0) for s in summaries),
        "hostcall_total": sum(float(s.get("hostcall_total") or 0.0) for s in summaries),
        "storage_reads": sum(int(s.get("storage_reads") or 0) for s in summaries),
        "report_hashes": sorted({h for s in summaries for h in s.get("report_hashes", [])}),
        "export_roots": sorted({h for s in summaries for h in s.get("export_roots", [])}),
    }
    speedup = None
    if args.baseline_median and stage_summary["median_wall"]:
        speedup = args.baseline_median / stage_summary["median_wall"]

    (args.out_dir / f"{args.stage}-summary.json").write_text(
        json.dumps(stage_summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    append_ledger(args.out_dir / "results.md", args.stage, args.change, stage_summary, speedup)
    print(json.dumps(stage_summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
