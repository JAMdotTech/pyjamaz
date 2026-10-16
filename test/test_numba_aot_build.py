import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def run_build_step(args, app, env):
    result = subprocess.run(
        args, cwd=app, env=env, capture_output=True, text=True, timeout=300
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def test_aot_build_propagates_compiler_failure(tmp_path):
    # Inject a compiler failure without importing the PVM or changing its cache.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    python = bin_dir / "python"
    python.write_text("#!/bin/sh\nexit 42\n")
    python.chmod(0o755)
    env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ["PATH"])

    result = subprocess.run(
        ["bash", str(ROOT / "scripts/build_numba_aot.sh")],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30,
    )

    assert result.returncode == 42, result.stdout + result.stderr
    assert "AOT cache warmup completed successfully" not in result.stdout


def test_cache_only_smoke_after_docker_source_stripping(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    shutil.copytree(
        ROOT / "pyjamaz", app / "pyjamaz",
        ignore=shutil.ignore_patterns(
            "local_settings.py", "__pycache__", "*.pyc", "*.pyo", "*.nbc", "*.nbi"
        ),
    )
    scripts = app / "scripts"
    scripts.mkdir()
    for name in ("build_numba_aot.sh", "check_numba_cache.py"):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)

    # The build script invokes `python`; keep it in this test's environment.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    python = bin_dir / "python"
    python.write_text(f"#!/bin/sh\nexec {shlex.quote(sys.executable)} \"$@\"\n")
    python.chmod(0o755)
    env = {key: value for key, value in os.environ.items() if not key.startswith("NUMBA_")}
    for key in ("JAM_FUZZ", "JAM_FUZZ_SPEC", "PYTHONOPTIMIZE"):
        env.pop(key, None)
    cache = tmp_path / "numba-cache"
    cache.mkdir()
    env.update(
        PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
        PYTHONPATH=str(app),
        PYTHONDONTWRITEBYTECODE="1",
        NUMBA_CACHE_DIR=str(cache),
        NUMBA_CPU_NAME="generic",
        NUMBA_CPU_FEATURES="",
        NUMBA_CACHE_ONLY="1",
        NUMBA_CACHE_WARMUP="0",
        PVM_INTERPRETER="NUMBA_AOT",
    )
    run_build_step(["bash", str(scripts / "build_numba_aot.sh")], app, env)
    assert list(cache.rglob("*.nbc")), "Warmup did not populate the clean cache"

    # Reproduce the Docker layout: legacy bytecode everywhere, retaining only
    # the Numba sources needed by its cache locator and code fingerprints.
    run_build_step(
        [sys.executable, "-m", "compileall", "-q", "-b", "-d", "/app", "./pyjamaz"],
        app, env,
    )
    numba_dir = app / "pyjamaz/pvm/interpreters/numba"
    for source in (app / "pyjamaz").rglob("*.py"):
        if not source.is_relative_to(numba_dir):
            source.unlink()
    shutil.rmtree(numba_dir / "__pycache__", ignore_errors=True)
    assert not (app / "pyjamaz/__init__.py").exists()
    assert (app / "pyjamaz/__init__.pyc").is_file()
    assert not (numba_dir / "__pycache__").exists()
    assert all(source.is_relative_to(numba_dir) for source in (app / "pyjamaz").rglob("*.py"))

    # A fresh process must resolve the stripped copy, even with an editable
    # installation of pyjamaz available in the parent test environment.
    smoke = (
        "from pathlib import Path; import pyjamaz; import runpy; "
        f"expected = Path({str(app / 'pyjamaz/__init__.pyc')!r}); "
        "origin = Path(pyjamaz.__file__).resolve(); "
        "assert origin == expected.resolve(), (origin, expected); "
        f"runpy.run_path({str(scripts / 'check_numba_cache.py')!r}, run_name='__main__')"
    )
    args = [sys.executable, "-c", smoke]
    result = run_build_step(args, app, env)
    assert "Numba cache-only PVM smoke check passed" in result.stdout

    # Prove the smoke check cannot silently recompile when an image cache is
    # missing, rather than merely succeeding via a JIT fallback.
    empty_cache = tmp_path / "empty-cache"
    empty_cache.mkdir()
    env["NUMBA_CACHE_DIR"] = str(empty_cache)
    result = subprocess.run(
        args, cwd=app, env=env, capture_output=True, text=True, timeout=300
    )
    assert result.returncode != 0, result.stdout + result.stderr
    assert "NUMBA cache-only: cached overload not found" in result.stderr
    assert not list(empty_cache.rglob("*.nbc"))
