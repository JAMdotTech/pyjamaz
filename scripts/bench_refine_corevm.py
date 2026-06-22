#!/usr/bin/env python3
import argparse
import json
import os
import signal
import shutil
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
GUARANTEE_RE = re.compile(r"Added guarantee for work-report 0x([0-9a-fA-F.]+)")
PRODUCED_BLOCK_RE = re.compile(r"Produced block for #(\d+)")
ACCUMULATABLE_RE = re.compile(r"Accumulatable work-reports: (\d+)")
ACCUMULATED_RE = re.compile(r"Accumulated work-reports: (\d+) root=0x([0-9a-fA-F.]+)")
CYCLE_EVENT_RE = re.compile(
    r"cycle_event=(?P<kind>[a-z_]+)"
    r"(?: work_package=(?P<work_package>[0-9a-fA-F]+))?"
    r"(?: report=(?P<report>[0-9a-fA-F]+))?"
)


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


def parse_node_log_acceptance(node_log_path: Path) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    if node_log_path.exists():
        for raw_line in node_log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = ANSI_RE.sub("", raw_line)
            ts_match = LOG_TS_RE.search(line)
            if ts_match is None:
                continue
            timestamp = datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S.%f")

            report_match = REPORT_RE.search(line)
            if report_match:
                events.append({"kind": "report", "timestamp": timestamp, "report_hash": report_match.group(1)})

            guarantee_match = GUARANTEE_RE.search(line)
            if guarantee_match:
                events.append({"kind": "guarantee", "timestamp": timestamp, "report_hash": guarantee_match.group(1)})

            produced_match = PRODUCED_BLOCK_RE.search(line)
            if produced_match:
                events.append({"kind": "produced_block", "timestamp": timestamp, "slot": int(produced_match.group(1))})

            accumulatable_match = ACCUMULATABLE_RE.search(line)
            if accumulatable_match:
                events.append({"kind": "accumulatable", "timestamp": timestamp, "count": int(accumulatable_match.group(1))})

            accumulated_match = ACCUMULATED_RE.search(line)
            if accumulated_match:
                events.append(
                    {
                        "kind": "accumulated",
                        "timestamp": timestamp,
                        "count": int(accumulated_match.group(1)),
                        "root": accumulated_match.group(2),
                    }
                )

    def first_block_after(kind: str) -> int | None:
        marks = [event["timestamp"] for event in events if event["kind"] == kind]
        if not marks:
            return None
        mark = marks[0]
        for event in events:
            if event["kind"] == "produced_block" and event["timestamp"] >= mark:
                return event["slot"]
        return None

    accumulated = [event for event in events if event["kind"] == "accumulated" and event.get("count", 0) > 0]
    reports = [event for event in events if event["kind"] == "report"]
    guarantees = [event for event in events if event["kind"] == "guarantee"]
    accumulatable = [event for event in events if event["kind"] == "accumulatable" and event.get("count", 0) > 0]

    return {
        "report_hash": reports[-1]["report_hash"] if reports else None,
        "guaranteed": bool(guarantees),
        "guarantee_inclusion_block": first_block_after("guarantee"),
        "assurance_block": None,
        "accumulatable_block": first_block_after("accumulatable"),
        "accumulation_block": first_block_after("accumulated"),
        "accumulated": bool(accumulated),
        "accumulated_count": accumulated[-1]["count"] if accumulated else 0,
        "accumulate_root": accumulated[-1]["root"] if accumulated else None,
        "accumulatable_events": len(accumulatable),
    }


