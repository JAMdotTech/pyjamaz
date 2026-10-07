"""Resolve W3F STF vectors without exposing fixtures to production code.

The repository keeps a compact vendored corpus under ``test/fixtures``.  Set
``JAM_TEST_VECTORS`` to either a ``jam-test-vectors`` checkout or its ``stf``
directory to run the same tests against the complete upstream tiny/full
corpus.  The selected runtime profile still comes from ``JAM_FUZZ_SPEC``.
"""

from __future__ import annotations

import os
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent


def stf_vector_dir(
    component: str,
    profile: str,
    *,
    local_component: str | None = None,
    local_profiled: bool = True,
) -> Path:
    """Return the selected component/profile vector directory.

    External vectors are deliberately available only through this test helper.
    Production STF and fuzzer-target code must compute transitions and must
    never consult JSON expected-value sidecars.
    """

    external_root = os.environ.get("JAM_TEST_VECTORS")
    if external_root:
        root = Path(external_root).expanduser().resolve()
        if (root / "stf").is_dir():
            root = root / "stf"
        selected = root / component / profile
        if not selected.is_dir():
            raise RuntimeError(
                f"JAM_TEST_VECTORS has no {component!r} vectors for profile {profile!r}: "
                f"{selected}"
            )
        return selected

    selected = TEST_DIR / "fixtures" / (local_component or component)
    if local_profiled:
        selected = selected / profile
    return selected


def codec_vector_dir(profile: str) -> Path:
    """Return W3F codec vectors for the selected tiny/full profile."""
    external_root = os.environ.get("JAM_TEST_VECTORS")
    if external_root:
        root = Path(external_root).expanduser().resolve()
        selected = root / "codec" / profile
        if not selected.is_dir():
            raise RuntimeError(
                f"JAM_TEST_VECTORS has no codec vectors for profile {profile!r}: "
                f"{selected}"
            )
        return selected
    return TEST_DIR / "fixtures" / "codec" / "w3f"


def trie_vector_file() -> Path:
    """Return the selected W3F Appendix D trie-vector file."""
    external_root = os.environ.get("JAM_TEST_VECTORS")
    if external_root:
        selected = Path(external_root).expanduser().resolve() / "trie" / "trie.json"
        if not selected.is_file():
            raise RuntimeError(
                f"JAM_TEST_VECTORS has no Appendix D trie vectors: {selected}"
            )
        return selected
    return TEST_DIR / "fixtures" / "trie.json"


def shuffle_vector_file() -> Path:
    """Return the selected W3F Appendix F shuffle-vector file."""
    external_root = os.environ.get("JAM_TEST_VECTORS")
    if external_root:
        selected = Path(external_root).expanduser().resolve() / "shuffle" / "shuffle_tests.json"
        if not selected.is_file():
            raise RuntimeError(
                f"JAM_TEST_VECTORS has no Appendix F shuffle vectors: {selected}"
            )
        return selected
    return TEST_DIR / "fixtures" / "shuffle_tests.json"
