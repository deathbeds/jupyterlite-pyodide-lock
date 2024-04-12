"""Tests of the ``jupyter-lite`` CLI with ``jupyterlite-pyodide-lock``."""

import difflib
from pathlib import Path

import pyodide_lock
from jupyterlite_core.constants import UTF8
from jupyterlite_pyodide_kernel.constants import PYODIDE_LOCK


def test_cli_good_build(
    lite_cli,
    a_lite_dir: Path,
    a_lite_config_with_widgets: Path,
) -> None:
    """Verify a build works, twice."""
    from jupyterlite_pyodide_lock.constants import PYODIDE_LOCK_STEM

    assert "webdriver" in a_lite_config_with_widgets.read_text(**UTF8)

    build, stdout, stderr = lite_cli("build", "--debug")
    assert build == 0

    out = a_lite_dir / "_output"
    assert out.exists()
    lock_dir = out / "static" / PYODIDE_LOCK_STEM
    assert lock_dir.exists()
    lock = lock_dir / PYODIDE_LOCK
    lock_text = lock.read_text(**UTF8)
    pyodide_lock.PyodideLockSpec.from_json(lock)

    rebuild, stdout, stderr = lite_cli("build", "--debug")
    assert rebuild == 0

    relock_text = lock.read_text(**UTF8)
    diff = [
        *difflib.unified_diff(
            lock_text.splitlines(),
            relock_text.splitlines(),
            "build",
            "rebuild",
        ),
    ]
    print("\n".join(diff))
    assert not diff, "didn't see same lockfile on rebuild"
