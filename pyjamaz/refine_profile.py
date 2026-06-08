import atexit
import contextvars
import json
import os
import time
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional


_profile_env = os.getenv("PYJAMAZ_REFINE_PROFILE")
ENABLED = bool(_profile_env and _profile_env.lower() not in ("0", "false", "no", "off"))
_DEFAULT_OUTPUT = Path("artifacts") / "refine-bench" / "refine-profile.jsonl"
_CURRENT: contextvars.ContextVar[Optional["RefineProfile"]] = contextvars.ContextVar(
    "pyjamaz_refine_profile_current",
    default=None,
)
_PROCESS_COUNTERS: dict[str, int] = defaultdict(int)


def _output_path() -> Path:
    if not _profile_env or _profile_env == "1":
        return _DEFAULT_OUTPUT
    return Path(_profile_env)


class RefineProfile:
    def __init__(self, work_package_hash: bytes | None = None, core_index: int | None = None, items: int | None = None):
        self.started_at = time.perf_counter()
        self.work_package_hash = work_package_hash.hex() if work_package_hash else None
        self.core_index = core_index
        self.items = items
        self.report_hash: str | None = None
        self.exports_root: str | None = None
        self.timers: dict[str, float] = defaultdict(float)
        self.counts: dict[str, int] = defaultdict(int)
        self.hostcalls: dict[str, dict[str, float | int]] = defaultdict(lambda: {"count": 0, "seconds": 0.0})

    @contextmanager
    def timer(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.timers[name] += time.perf_counter() - start

    def count(self, name: str, value: int = 1) -> None:
        self.counts[name] += value

    def hostcall(self, host_call_id: int, elapsed: float) -> None:
        key = str(host_call_id)
        data = self.hostcalls[key]
        data["count"] = int(data["count"]) + 1
        data["seconds"] = float(data["seconds"]) + elapsed

    def finish(self, report_hash: bytes | None = None, exports_root: bytes | None = None) -> None:
        if report_hash is not None:
            self.report_hash = report_hash.hex()
        if exports_root is not None:
            self.exports_root = exports_root.hex()

        row: dict[str, Any] = {
            "kind": "refine",
            "wall_seconds": time.perf_counter() - self.started_at,
            "work_package_hash": self.work_package_hash,
            "core_index": self.core_index,
            "items": self.items,
            "report_hash": self.report_hash,
            "exports_root": self.exports_root,
            "timers": dict(self.timers),
            "counts": dict(self.counts),
            "hostcalls": {k: dict(v) for k, v in self.hostcalls.items()},
        }
        path = _output_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(row, sort_keys=True) + "\n")


def current() -> Optional[RefineProfile]:
    if not ENABLED:
        return None
    return _CURRENT.get()


def start(work_package_hash: bytes | None = None, core_index: int | None = None, items: int | None = None) -> RefineProfile | None:
    if not ENABLED:
        return None
    profile = RefineProfile(work_package_hash=work_package_hash, core_index=core_index, items=items)
    _CURRENT.set(profile)
    return profile


@contextmanager
def timer(name: str):
    profile = current()
    if profile is None:
        yield
        return
    with profile.timer(name):
        yield


def count(name: str, value: int = 1) -> None:
    profile = current()
    if profile is not None:
        profile.count(name, value)


def hostcall(host_call_id: int, elapsed: float) -> None:
    profile = current()
    if profile is not None:
        profile.hostcall(host_call_id, elapsed)


def process_count(name: str, value: int = 1) -> None:
    if ENABLED:
        _PROCESS_COUNTERS[name] += value


def _write_process_counters() -> None:
    if not ENABLED or not _PROCESS_COUNTERS:
        return
    path = _output_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps({"kind": "process", "counts": dict(_PROCESS_COUNTERS)}, sort_keys=True) + "\n")


atexit.register(_write_process_counters)
