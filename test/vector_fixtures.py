"""Resolve W3F test vectors without exposing fixtures to production code.

The repository keeps a compact vendored corpus under ``test/fixtures``.  Set
``JAM_TEST_VECTORS`` to either a ``jam-test-vectors`` checkout or its ``stf``
directory to run the same tests against the complete upstream tiny/full
corpus.  The selected runtime profile still comes from ``JAM_FUZZ_SPEC``.
"""

from __future__ import annotations

import os
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent


def _external_vector_root() -> Path | None:
    external_root = os.environ.get("JAM_TEST_VECTORS")
    if not external_root:
        return None
    root = Path(external_root).expanduser().resolve()
    return root.parent if root.name == "stf" else root


def _require_vendored_tiny(profile: str) -> None:
    if profile != "tiny":
        raise RuntimeError(
            f"Vendored vectors support only profile 'tiny', not {profile!r}; "
            "set JAM_TEST_VECTORS to a jam-test-vectors release checkout "
            "or its stf directory."
        )


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

    root = _external_vector_root()
    if root is not None:
        selected = root / "stf" / component / profile
        if not selected.is_dir():
            raise RuntimeError(
                f"JAM_TEST_VECTORS has no {component!r} vectors for profile {profile!r}: "
                f"{selected}"
            )
        return selected

    _require_vendored_tiny(profile)
    selected = TEST_DIR / "fixtures" / (local_component or component)
    if local_profiled:
        selected = selected / profile
    if not selected.is_dir():
        raise RuntimeError(f"Missing vendored {component!r} vectors: {selected}")
    return selected


def codec_vector_dir(profile: str) -> Path:
    """Return W3F codec vectors for the selected tiny/full profile."""
    root = _external_vector_root()
    if root is not None:
        selected = root / "codec" / profile
        if not selected.is_dir():
            raise RuntimeError(
                f"JAM_TEST_VECTORS has no codec vectors for profile {profile!r}: "
                f"{selected}"
            )
        return selected
    _require_vendored_tiny(profile)
    return TEST_DIR / "fixtures" / "codec" / "w3f"


def trie_vector_file() -> Path:
    """Return the selected W3F Appendix D trie-vector file."""
    root = _external_vector_root()
    if root is not None:
        selected = root / "trie" / "trie.json"
        if not selected.is_file():
            raise RuntimeError(
                f"JAM_TEST_VECTORS has no Appendix D trie vectors: {selected}"
            )
        return selected
    return TEST_DIR / "fixtures" / "trie.json"


def shuffle_vector_file() -> Path:
    """Return the selected W3F Appendix F shuffle-vector file."""
    root = _external_vector_root()
    if root is not None:
        selected = root / "shuffle" / "shuffle_tests.json"
        if not selected.is_file():
            raise RuntimeError(
                f"JAM_TEST_VECTORS has no Appendix F shuffle vectors: {selected}"
            )
        return selected
    return TEST_DIR / "fixtures" / "shuffle_tests.json"