def parse_node_log_cycle_events(node_log_path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not node_log_path.exists():
        return events

    for raw_line in node_log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = ANSI_RE.sub("", raw_line)
        ts_match = LOG_TS_RE.search(line)
        event_match = CYCLE_EVENT_RE.search(line)
        if ts_match is None or event_match is None:
            continue
        events.append(
            {
                "kind": event_match.group("kind"),
                "timestamp": datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S.%f"),
                "work_package": event_match.group("work_package"),
                "report": event_match.group("report"),
            }
        )
    return events


def summarize_cycle_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    created_to_sent: list[float] = []
    submit_to_refine: list[float] = []
    reported_to_next_submit: list[float] = []

    by_package: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        work_package = event.get("work_package")
        if work_package:
            by_package.setdefault(work_package, []).append(event)

    for package_events in by_package.values():
        created = next((e for e in package_events if e["kind"] == "work_report_created"), None)
        sent = next((e for e in package_events if e["kind"] == "reported_status_sent"), None)
        received = next((e for e in package_events if e["kind"] == "work_package_received"), None)
        started = next((e for e in package_events if e["kind"] == "refine_started"), None)

        if created and sent:
            created_to_sent.append((sent["timestamp"] - created["timestamp"]).total_seconds())
        if received and started:
            submit_to_refine.append((started["timestamp"] - received["timestamp"]).total_seconds())

    ordered = sorted(events, key=lambda e: e["timestamp"])
    for idx, event in enumerate(ordered):
        if event["kind"] != "reported_status_sent":
            continue
        next_received = next((e for e in ordered[idx + 1:] if e["kind"] == "work_package_received"), None)
        if next_received:
            reported_to_next_submit.append((next_received["timestamp"] - event["timestamp"]).total_seconds())

    return {
        "events": [
            {
                **event,
                "timestamp": event["timestamp"].isoformat(),
            }
            for event in events
        ],
        "reported_status_sent_count": sum(1 for e in events if e["kind"] == "reported_status_sent"),
        "work_package_received_count": sum(1 for e in events if e["kind"] == "work_package_received"),
        "refine_started_count": sum(1 for e in events if e["kind"] == "refine_started"),
        "work_report_created_to_reported_sent": created_to_sent,
        "reported_sent_to_next_submit_received": reported_to_next_submit,
        "next_submit_received_to_next_refine_started": submit_to_refine[1:] if len(submit_to_refine) > 1 else [],
        "submit_received_to_refine_started": submit_to_refine,
    }


def wait_for_accumulation(node_log_path: Path, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    acceptance = parse_node_log_acceptance(node_log_path)
    while time.monotonic() < deadline:
        acceptance = parse_node_log_acceptance(node_log_path)
        if acceptance.get("accumulated"):
            return acceptance
        time.sleep(0.5)
    return acceptance


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
        "walls": wall,
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
    if run_dir.exists():
        shutil.rmtree(run_dir)
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
        acceptance = parse_node_log_acceptance(node_log_path)
        if args.require_accumulated:
            acceptance = wait_for_accumulation(
                node_log_path,
                timeout=max(0.0, args.wait_accumulation_slots * 6.5),
            )
    finally:
        terminate(node)

    profile_rows = read_profiles(profile_path)
    if not profile_rows:
        profile_rows = parse_node_log_refines(node_log_path)
    summary = summarize_profile(profile_rows)
    cycle = summarize_cycle_events(parse_node_log_cycle_events(node_log_path))
    summary.update(
        {
            "run_index": run_index,
            "measured": measured,
            "init_seconds": init_seconds,
            "builder_seconds": builder_seconds,
            "builder_capped": builder_capped,
            "profile_path": str(profile_path),
            "db_path": str(db_path),
            "acceptance": acceptance,
            "cycle": cycle,
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
    parser.add_argument("--require-accumulated", action="store_true")
    parser.add_argument("--max-refine-wall", type=float, default=None)
    parser.add_argument("--max-refine-p95", type=float, default=None)
    parser.add_argument("--cycle-runs", type=int, default=None)
    parser.add_argument("--max-reported-to-next-refine-start", type=float, default=None)
    parser.add_argument("--require-reported-status-sent", action="store_true")
    parser.add_argument("--wait-accumulation-slots", type=int, default=16)
    args = parser.parse_args()
    if args.cycle_runs is not None and args.max_refines_per_run is None:
        args.max_refines_per_run = args.cycle_runs

    repo = args.repo.resolve()
    args.trace = args.trace.resolve()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stage_dir = args.out_dir / args.stage
    stage_dir.mkdir(parents=True, exist_ok=True)

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
    (stage_dir / f"{args.stage}-metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    for idx in range(args.warmups):
        run_one(args, repo, stage_dir, idx + 1, measured=False)

    summaries = [run_one(args, repo, stage_dir, idx + 1, measured=True) for idx in range(args.runs)]
    measured_wall = [s["median_wall"] for s in summaries if s.get("median_wall") is not None]
    all_refine_walls = [wall for s in summaries for wall in s.get("walls", [])]
    stage_summary = {
        "runs": summaries,
        "all_refine_walls": all_refine_walls,
        "median_wall": statistics.median(measured_wall) if measured_wall else None,
        "p95_wall": percentile(all_refine_walls, 0.95),
        "pvm_setup": sum(float(s.get("pvm_setup") or 0.0) for s in summaries),
        "hostcall_total": sum(float(s.get("hostcall_total") or 0.0) for s in summaries),
        "storage_reads": sum(int(s.get("storage_reads") or 0) for s in summaries),
        "report_hashes": sorted({h for s in summaries for h in s.get("report_hashes", [])}),
        "export_roots": sorted({h for s in summaries for h in s.get("export_roots", [])}),
        "acceptance": {
            "require_accumulated": args.require_accumulated,
            "accumulated_runs": sum(1 for s in summaries if s.get("acceptance", {}).get("accumulated")),
            "guaranteed_runs": sum(1 for s in summaries if s.get("acceptance", {}).get("guaranteed")),
            "accumulate_roots": sorted(
                {
                    s.get("acceptance", {}).get("accumulate_root")
                    for s in summaries
                    if s.get("acceptance", {}).get("accumulate_root")
                }
            ),
        },
        "cycle": {
            "reported_status_sent_count": sum(
                s.get("cycle", {}).get("reported_status_sent_count", 0) for s in summaries
            ),
            "work_package_received_count": sum(
                s.get("cycle", {}).get("work_package_received_count", 0) for s in summaries
            ),
            "refine_started_count": sum(
                s.get("cycle", {}).get("refine_started_count", 0) for s in summaries
            ),
            "work_report_created_to_reported_sent": [
                value
                for s in summaries
                for value in s.get("cycle", {}).get("work_report_created_to_reported_sent", [])
            ],
            "reported_sent_to_next_submit_received": [
                value
                for s in summaries
                for value in s.get("cycle", {}).get("reported_sent_to_next_submit_received", [])
            ],
            "next_submit_received_to_next_refine_started": [
                value
                for s in summaries
                for value in s.get("cycle", {}).get("next_submit_received_to_next_refine_started", [])
            ],
            "submit_received_to_refine_started": [
                value
                for s in summaries
                for value in s.get("cycle", {}).get("submit_received_to_refine_started", [])
            ],
        },
    }
    speedup = None
    if args.baseline_median and stage_summary["median_wall"]:
        speedup = args.baseline_median / stage_summary["median_wall"]

    (stage_dir / f"{args.stage}-summary.json").write_text(
        json.dumps(stage_summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    append_ledger(args.out_dir / "results.md", args.stage, args.change, stage_summary, speedup)
    if args.require_accumulated:
        missing = [s["run_index"] for s in summaries if not s.get("acceptance", {}).get("accumulated")]
        if missing:
            raise SystemExit(f"Required accumulation was not observed for measured runs: {missing}")
    if args.max_refine_wall is not None:
        too_slow = [wall for wall in all_refine_walls if wall > args.max_refine_wall]
        if too_slow:
            raise SystemExit(
                f"Refine wall limit failed: {len(too_slow)} refine(s) exceeded {args.max_refine_wall:.3f}s; "
                f"max={max(too_slow):.6f}s"
            )
    if args.max_refine_p95 is not None and stage_summary["p95_wall"] is not None:
        if stage_summary["p95_wall"] > args.max_refine_p95:
            raise SystemExit(
                f"Refine p95 limit failed: p95={stage_summary['p95_wall']:.6f}s > {args.max_refine_p95:.3f}s"
            )
    if args.require_reported_status_sent and stage_summary["cycle"]["reported_status_sent_count"] == 0:
        raise SystemExit("Required reported_status_sent cycle event was not observed")
    if args.max_reported_to_next_refine_start is not None:
        submit_to_start = stage_summary["cycle"]["next_submit_received_to_next_refine_started"]
        too_slow = [value for value in submit_to_start if value > args.max_reported_to_next_refine_start]
        if too_slow:
            raise SystemExit(
                "Reported-to-next-refine-start limit failed: "
                f"{len(too_slow)} cycle(s) exceeded {args.max_reported_to_next_refine_start:.3f}s; "
                f"max={max(too_slow):.6f}s"
            )
    print(json.dumps(stage_summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
